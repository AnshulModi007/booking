from pydantic import BaseModel, EmailStr
from datetime import datetime

class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: str

class TokenData(BaseModel):
    id: str

class RefreshTokenCreate(BaseModel):
    refresh_token: str

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    roll_number: str
    role: str

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    roll_number: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


class FacilityCreate(BaseModel):
    name: str
    type: str
    location: str
    slot_duration_minutes: int
    opens_at: datetime
    closes_at: datetime
    max_advance_days: int
    max_active_bookings_per_user: int
    min_cancellation_notice_hours: int
    is_active: bool


class FacilityResponse(BaseModel):
    id: int
    name: str
    type: str
    location: str
    slot_duration_minutes: int
    opens_at: datetime
    closes_at: datetime
    max_advance_days: int
    max_active_bookings_per_user: int
    min_cancellation_notice_hours: int
    is_active: bool

    class Config:
        from_attributes = True
