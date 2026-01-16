from fastapi import FastAPI
from app.routers import auth, logs, analytics, admin, test, ai_feedback

app = FastAPI()

app.include_router(auth.router)
app.include_router(logs.router)
app.include_router(analytics.router)
app.include_router(admin.router)
app.include_router(test.router)
app.include_router(ai_feedback.router)

