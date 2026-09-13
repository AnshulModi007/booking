# Campus Facility Booking — Implementation Spec

## What this is

A booking system for shared campus facilities (badminton/TT courts, music
room, club rooms, lab equipment). Students sign in with their institute email
and reserve fixed-length slots. Admins manage facilities and block them for
maintenance or events.

Target deployment: real use at IIT Dharwad, not a demo. That constraint drives
several decisions below — in particular the availability endpoint and the
minimal mobile web UI, both of which an API-only project could skip and still
"work" while having zero users.

## Stack

FastAPI, SQLAlchemy 2.x, PostgreSQL, Alembic, JWT (python-jose + passlib),
pytest, Docker + docker-compose, GitHub Actions. Deployment on Render (managed
Postgres, no VPS administration).

Postgres specifically, not SQLite — the core correctness guarantee in this
project depends on Postgres features (partial unique indexes, `EXCLUDE`
constraints, `SELECT ... FOR UPDATE`). SQLite cannot express them.

---

## Data model

### User
| column | type | notes |
|---|---|---|
| id | int PK | |
| email | text unique not null | institute domain enforced at signup |
| password | text not null | bcrypt hash |
| full_name | text | |
| role | text not null | `student` or `admin`, default `student` |
| created_at | timestamptz not null | `now()` |

### Facility
| column | type | notes |
|---|---|---|
| id | int PK | |
| name | text not null | e.g. "Badminton Court 1" |
| type | text not null | `court`, `room`, `equipment` |
| location | text | |
| slot_duration_minutes | int not null | e.g. 60 |
| opens_at | time not null | e.g. 06:00 |
| closes_at | time not null | e.g. 22:00 |
| max_advance_days | int not null | how far ahead booking is allowed, default 7 |
| max_active_bookings_per_user | int not null | default 2 |
| min_cancel_notice_minutes | int not null | default 60 |
| is_active | bool not null | soft disable, default true |

Policy lives on the facility, not in code constants, so an admin can tune a
busy court without a redeploy.

### Closure
| column | type | notes |
|---|---|---|
| id | int PK | |
| facility_id | int FK → facilities | on delete cascade |
| start_time | timestamptz not null | |
| end_time | timestamptz not null | |
| reason | text | "maintenance", "inter-hall tournament" |
| created_by | int FK → users | |

Admin-created. Blocks bookings in the range and hides those slots from
availability.

### Booking
| column | type | notes |
|---|---|---|
| id | int PK | |
| facility_id | int FK → facilities | on delete cascade |
| user_id | int FK → users | on delete cascade |
| start_time | timestamptz not null | |
| end_time | timestamptz not null | |
| status | text not null | `confirmed` / `cancelled`, default `confirmed` |
| created_at | timestamptz not null | |
| cancelled_at | timestamptz | |

Cancellation is a status change, never a row delete — you want the history,
and it makes no-show tracking possible later.

All timestamps are `timestamptz` and stored in UTC. Convert to IST at the
presentation layer only. Mixing naive and aware datetimes is the most common
source of bugs in this kind of project.

---

## Database constraints

These go in Alembic migrations. They are the correctness backbone of the
project — not decoration.

```sql
-- times must be sane
ALTER TABLE bookings ADD CONSTRAINT end_after_start CHECK (end_time > start_time);
ALTER TABLE closures ADD CONSTRAINT closure_end_after_start CHECK (end_time > start_time);

-- no two confirmed bookings may overlap on the same facility
CREATE EXTENSION IF NOT EXISTS btree_gist;
ALTER TABLE bookings
  ADD CONSTRAINT no_overlapping_bookings
  EXCLUDE USING gist (
    facility_id WITH =,
    tstzrange(start_time, end_time) WITH &&
  ) WHERE (status = 'confirmed');
```

Note the `WHERE (status = 'confirmed')` predicate: cancelled bookings are
excluded from the constraint, so cancelling genuinely frees the slot.

`tstzrange`, not `tsrange` — the columns are `timestamptz`. Using the wrong one
fails at migration time with a type error.

---

## Concurrency — the part that matters

There are two distinct concurrency problems here, and they have different
solutions. Understanding *why* they differ is the main technical takeaway of
this project.

### Problem 1: double-booking — solvable in the database

