from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from .. import schemas, database, models, oauth2, utils
from fastapi.security import OAuth2PasswordRequestForm

router=APIRouter(tags=["Authentication"])

@router.post("/login", response_model=schemas.Token)
def login(user_credentials: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    db_user = db.query(models.User).filter(models.User.email == user_credentials.username).first()
    if not db_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Credentials")
    
    if not utils.password_verify(user_credentials.password, db_user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Credentials")


    access_token = oauth2.create_access_token(data={"user_id": db_user.id})
    refresh_token = oauth2.create_refresh_token(user_id=db_user.id, db=db)
    return {"access_token": access_token, "token_type": "bearer", "refresh_token": refresh_token}
@router.post("/refresh", response_model=schemas.Token)
def refresh_token(refresh_token: schemas.RefreshTokenCreate, db: Session = Depends(database.get_db)):
    # Verify the refresh token
    try:
        payload = oauth2.jwt.decode(refresh_token.refresh_token, oauth2.secret_key, algorithms=[oauth2.algorithm])
        user_id: str = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    except oauth2.JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    # Check if the refresh token exists in the database and is not revoked
    db_refresh_token = db.query(models.RefreshToken).filter(models.RefreshToken.token == refresh_token.refresh_token).first()
    if not db_refresh_token or db_refresh_token.revoked:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked refresh token")

    # Create a new access token
    new_access_token = oauth2.create_access_token(data={"user_id": user_id})
    return {"access_token": new_access_token, "token_type": "bearer"}

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(refresh_token: schemas.RefreshTokenCreate, db: Session = Depends(database.get_db)):
    # Verify the refresh token
    try:
        payload = oauth2.jwt.decode(refresh_token.refresh_token, oauth2.secret_key, algorithms=[oauth2.algorithm])
        user_id: str = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    except oauth2.JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    # Check if the refresh token exists in the database and is not revoked
    db_refresh_token = db.query(models.RefreshToken).filter(models.RefreshToken.token == refresh_token.refresh_token).first()
    if not db_refresh_token or db_refresh_token.revoked:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked refresh token")

    # Revoke the refresh token
    db_refresh_token.revoked = True
    db.commit()

@router.get("/auth/me", response_model=schemas.UserResponse)
def get_me(current_user: models.User = Depends(oauth2.get_current_user)):
    return current_user


