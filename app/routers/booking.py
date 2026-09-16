from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from .. import models, schemas, oauth2
from ..database import get_db

router = APIRouter(prefix="/bookings", tags=["Bookings"])

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.BookingResponse)
def create_booking(booking: schemas.BookingCreate, db: Session = Depends(get_db), current_user: models.User = Depends(oauth2.get_current_user)):
    facility = db.query(models.Facility).filter(models.Facility.id == booking.facility_id).first()
    if not facility or not facility.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Facility not found")

    if booking.end_time <= booking.start_time:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="end_time must be after start_time")

    now = datetime.now(timezone.utc)
    if booking.start_time < now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot book a slot in the past")

    max_date = now.date() + timedelta(days=facility.max_advance_days)
    if booking.start_time.date() > max_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Booking is beyond the allowed advance window")

    active_count = db.query(models.Booking).filter(
        models.Booking.user_id == current_user.id,
        models.Booking.status == "confirmed",
        models.Booking.end_time > now,
    ).count()
    if active_count >= facility.max_active_bookings_per_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Active booking limit reached")

    overlap = db.query(models.Booking).filter(
        models.Booking.facility_id == booking.facility_id,
        models.Booking.status == "confirmed",
        models.Booking.start_time < booking.end_time,
        models.Booking.end_time > booking.start_time,
    ).first()
    if overlap:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slot already booked")

    closure = db.query(models.Closure).filter(
        models.Closure.facility_id == booking.facility_id,
        models.Closure.start_time < booking.end_time,
        models.Closure.end_time > booking.start_time,
    ).first()
    if closure:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Facility closed during this slot")

    new_booking = models.Booking(
        user_id=current_user.id,
        facility_id=booking.facility_id,
        start_time=booking.start_time,
        end_time=booking.end_time,
    )
    db.add(new_booking)
    db.commit()
    db.refresh(new_booking)
    return new_booking


@router.get("/", response_model=list[schemas.BookingResponse])
def list_my_bookings(db: Session = Depends(get_db), current_user: models.User = Depends(oauth2.get_current_user)):
    return db.query(models.Booking).filter(models.Booking.user_id == current_user.id).all()


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_booking(id: int, db: Session = Depends(get_db), current_user: models.User = Depends(oauth2.get_current_user)):
    booking = db.query(models.Booking).filter(models.Booking.id == id).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if booking.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to cancel this booking")
    if booking.status != "confirmed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Booking is not active")

    facility = db.query(models.Facility).filter(models.Facility.id == booking.facility_id).first()
    now = datetime.now(timezone.utc)
    if booking.start_time - now < timedelta(hours=facility.min_cancellation_notice_hours):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cancellation notice period has passed")

    booking.status = "cancelled"
    booking.cancelled_at = now
    db.commit()
