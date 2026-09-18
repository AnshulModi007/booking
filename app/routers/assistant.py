from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import date as date_type, datetime, timezone
import json
import ollama

from .. import models, schemas, oauth2
from ..database import get_db
from ..config import settings
from . import booking as booking_router, facility as facility_router, availiblity as availability_router, closure as closure_router

router = APIRouter(prefix="/assistant", tags=["Assistant"])

SYSTEM_PROMPT = (
    "You are a booking assistant for a campus facility booking system. "
    "Always use the tools to look up real facilities, availability, and bookings — "
    "never invent facility IDs, booking IDs, or slot times. "
    "facility_id is always a number. If you don't already know a facility's numeric id "
    "from an earlier tool result in this conversation, call list_facilities first to look "
    "it up by name before calling get_availability, create_booking, or cancel_booking — "
    "never pass a facility name as facility_id. When looking up a facility by name, call "
    "list_facilities with NO arguments and search the returned list yourself — its 'type' "
    "argument is a strict category filter ('court', 'room', or 'equipment' only), never a "
    "name search. "
    "Confirm the facility, date, and time with the user before calling create_booking. "
    "If the user has not given BOTH a specific date and a specific start time (e.g. 'book "
    "cricket for me' with no date/time), do NOT call create_booking and do NOT guess a "
    "time — ask the user which date and time they want, or call get_availability for a date "
    "they mention so they can pick from the real slot list.\n\n"
    "Domain model: each facility has an 'opens_at' and 'closes_at' time-of-day "
    "(e.g. '06:00' to '22:00') that repeats every single day — these are daily opening "
    "hours, NOT a date and NOT when the facility 'became available'. To find out what's "
    "actually free on a specific day, always call get_availability with that facility's "
    "id and a date — never infer real availability from a facility's opening hours alone, "
    "and never tell the user a facility has been 'available since' or 'available from' a "
    "particular date.\n\n"
    "Time precision: every time in a tool's input or output (opens_at, closes_at, slot start/end, "
    "booking start_time/end_time) is UTC and in 24-hour HH:MM form. When you tell the user a time, "
    "state the exact value from the tool result — never round, approximate, or guess AM/PM. "
    "If it's more natural to speak in 12-hour time, convert precisely (e.g. '09:30' UTC is "
    "'9:30 AM', not '3:30 PM') and say it's UTC. A booking will be silently wrong if you state "
    "a time that doesn't exactly match the tool data.\n\n"
    "Grounding rule: only state facts that literally appear in the JSON returned by a tool "
    "call you just made in this conversation. Never say a facility is unavailable, closed, "
    "fully booked, or has specific hours unless that exact fact is present in a tool result. "
    "If you do not have the information, say so and call the appropriate tool or ask the "
    "user for what is missing — do not guess.\n\n"
    "Never do time arithmetic yourself — you are unreliable at it. Never compute an end_time "
    "from a start_time and a duration, and never invent or adjust a start_time to 'fix' a "
    "duration mismatch. The ONLY valid source for a booking's start_time and end_time is a "
    "single slot object with available:true from a get_availability result you already "
    "received in this conversation — copy that slot's 'start' and 'end' values into "
    "create_booking byte-for-byte. If the user asks for a time that doesn't exactly match one "
    "of those slot objects, call get_availability for that date (if you haven't already) and "
    "show them the real slot list to pick from — do not construct a time and do not claim a "
    "duration mismatch without quoting the real slot_duration_minutes value from list_facilities.\n\n"
    "Only call create_facility, deactivate_facility, create_closure, or delete_closure if the "
    "current user's role (given below) is 'admin'. If a non-admin user asks to create/edit a "
    "facility or manage a closure, tell them plainly that this requires an admin account — "
    "never claim you did it or that you can do it for them."
)

