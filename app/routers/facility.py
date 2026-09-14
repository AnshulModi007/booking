from .. import models, utils, schemas, database, oauth2
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from sqlalchemy.exc import IntegrityError

router =APIRouter(prefix="/facilities", tags=["Facility"])

@router.get("/", response_model=list[schemas.FacilityResponse])
def list_facilities(db: Session=Depends(get_db)):
    return db.query(models.Facility).filter(models.Facility.is_active == True).all()

@router.get("/{id}", response_model=schemas.FacilityResponse)
def get_facility(id: int, db: Session=Depends(get_db)):
    facility=db.query(models.Facility).filter(models.Facility.id == id).first()
    if not facility:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Facility not found")
    return facility

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.FacilityResponse)
def create_facility(facility: schemas.FacilityCreate, db: Session=Depends(get_db), current_user: models.User = Depends(oauth2.require_admin),):
    new_facility=models.Facility(**facility.dict())
    db.add(new_facility)
    db.commit()
    db.refresh(new_facility)
    return new_facility