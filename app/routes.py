from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import DailyLog
from app.schemas import DailyLogCreate

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/daily-log/{user_id}")
def create_daily_log(
    user_id: int,
    log: DailyLogCreate,
    db: Session = Depends(get_db)
):
    entry = DailyLog(user_id=user_id, **log.dict())
    db.add(entry)
    db.commit()
    return {"message": "Daily log saved"}