Two students request the same court at the same instant. The naive
implementation is:

```python
existing = db.query(Booking).filter(...overlaps...).first()
if existing:
    raise HTTPException(409)
db.add(new_booking)
db.commit()
```

This is a race condition. Both requests can run the SELECT before either runs
the INSERT, both find nothing, and both succeed.

The fix is the `EXCLUDE` constraint above. Postgres itself rejects the second
INSERT, so there is no window between check and write. The application code
becomes:

```python
db.add(new_booking)
try:
    db.commit()
except IntegrityError:
    db.rollback()
    raise HTTPException(409, "That slot was just taken")
```

The pre-check can stay as a fast path for a friendlier error message, but it
is an optimization, not the guarantee. The constraint is the guarantee.

### Problem 2: per-user quota — NOT solvable with a constraint

"A student may hold at most 2 active bookings" is a condition across multiple
rows for the same user. No unique index or `EXCLUDE` constraint can express
it. The same race applies: two simultaneous requests each count 1 existing
booking, both pass, the student ends up with 3.

Fix: serialize per user by taking a row lock inside the transaction before
counting.

```python
# lock this user's row for the duration of the transaction
db.execute(
    select(User).where(User.id == current_user.id).with_for_update()
)

active = db.query(Booking).filter(
    Booking.user_id == current_user.id,
    Booking.status == "confirmed",
    Booking.end_time > func.now(),
).count()

if active >= facility.max_active_bookings_per_user:
    raise HTTPException(409, "Booking limit reached")

db.add(new_booking)
db.commit()   # lock releases here
```

Concurrent requests from the *same* user now queue behind the lock; requests
from *different* users are unaffected, since they lock different rows.

Being able to articulate the boundary — problem 1 has a clean declarative
answer, problem 2 needs explicit locking because the invariant spans rows — is
worth more in an interview than reciting either fix alone.

---

## API surface

### Auth
| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/auth/register` | — | signup; reject non-institute email domains |
| POST | `/auth/login` | — | returns JWT |
| GET | `/auth/me` | student | current user profile |

### Facilities
| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/facilities` | — | list active facilities, filterable by `type` |
| GET | `/facilities/{id}` | — | detail incl. policy fields |
| POST | `/facilities` | admin | create |
| PATCH | `/facilities/{id}` | admin | update / deactivate |

### Availability — the most important endpoint

```
GET /facilities/{id}/availability?date=2026-09-20
```

```json
{
  "facility_id": 3,
  "date": "2026-09-20",
  "slots": [
    {"start": "2026-09-20T06:00:00+05:30", "end": "...07:00...", "available": true},
    {"start": "...07:00...", "end": "...08:00...", "available": false, "reason": "booked"},
    {"start": "...08:00...", "end": "...09:00...", "available": false, "reason": "closure"}
  ]
}
```

Algorithm:
1. Generate candidate slots from `opens_at` → `closes_at` stepping by
   `slot_duration_minutes`.
2. Fetch confirmed bookings for that facility and date; mark overlapping slots
   unavailable with `reason: "booked"`.
3. Fetch closures overlapping that date; mark those slots `reason: "closure"`.
4. Mark slots already in the past, or beyond `max_advance_days`, unavailable.

This endpoint is what the UI actually calls. Without it, users have no way to
see what's free, and the product doesn't exist regardless of how correct the
booking logic is.

### Bookings
| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/bookings/me` | student | own bookings, `?upcoming=true` filter |
| POST | `/bookings` | student | create (all validation below applies) |
| DELETE | `/bookings/{id}` | student (owner) | cancel |
| GET | `/bookings` | admin | all bookings, filterable |

Validation on `POST /bookings`, in order:
1. Facility exists and `is_active`
2. `start_time` is in the future
3. `start_time` is within `max_advance_days`
4. Slot is aligned to the facility grid (matches `opens_at` + n ×
   `slot_duration_minutes`) and duration equals `slot_duration_minutes`
5. Does not fall inside a closure
6. User quota not exceeded — under the row lock described above
7. Insert; catch `IntegrityError` → 409

Cancellation rejects if `start_time - now < min_cancel_notice_minutes`.

### Closures
| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/facilities/{id}/closures` | — | upcoming closures |
| POST | `/closures` | admin | create |
| DELETE | `/closures/{id}` | admin | remove |

