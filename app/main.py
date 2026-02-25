from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from app.middleware.timing import TimingMiddleware
from app.routers import auth, daily_ai_motivation, dead_letters, health, logs, analytics, admin, test, ai_feedback,ai_validation, users
from app.middleware.throttel import ThrottleMiddleware
from app.logging_config import setup_logging
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI(title="Personal Tracker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],  # Vite frontend
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods including OPTIONS
    allow_headers=["*"],  # Allow all headers
)


setup_logging()

app.add_middleware(ThrottleMiddleware)
app.add_middleware(TimingMiddleware)

app.include_router(auth.router)
app.include_router(logs.router)
app.include_router(analytics.router)
app.include_router(admin.router)
app.include_router(test.router)
app.include_router(ai_feedback.router)
app.include_router(ai_validation.router)
app.include_router(health.router)
app.include_router(dead_letters.router)
app.include_router(users.router)
app.include_router(daily_ai_motivation.router)

from fastapi.staticfiles import StaticFiles
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


Instrumentator().instrument(app).expose(app)

