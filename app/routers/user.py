from .. import models, utils, schemas, database, oauth2
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from sqlalchemy.exc import IntegrityError
from ..config import settings

router=APIRouter(prefix="/users", tags=["Users"])

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.UserResponse)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    if not user.email.endswith(f"@{settings.institute_email_domain}"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Must register with an institute email")
    existing = db.query(models.User).filter(models.User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this email already exists")
    existing_roll = db.query(models.User).filter(models.User.roll_number == user.roll_number).first()
    if existing_roll:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this roll number already exists")

    hashed_password = utils.password_hash(user.password)
    # public self-registration must never grant a role the caller chooses —
    # every new account starts as a student; promotion to admin happens
    # out-of-band (see README/CLAUDE notes), never via this open endpoint.
    new_user = models.User(email=user.email, password=hashed_password, full_name=user.full_name, roll_number=user.roll_number, role="student")
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this email or roll number already exists")
    db.refresh(new_user)
    return new_user

@router.get('/', response_model=list[schemas.UserResponse])
def get_users(db: Session = Depends(get_db), current_user: models.User = Depends(oauth2.get_current_user)):
    return db.query(models.User).all()

@router.get('/{id}', response_model=schemas.UserResponse)
def get_user(id: int, db: Session = Depends(get_db), current_user: models.User = Depends(oauth2.get_current_user)):
    user = db.query(models.User).filter(models.User.id == id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with id {id} not found")
    if user.id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to access this user")
    return user

