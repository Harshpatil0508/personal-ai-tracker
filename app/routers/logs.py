from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date,datetime
from app.models import DailyLog
from app.schemas import DailyLogCreate, DailyLogUpdate
from app.dependencies import get_current_user_id
from app.db import get_db
router = APIRouter(prefix="/daily-logs", tags=["Daily Logs"])

# Create daily log
@router.post("/")
def create_daily_log(
    log: DailyLogCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    today = datetime.today().date()
    print(today)
    exists = db.query(DailyLog).filter(
        DailyLog.user_id == user_id,
        DailyLog.date == today
    ).first()
    print(exists)
    if exists:
        raise HTTPException(
            status_code=400,
            detail="Daily log for today already exists"
        )

    entry = DailyLog(
        user_id=user_id,
        date=today,
        **log.model_dump()
    )

    db.add(entry)
    db.commit()
    db.refresh(entry)

    return {
        "message": "Daily log saved successfully",
        "id": entry.id
    }

# Fetch today's log
@router.get("/today")
def get_daily_log(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    today = datetime.today().date()
    log = db.query(DailyLog).filter(
        DailyLog.user_id == user_id,
        DailyLog.date == today
    ).first()

    if not log:
        raise HTTPException(status_code=400, detail="No daily log found for today")

    return get_daily_log_by_date(today,user_id,db)
 
# Fetch log by date
@router.get("/by-date/{logDate}")
def get_daily_log_by_date(
    logDate: date,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    log = db.query(DailyLog).filter(
        DailyLog.user_id == user_id,
        DailyLog.date == logDate
    ).first()

    if not log:
        raise HTTPException(status_code=400, detail=f"No daily log found for date {logDate}") # Changed detail message to include date

    return log

# Fetch all logs
@router.get("/all-logs")
def get_all_daily_log(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    today = datetime.today().date()
    log = db.query(DailyLog).filter(
        DailyLog.user_id == user_id,
    ).order_by(DailyLog.date.desc()).all()

    if not log:
        raise HTTPException(status_code=400, detail="No logs found for user")

    return log

# Delete today's log
@router.delete("/today")
def delete_daily_log(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    today = datetime.today().date()
    return delete_daily_log_by_date(today,user_id,db)

# Delete log by date
@router.delete("/by-date/{logDate}") # Changed the path to avoid conflict with /all
def delete_daily_log_by_date(
    logDate : date,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    log = db.query(DailyLog).filter(
        DailyLog.user_id == user_id,
        DailyLog.date == logDate
    ).first()

    if not log:
        raise HTTPException(status_code=400, detail="No daily log found for this date")

    db.delete(log)
    db.commit()

    return {"message": "Daily log deleted successfully"}

# Update today's log
@router.patch("/today")
def update_today_log(
    payload: DailyLogUpdate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    today = datetime.today().date()
    return update_log_by_date(today, payload, user_id, db)

# Update log by date
@router.patch("/by-date/{log_date}")
def update_log_by_date(
    log_date: date,
    payload: DailyLogUpdate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    log = db.query(DailyLog).filter(
        DailyLog.user_id == user_id,
        DailyLog.date == log_date
    ).first()

    if not log:
        raise HTTPException(status_code=400, detail="No daily log found for this date")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(log, field, value)

    db.commit()
    db.refresh(log)

    return {
        "message": "Daily log updated successfully",
        "log": log
    }

# Delete all logs
@router.delete("/all-logs")
def delete_all_daily_log(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):

    log = db.query(DailyLog).filter(
        DailyLog.user_id == user_id,
    ).delete()
    
    db.commit()
    
    return {"message": "User's all daily logs deleted"}
