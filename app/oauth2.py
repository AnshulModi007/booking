from jose import jwt, JWTError
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from .config import settings
from . import models, database, schemas
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import secrets


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

secret_key = settings.jwt_secret_key
algorithm = settings.jwt_algorithm 
access_token_expire_minutes = settings.access_token_expire_minutes

def create_access_token(data: dict):
    expire = datetime.utcnow() + timedelta(minutes=access_token_expire_minutes)
    to_encode=data.copy()
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)
    return encoded_jwt

def verify_token(token: str, credentials_exception):
    try:
        payload=jwt.decode(token, secret_key, algorithms=[algorithm])
        id: str=payload.get("user_id")
        if id is None:
            raise credentials_exception
        token_data= schemas.TokenData(id=str(id))
    except JWTError:
        raise credentials_exception
    return token_data
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(database.get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = verify_token(token, credentials_exception)
    user = db.query(models.User).filter(models.User.id == token.id).first()
    if user is None:
        raise credentials_exception
    return user

def create_refresh_token(user_id: int, db: Session):
    token = secrets.token_urlsafe(32)
    db_token = models.RefreshToken(user_id=user_id, token=token, revoked=False)
    db.add(db_token)
    db.commit()
    return token

def require_admin(current_user: models.User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user