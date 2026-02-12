from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from app.middleware.timing import TimingMiddleware
from app.routers import auth, dead_letters, health, logs, analytics, admin, test, ai_feedback,ai_validation
from app.middleware.throttel import ThrottleMiddleware

app = FastAPI()

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

Instrumentator().instrument(app).expose(app)