TOOLS = [
    {"type": "function", "function": {
        "name": "list_facilities",
        "description": "List active facilities. Returns every facility with its name, id, and type — call with no arguments to search by name yourself.",
        "parameters": {"type": "object", "properties": {
            "type": {"type": "string", "enum": ["court", "room", "equipment"],
                      "description": "Optional STRICT category filter — must be exactly one of these three values. Never pass a facility name here; to find a facility by name, call with no arguments and look through the results."}}},
    }},
    {"type": "function", "function": {
        "name": "get_availability",
        "description": "Get available slots for a facility on a date",
        "parameters": {"type": "object", "properties": {
            "facility_id": {"type": "integer"},
            "date": {"type": "string", "description": "YYYY-MM-DD"}},
            "required": ["facility_id", "date"]},
    }},
    {"type": "function", "function": {
        "name": "create_booking",
        "description": "Book a facility slot for the current user",
        "parameters": {"type": "object", "properties": {
            "facility_id": {"type": "integer"},
            "start_time": {"type": "string", "description": "ISO 8601 datetime"},
            "end_time": {"type": "string", "description": "ISO 8601 datetime"}},
            "required": ["facility_id", "start_time", "end_time"]},
    }},
    {"type": "function", "function": {
        "name": "cancel_booking",
        "description": "Cancel one of the current user's bookings",
        "parameters": {"type": "object", "properties": {
            "booking_id": {"type": "integer"}}, "required": ["booking_id"]},
    }},
    {"type": "function", "function": {
        "name": "list_my_bookings",
        "description": "List the current user's own bookings",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "create_facility",
        "description": "Create a new facility. Admin only — will be rejected for a non-admin user.",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string"},
            "type": {"type": "string", "enum": ["court", "room", "equipment"]},
            "location": {"type": "string"},
            "slot_duration_minutes": {"type": "integer"},
            "opens_at": {"type": "string", "description": "HH:MM, 24-hour, UTC"},
            "closes_at": {"type": "string", "description": "HH:MM, 24-hour, UTC"},
            "max_advance_days": {"type": "integer"},
            "max_active_bookings_per_user": {"type": "integer"},
            "min_cancellation_notice_hours": {"type": "integer"}},
            "required": ["name", "type", "location", "slot_duration_minutes", "opens_at",
                         "closes_at", "max_advance_days", "max_active_bookings_per_user",
                         "min_cancellation_notice_hours"]},
    }},
    {"type": "function", "function": {
        "name": "deactivate_facility",
        "description": "Deactivate a facility so it stops accepting new bookings. Admin only.",
        "parameters": {"type": "object", "properties": {
            "facility_id": {"type": "integer"}}, "required": ["facility_id"]},
    }},
    {"type": "function", "function": {
        "name": "create_closure",
        "description": "Block a facility for maintenance or an event over a time range. Admin only. "
                        "If confirmed bookings overlap the range, this fails unless force=true, which "
                        "cancels those bookings — always ask the user to confirm before passing force=true.",
        "parameters": {"type": "object", "properties": {
            "facility_id": {"type": "integer"},
            "start_time": {"type": "string", "description": "ISO 8601 datetime, UTC"},
            "end_time": {"type": "string", "description": "ISO 8601 datetime, UTC"},
            "reason": {"type": "string"},
            "force": {"type": "boolean", "description": "true to cancel conflicting bookings and proceed"}},
            "required": ["facility_id", "start_time", "end_time", "reason"]},
    }},
    {"type": "function", "function": {
        "name": "delete_closure",
        "description": "Remove an existing closure. Admin only.",
        "parameters": {"type": "object", "properties": {
            "closure_id": {"type": "integer"}}, "required": ["closure_id"]},
    }},
]

ADMIN_TOOL_NAMES = {"create_facility", "deactivate_facility", "create_closure", "delete_closure"}

KNOWN_TOOL_NAMES = {t["function"]["name"] for t in TOOLS}


def _extract_leaked_tool_call(content: str):
    """The model sometimes narrates a tool call as JSON text in its reply
    instead of using the structured tool-calling API — e.g. writing
    '{"name": "create_booking", "parameters": {...}}' as visible text.
    Detect that and recover the intended call instead of showing raw JSON
    to the user or silently dropping the action."""
    depth = 0
    start = None
    for i, ch in enumerate(content):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    try:
                        obj = json.loads(content[start:i + 1])
                    except (json.JSONDecodeError, TypeError):
                        continue
                    name = obj.get("name")
                    args = obj.get("parameters", obj.get("arguments"))
                    if name in KNOWN_TOOL_NAMES and isinstance(args, dict):
                        return name, args
    return None


