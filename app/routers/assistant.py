from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import date as date_type
import json
import ollama

from .. import models, schemas, oauth2
from ..database import get_db
from ..config import settings
from . import booking as booking_router, facility as facility_router, availiblity as availability_router

router = APIRouter(prefix="/assistant", tags=["Assistant"])

SYSTEM_PROMPT = (
    "You are a booking assistant for a campus facility booking system. "
    "Always use the tools to look up real facilities, availability, and bookings — "
    "never invent facility IDs, booking IDs, or slot times. "
    "Confirm the facility, date, and time with the user before calling create_booking."
)

TOOLS = [
    {"type": "function", "function": {
        "name": "list_facilities",
        "description": "List active facilities, optionally filtered by type",
        "parameters": {"type": "object", "properties": {
            "type": {"type": "string", "description": "optional facility type filter"}}},
    }},
    {"type": "function", "function": {
        "name": "get_availability",
        "description": "Get available slots for a facility on a date",
        "parameters": {"type": "object", "properties": {
            "facility_id": {"type": "integer"},
            "date": {"type": "string", "description": "YYYY-MM-DD"}},
            "required": ["facility_id", "date"]},
    }},
    {"type": "function", "function": {
        "name": "create_booking",
        "description": "Book a facility slot for the current user",
        "parameters": {"type": "object", "properties": {
            "facility_id": {"type": "integer"},
            "start_time": {"type": "string", "description": "ISO 8601 datetime"},
            "end_time": {"type": "string", "description": "ISO 8601 datetime"}},
            "required": ["facility_id", "start_time", "end_time"]},
    }},
    {"type": "function", "function": {
        "name": "cancel_booking",
        "description": "Cancel one of the current user's bookings",
        "parameters": {"type": "object", "properties": {
            "booking_id": {"type": "integer"}}, "required": ["booking_id"]},
    }},
    {"type": "function", "function": {
        "name": "list_my_bookings",
        "description": "List the current user's own bookings",
        "parameters": {"type": "object", "properties": {}},
    }},
]

def _run_tool(name: str, args: dict, db: Session, current_user: models.User) -> dict:
    try:
        if name == "list_facilities":
            result = facility_router.list_facilities(type=args.get("type"), db=db)
            return {"facilities": [schemas.FacilityResponse.model_validate(f).model_dump(mode="json") for f in result]}
        if name == "get_availability":
            result = availability_router.get_availiblity(id=args["facility_id"], date=date_type.fromisoformat(args["date"]), db=db)
            return result.model_dump(mode="json")
        if name == "create_booking":
            payload = schemas.BookingCreate(**args)
            result = booking_router.create_booking(payload, db=db, current_user=current_user)
            return schemas.BookingResponse.model_validate(result).model_dump(mode="json")
        if name == "cancel_booking":
            booking_router.cancel_booking(id=args["booking_id"], db=db, current_user=current_user)
            return {"status": "cancelled"}
        if name == "list_my_bookings":
            result = booking_router.list_my_bookings(upcoming=False, db=db, current_user=current_user)
            return {"bookings": [schemas.BookingResponse.model_validate(b).model_dump(mode="json") for b in result]}
        return {"error": f"unknown tool {name}"}
    except HTTPException as e:
        return {"error": e.detail}

@router.post("/chat", response_model=schemas.ChatResponse)
def chat(req: schemas.ChatRequest, db: Session = Depends(get_db), current_user: models.User = Depends(oauth2.get_current_user)):
    client = ollama.Client(host=settings.ollama_host)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + [m.dict() for m in req.messages]

    for _ in range(5):
        response = client.chat(model=settings.ollama_model, messages=messages, tools=TOOLS)
        msg = response["message"]
        messages.append(msg)

        if not msg.get("tool_calls"):
            return schemas.ChatResponse(reply=msg["content"])

        for call in msg["tool_calls"]:
            result = _run_tool(call["function"]["name"], call["function"]["arguments"], db, current_user)
            messages.append({"role": "tool", "content": json.dumps(result)})

    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Assistant did not produce a final reply")