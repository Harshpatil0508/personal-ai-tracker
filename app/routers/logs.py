from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date,datetime
from app.models import DailyLog
from app.schemas import DailyLogCreate, DailyLogUpdate
from app.dependencies import get_current_user_id
from app.db import get_db
router = APIRouter(prefix="/daily-logs", tags=["Daily Logs"])


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
 
@router.get("/{logDate}")
def get_daily_log_by_date(
    logDate= date,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    log = db.query(DailyLog).filter(
        DailyLog.user_id == user_id,
        DailyLog.date == logDate
    ).first()

    if not log:
        raise HTTPException(status_code=400, detail="No daily log found for this date: "+logDate)

    return log
    
@router.get("/all")
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

@router.delete("/today")
def delete_daily_log(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    today = datetime.today().date()
    return delete_daily_log_by_date(today,user_id,db)

@router.delete("/{logDate}")
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

@router.patch("/today")
def update_today_log(
    payload: DailyLogUpdate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    today = datetime.today().date()
    return update_log_by_date(today, payload, user_id, db)

@router.patch("/{log_date}")
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

@router.delete("/all")
def delete_all_daily_log(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):

    log = db.query(DailyLog).filter(
        DailyLog.user_id == user_id,
    ).delete()
    
    db.commit()
    
    return {"message": "User's all daily logs deleted"}
