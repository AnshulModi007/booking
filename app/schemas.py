from pydantic import BaseModel, EmailStr
from datetime import datetime
from datetime import date as data_type
from typing import Literal

FacilityType = Literal["court", "room", "equipment"]

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
    type: FacilityType
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

class FacilityUpdate(BaseModel):
    name: str | None = None
    type: FacilityType | None = None
    location: str | None = None
    slot_duration_minutes: int | None = None
    opens_at: datetime | None = None
    closes_at: datetime | None = None
    max_advance_days: int | None = None
    max_active_bookings_per_user: int | None = None
    min_cancellation_notice_hours: int | None = None
    is_active: bool | None = None

class ClosureCreate(BaseModel):
    facility_id: int
    start_time: datetime
    end_time: datetime
    reason: str

class ClosureResponse(BaseModel):
    id: int
    facility_id: int
    start_time: datetime
    end_time: datetime
    reason:str

    class Config:
        from_attributes = True


class BookingCreate(BaseModel):
    facility_id: int
    start_time: datetime
    end_time: datetime

class BookingResponse(BaseModel):
    id: int
    user_id: int
    facility_id: int
    start_time: datetime
    end_time: datetime
    status: str
    created_at: datetime
    cancelled_at: datetime | None = None

    class Config:
        from_attributes = True


class SlotOut(BaseModel):
    start: datetime
    end: datetime
    available: bool
    reason: str | None=None

class AvailiblityResponse(BaseModel):
    facility_id: int
    date: data_type
    slots: list[SlotOut]

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]

class ChatResponse(BaseModel):
    reply: str
