from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, date as date_type, timedelta
from .. import models, schemas
from ..database import get_db

router=APIRouter(tags=["Availiblity"])

@router.get("/facilities/{id}/availiblity", response_model=schemas.AvailiblityResponse)
def get_availiblity(id: int, date:date_type, db: Session = Depends(get_db)):
    facility=db.query(models.Facility).filter(models.Facility.id == id).first()
    if not facility:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Facility not found")

    day_start= datetime.combine(date, facility.opens_at.time())
    day_end = datetime.combine(date, facility.closes_at.time())

    bookings=db.query(models.Booking).filter(
        models.Booking.facility_id == id,
        models.Booking.status == "confirmed",
        models.Booking.start_time< day_end,
        models.Booking.end_time > day_start,
    ).all()

    closures=db.query(models.Closure).filter(
        models.Closure.facility_id == id,
        models.Closure.start_time < day_end,
        models.Closure.end_time > day_start,
    ).all()

    now=datetime.now()
    max_date= now.date() + timedelta(days=facility.max_advance_days)

    slots= []
    step = timedelta(minutes=facility.slot_duration_minutes)
    slot_start = day_start
    while slot_start + step <=day_end:
        slot_end=slot_start + step
        available, reason= True, None

        if any(b.start_time < slot_end and b.end_time > slot_start for b in bookings):
            available, reason = False, "booked"
        elif any(c.start_time < slot_end and c.end_time > slot_start for c in closures):
            available, reason = False, "Closure"
        elif slot_start < now:
            available, reason = False, "past"
        elif date > max_date:
            available, reason = False, "beyond_advance_days"

        slots.append(schemas.SlotOut(start=slot_start, end=slot_end, available=available, reason=reason))
        slot_start = slot_end

    return schemas.AvailiblityResponse(facility_id=id, date=date, slots=slots) 