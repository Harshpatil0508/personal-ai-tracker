from fastapi import FastAPI
from app.database import engine, Base
from app.routes import router

# Base.metadata.create_all(bind=engine)

app = FastAPI(title="Personal AI Tracker")

app.include_router(router)
