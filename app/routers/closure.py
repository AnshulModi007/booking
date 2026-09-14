from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from .. import models, schemas, oauth2
from ..database import get_db

router=APIRouter(tags=["Closures"])

@router.get("/facilities/{id}/closures", response_model=list[schemas.ClosureResponse])
def list_closures(id: int, db:Session = Depends(get_db)):
    return db.query(models.Closure).filter(models.Closure.facility_id == id, models.Closure.end_time > datetime.now(timezone.utc),).all()

@router.post("/closures", status_code=status.HTTP_201_CREATED, response_model=schemas.ClosureResponse)
def create_closure(closure: schemas.ClosureCreate, db: Session = Depends(get_db), current_user: models.User = Depends(oauth2.require_admin), ):
    new_closure = models.Closure(**closure.dict())
    db.add(new_closure)
    db.commit()
    db.refresh(new_closure)
    return new_closure

@router.delete("/closures/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_closures(id: int, db:Session = Depends(get_db), current_user: models.User = Depends(oauth2.require_admin), ):
    closure = db.query(models.Closure).filter(models.Closure.id == id).first()
    if not closure:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Closure not Found")
    db.delete(closure)
    db.commit()