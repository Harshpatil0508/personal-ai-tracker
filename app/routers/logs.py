import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi import Query
from sqlalchemy import asc, desc, func
from sqlalchemy.orm import Session
from datetime import date,datetime
from app.cache.ai_output_cache import invalidate_daily_ai_cache
from app.cache.daily_logs_cache import invalidate_daily_logs_cache
from app.cache.monthly_analytics_cache import invalidate_monthly_analytics_cache
from app.cache.redis_client import redis_client
from app.database.models import DailyLog
from app.schemas import DailyLogCreate, DailyLogUpdate
from app.dependencies import get_current_user_id
from app.database.db import get_db
from app.security.daily_log_limit import enforce_daily_log_limit


router = APIRouter(prefix="/daily-logs", tags=["Daily Logs"])

# Create daily log
@router.post("/")
def create_daily_log(
    log: DailyLogCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    enforce_daily_log_limit(user_id)
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
    invalidate_daily_logs_cache(user_id)
    # redis_client.delete(f"daily_logs:{user_id}")
    invalidate_daily_ai_cache(user_id, today)
    invalidate_monthly_analytics_cache(user_id, today)

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
    cache_key = f"daily_log:today:{user_id}"
    # Try Redis
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)
    
    today = datetime.today().date()
    log = db.query(DailyLog).filter(
        DailyLog.user_id == user_id,
        DailyLog.date == today
    ).first()

    if not log:
        raise HTTPException(status_code=400, detail="No daily log found for today")
    redis_client.setex(
        cache_key,
        300,
        json.dumps(
            log.__dict__,
            default=str
        )
    )
    return get_daily_log_by_date(today,user_id,db)
 
# Fetch log by date
@router.get("/by-date/{logDate}")
def get_daily_log_by_date(
    logDate: date,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    cache_key = f"daily_log:{logDate}:{user_id}"
    # Try Redis
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    log = db.query(DailyLog).filter(
        DailyLog.user_id == user_id,
        DailyLog.date == logDate
    ).first()

    if not log:
        raise HTTPException(status_code=400, detail=f"No daily log found for date {logDate}") # Changed detail message to include date

    redis_client.setex(
        cache_key,
        300,
        json.dumps(
            log.__dict__,
            default=str
        )
    )
    return log

@router.get("/all-logs")
def get_all_daily_log(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),

    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),

    start_date: date | None = None,
    end_date: date | None = None,

    sort: str = Query("desc", pattern="^(asc|desc)$"),
):
    """
    Paginated logs with optional filtering + sorting.
    Cached for 5 minutes.
    """

    # cache key must include params
    cache_key = f"daily_logs:{user_id}:{limit}:{offset}:{start_date}:{end_date}:{sort}"

    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    query = db.query(DailyLog).filter(DailyLog.user_id == user_id)

    # filtering
    if start_date:
        query = query.filter(DailyLog.date >= start_date)

    if end_date:
        query = query.filter(DailyLog.date <= end_date)

    # total count (for frontend pagination UI)
    total = query.with_entities(func.count()).scalar()

    # sorting
    if sort == "asc":
        query = query.order_by(asc(DailyLog.date))
    else:
        query = query.order_by(desc(DailyLog.date))

    # pagination
    logs = query.offset(offset).limit(limit).all()

    response = {
        "total": total,
        "limit": limit,
        "offset": offset,
        "sort": sort,
        "start_date": str(start_date) if start_date else None,
        "end_date": str(end_date) if end_date else None,
        "data": [
            {
                "id": log.id,
                "date": str(log.date),
                "work_hours": log.work_hours,
                "study_hours": log.study_hours,
                "sleep_hours": log.sleep_hours,
                "mood_score": log.mood_score,
                "goal_completed_percentage": log.goal_completed_percentage,
                "notes": log.notes,
                "is_auto": log.is_auto,
            }
            for log in logs
        ]
    }

    # cache response for 5 minutes
    redis_client.setex(cache_key, 300, json.dumps(response, default=str))

    return response

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
    invalidate_daily_logs_cache(user_id)
    # redis_client.delete(f"daily_logs:{user_id}")


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
    invalidate_daily_logs_cache(user_id)

    # redis_client.delete(f"daily_logs:{user_id}")


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
    invalidate_daily_logs_cache(user_id)
    # redis_client.delete(f"daily_logs:{user_id}")

    
    return {"message": "User's all daily logs deleted"}