Creating a closure over existing confirmed bookings should return those
bookings and require `?force=true` to proceed, cancelling them. Silently
destroying reservations is the kind of thing that gets a tool abandoned.

---

## Minimal web UI

Plain HTML + vanilla JS, served as static files by FastAPI. No React, no build
step — a framework here adds setup cost without adding anything the project
needs.

Four pages:
1. **Login / register** — institute email + password
2. **Facility list** — cards, tap one to open
3. **Availability + book** — date picker, slot grid from the availability
   endpoint, tap a free slot to book. This is the main screen.
4. **My bookings** — upcoming list with cancel buttons

Must be usable one-handed on a phone. Students will book from their phones
while walking to the court, not from a laptop.

Admin can be a single crude page behind a role check: add facility, add
closure, view all bookings.

---

## Testing

The suite exists to prove the invariants hold, not to inflate a count.

**Concurrency tests — the ones that matter:**
- Two overlapping bookings on one facility → exactly one succeeds, other gets 409
- Same slot on *different* facilities → both succeed (constraint is scoped
  per-facility, not global)
- Cancel a booking, rebook that slot → succeeds (the partial-index predicate
  works)
- Truly parallel requests using threads against a real Postgres — two threads
  POSTing the same slot simultaneously. Exactly one 201, one 409. A sequential
  test passes even with a naive implementation; only a parallel one actually
  proves the constraint.
- Quota: fire N+1 concurrent bookings for one user, assert only N succeed

**Sanity check on the tests themselves:** temporarily drop the `EXCLUDE`
constraint and confirm the overlap test *fails*. A test that passes with the
protection removed is testing nothing.

**Availability tests:**
- Slot grid matches opening hours and duration
- Booked slots marked unavailable
- Closure-covered slots marked unavailable with the right reason
- Past slots excluded

**Validation tests:** misaligned start time, wrong duration, past date, beyond
`max_advance_days`, cancel inside notice window, non-owner cancel → 403.

**Auth tests:** non-institute email rejected, unauthenticated booking → 401,
student hitting admin endpoint → 403.

Use a separate test database, transaction-rollback fixtures per test, and
`pytest.mark.parametrize` for the validation cases.

---

## Build order

Each stage should end with something runnable and verified before moving on.

1. **Scaffold** — FastAPI app, config, database session, Docker Compose with
   Postgres, health endpoint. Verify: `docker-compose up` and `GET /health`
   returns 200.
2. **Auth** — User model, register with domain check, login, JWT, `get_current_user`
   and `require_admin` dependencies. Verify: register → login → `/auth/me`.
3. **Facilities** — model, admin CRUD, public list/detail.
4. **Availability** — the slot-generation endpoint, bookings not yet
   implemented so every slot is free. Verify the grid against opening hours.
5. **Bookings, correctness first** — model plus *both* migrations (check
   constraint and `EXCLUDE`) before any endpoint code. Then POST/cancel with
   full validation and the quota lock. Write the concurrency tests here, not
   later.
6. **Closures** — model, admin endpoints, wire into availability and booking
   validation.
7. **Web UI** — the four pages.
8. **CI + deploy** — GitHub Actions running pytest against a Postgres service
   container; deploy to Render with managed Postgres; run `alembic upgrade head`
   as the release command.

Stage 5 is the project. If time runs short, cut the UI polish and closures
before cutting anything in stage 5.

---

## Deliberately deferred to v2

- **Waitlist** — when a booking is cancelled, who gets the slot? Interesting
  precisely because awarding it reintroduces a race the `EXCLUDE` constraint
  doesn't solve on its own. Worth building properly later rather than rushing.
- Email confirmations and reminders (background tasks + scheduler)
- No-show marking and reliability scoring
- Recurring bookings (club practice every Tuesday)
- Usage analytics for admins

---

## README notes for later

When writing the README, the section worth real effort is the concurrency
explanation: why check-then-insert is broken, why the `EXCLUDE` constraint
fixes booking overlap declaratively, and why the per-user quota needs row
locking instead. Include the actual SQL. That section is the thing a reviewer
will read, and it's the thing you should be able to explain out loud without
notes.