def _run_tool(name: str, args: dict, db: Session, current_user: models.User) -> dict:
    try:
        if name in ADMIN_TOOL_NAMES and current_user.role != "admin":
            return {"error": "This action requires an admin account. The current user is not an admin."}
        if name == "list_facilities":
            result = facility_router.list_facilities(type=args.get("type"), db=db)
            facilities = []
            for f in result:
                data = schemas.FacilityResponse.model_validate(f).model_dump(mode="json")
                data["opens_at"] = f.opens_at.strftime("%H:%M")
                data["closes_at"] = f.closes_at.strftime("%H:%M")
                facilities.append(data)
            return {"facilities": facilities}
        if name == "get_availability":
            result = availability_router.get_availiblity(id=args["facility_id"], date=date_type.fromisoformat(args["date"]), db=db)
            return result.model_dump(mode="json")
        if name == "create_booking":
            # the model sometimes copies "start"/"end" verbatim from a
            # get_availability slot object instead of renaming to the
            # start_time/end_time this tool actually expects — accept both.
            booking_args = {
                "facility_id": args.get("facility_id"),
                "start_time": args.get("start_time", args.get("start")),
                "end_time": args.get("end_time", args.get("end")),
            }
            payload = schemas.BookingCreate(**booking_args)
            result = booking_router.create_booking(payload, db=db, current_user=current_user)
            return schemas.BookingResponse.model_validate(result).model_dump(mode="json")
        if name == "cancel_booking":
            booking_router.cancel_booking(id=args["booking_id"], db=db, current_user=current_user)
            return {"status": "cancelled"}
        if name == "list_my_bookings":
            result = booking_router.list_my_bookings(upcoming=False, db=db, current_user=current_user)
            return {"bookings": [schemas.BookingResponse.model_validate(b).model_dump(mode="json") for b in result]}
        if name == "create_facility":
            anchor = date_type(2000, 1, 1)
            opens_at = datetime.combine(anchor, datetime.strptime(args["opens_at"], "%H:%M").time(), tzinfo=timezone.utc)
            closes_at = datetime.combine(anchor, datetime.strptime(args["closes_at"], "%H:%M").time(), tzinfo=timezone.utc)
            payload = schemas.FacilityCreate(
                name=args["name"], type=args["type"], location=args["location"],
                slot_duration_minutes=args["slot_duration_minutes"],
                opens_at=opens_at, closes_at=closes_at,
                max_advance_days=args["max_advance_days"],
                max_active_bookings_per_user=args["max_active_bookings_per_user"],
                min_cancellation_notice_hours=args["min_cancellation_notice_hours"],
                is_active=True,
            )
            result = facility_router.create_facility(payload, db=db, current_user=current_user)
            data = schemas.FacilityResponse.model_validate(result).model_dump(mode="json")
            data["opens_at"] = result.opens_at.strftime("%H:%M")
            data["closes_at"] = result.closes_at.strftime("%H:%M")
            return data
        if name == "deactivate_facility":
            result = facility_router.update_facility(args["facility_id"], schemas.FacilityUpdate(is_active=False), db=db, current_user=current_user)
            return {"id": result.id, "name": result.name, "is_active": result.is_active}
        if name == "create_closure":
            payload = schemas.ClosureCreate(facility_id=args["facility_id"], start_time=args["start_time"], end_time=args["end_time"], reason=args["reason"])
            result = closure_router.create_closure(payload, force=args.get("force", False), db=db, current_user=current_user)
            return schemas.ClosureResponse.model_validate(result).model_dump(mode="json")
        if name == "delete_closure":
            closure_router.delete_closures(args["closure_id"], db=db, current_user=current_user)
            return {"status": "deleted"}
        return {"error": f"unknown tool {name}"}
    except HTTPException as e:
        return {"error": e.detail}
    except Exception as e:
        db.rollback()
        return {"error": f"Invalid arguments for {name}: {e}"}

@router.post("/chat", response_model=schemas.ChatResponse)
def chat(req: schemas.ChatRequest, db: Session = Depends(get_db), current_user: models.User = Depends(oauth2.get_current_user)):
    client = ollama.Client(host=settings.ollama_host)

    today = datetime.now(timezone.utc).date().isoformat()
    facilities = _run_tool("list_facilities", {}, db, current_user)
    context_prompt = (
        SYSTEM_PROMPT
        + f"\n\nToday's date is {today} (UTC). Resolve relative dates like 'tomorrow', "
        "'next week', or 'this weekend' against this date — never guess or invent a date."
        + "\n\nHere is the current, real list of facilities with their exact ids — use these "
        "ids directly, you do not need to call list_facilities again unless you want to filter "
        f"by type ('court', 'room', or 'equipment'):\n{json.dumps(facilities)}"
        + f"\n\nThe current user's role is '{current_user.role}'."
    )
    messages = [{"role": "system", "content": context_prompt}] + [m.dict() for m in req.messages]

    for _ in range(5):
        response = client.chat(model=settings.ollama_model, messages=messages, tools=TOOLS, options={"temperature": 0})
        msg = response["message"]
        messages.append(msg)

        if not msg.get("tool_calls"):
            leaked = _extract_leaked_tool_call(msg.get("content") or "")
            if leaked:
                name, args = leaked
                result = _run_tool(name, args, db, current_user)
                messages.append({"role": "tool", "content": json.dumps(result)})
                continue
            return schemas.ChatResponse(reply=msg["content"])

        for call in msg["tool_calls"]:
            result = _run_tool(call["function"]["name"], call["function"]["arguments"], db, current_user)
            messages.append({"role": "tool", "content": json.dumps(result)})

    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Assistant did not produce a final reply")