from .database import Base
from sqlalchemy import TIMESTAMP, Boolean, Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

class User(Base):
    __tablename__ = "Users"

    id= Column(Integer, primary_key=True, index=True)
    email= Column(String, unique=True, index=True, nullable=False)
    password= Column(String, nullable=False)
    full_name= Column(String, nullable=False)
    roll_number= Column(String, unique=True, index=True, nullable=False)
    role= Column(String, nullable=False, default="student")
    created_at= Column(TIMESTAMP(timezone=True), nullable=False, server_default="now()")
    bookings = relationship("Booking", back_populates="user")


class Facility(Base):
    __tablename__ = "Facility"

    id= Column(Integer, primary_key=True, index=True)
    name= Column(String, unique=True, index=True, nullable=False)
    type= Column(String, nullable=False)
    location= Column(String, nullable=False)
    slot_duration_minutes= Column(Integer, nullable=False)
    opens_at= Column(TIMESTAMP(timezone=True), nullable=False)
    closes_at= Column(TIMESTAMP(timezone=True), nullable=False)
    max_advance_days= Column(Integer, nullable=False)
    max_active_bookings_per_user= Column(Integer, nullable=False)
    min_cancellation_notice_hours= Column(Integer, nullable=False)
    is_active= Column(Boolean, nullable=False, default=True)
    closures = relationship("Closure", back_populates="facility")   # add
    bookings = relationship("Booking", back_populates="facility")

class Closure(Base):
    __tablename__ = "Closure"

    id= Column(Integer, primary_key=True, index=True)
    facility_id= Column(Integer, ForeignKey("Facility.id"), nullable=False)
    start_time= Column(TIMESTAMP(timezone=True), nullable=False)
    end_time= Column(TIMESTAMP(timezone=True), nullable=False)
    reason= Column(String, nullable=False)

    facility= relationship("Facility", back_populates="closures")


class Booking(Base):
    __tablename__ = "Booking"

    id= Column(Integer, primary_key=True, index=True)
    user_id= Column(Integer, ForeignKey("Users.id"), nullable=False)
    facility_id= Column(Integer, ForeignKey("Facility.id"), nullable=False)
    start_time= Column(TIMESTAMP(timezone=True), nullable=False)
    end_time= Column(TIMESTAMP(timezone=True), nullable=False)
    status= Column(String, nullable=False, default="active")
    created_at= Column(TIMESTAMP(timezone=True), nullable=False, server_default="now()")

    user= relationship("User", back_populates="bookings")
    facility= relationship("Facility", back_populates="bookings")


class RefreshToken(Base):
    __tablename__ = "RefreshToken"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("Users.id"), nullable=False)
    token = Column(String, unique=True, index=True, nullable=False)
    revoked = Column(Boolean, nullable=False, default=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default="now()")   