from fastapi import APIRouter
from sqlalchemy import text

from app.cache.redis_client import redis_client
from app.database.database import SessionLocal

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/")
def health_check():
    return {"status": "ok"}


@router.get("/redis")
def redis_health():
    try:
        redis_client.ping()
        return {"redis": "ok"}
    except Exception as e:
        return {"redis": "down", "error": str(e)}


@router.get("/db")
def db_health():
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return {"db": "ok"}
    except Exception as e:
        return {"db": "down", "error": str(e)}
