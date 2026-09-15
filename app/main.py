from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import Settings
from . import models
from .database import engine, get_db, sessionLocal, Base
from .routers import user, auth, facility, closure, availiblity

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

@app.get("/")
def read_root():
    return {"status": "server running"}