"""
REFLECTA — Main Application Entry Point
"The AI that knows you better than you know yourself"
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator

from app.middleware.timing import TimingMiddleware
from app.middleware.throttel import ThrottleMiddleware
from app.logging_config import setup_logging
from app.routers import auth, logs, goals, ai, health, dead_letters, users, analytics, admin

app = FastAPI(
    title="Reflecta",
    description="AI-powered personal life coaching system",
    version="2.0.0",
)

# ─── CORS ────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],  # Vite frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── MIDDLEWARE ──────────────────────────────────────────────────
setup_logging()
app.add_middleware(ThrottleMiddleware)
app.add_middleware(TimingMiddleware)

# ─── ROUTERS ─────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(logs.router)
app.include_router(goals.router)
app.include_router(ai.router)
app.include_router(health.router)
app.include_router(dead_letters.router)
app.include_router(users.router)
app.include_router(analytics.router)
app.include_router(admin.router)
# ─── STATIC FILES ───────────────────────────────────────────────
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# ─── PROMETHEUS ──────────────────────────────────────────────────
Instrumentator().instrument(app).expose(app)
