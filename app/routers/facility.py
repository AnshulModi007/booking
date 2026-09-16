from .. import models, utils, schemas, database, oauth2
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from sqlalchemy.exc import IntegrityError

router =APIRouter(prefix="/facilities", tags=["Facility"])

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

@router.patch("/{id}", response_model=schemas.FacilityResponse)
def update_facility(id: int, facility: schemas.FacilityUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(oauth2.require_admin)):
    db_facility = db.query(models.Facility).filter(models.Facility.id == id).first()
    if not db_facility:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Facility not found")
    for feild, value in facility.dict(exclude_unset=True).items():
        setattr(db_facility, feild, value)
    db.commit()
    db.refresh(db_facility)
    return db_facility

@router.get("/", response_model=list[schemas.FacilityResponse])
def list_facilities(type: str | None = None, db: Session = Depends(get_db)):
    query = db.query(models.Facility).filter(models.Facility.is_active == True)
    if type is not None:
        query = query.filter(models.Facility.type == type)
    return query.all()