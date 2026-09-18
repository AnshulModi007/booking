from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from app.config import Settings
from fastapi.staticfiles import StaticFiles
from . import models
from .database import engine, get_db, sessionLocal, Base
from .routers import user, auth, facility, closure, availiblity, booking, assistant

app=FastAPI()

models.Base.metadata.create_all(bind=engine)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user.router)
app.include_router(auth.router)
app.include_router(facility.router)
app.include_router(closure.router)
app.include_router(availiblity.router)
app.include_router(booking.router)
app.include_router(assistant.router)

@app.get("/")
def read_root():
    return RedirectResponse(url="/login.html")

@app.get("/health")
def health():
    return {"return": "ok"}

app.mount("/", StaticFiles(directory="app/static", html=True), name="static")