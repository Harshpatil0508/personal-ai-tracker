"""
REFLECTA — Daily Logs Router
Morning and evening check-ins with silent AI extraction.
"""

import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.models import DailyLog
from app.schemas import MorningLogCreate, EveningLogCreate, DailyLogOut
from app.dependencies import get_current_user_id
from app.database.db import get_db
from app.services.extraction_service import extract_journal_data
from app.services.rag_service import store_memory
from app.services.intervention_checker import run_intervention_checks

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/logs", tags=["Daily Logs"])


# ─── MORNING CHECK-IN ───────────────────────────────────────────
@router.post("/morning")
def submit_morning_log(
    log: MorningLogCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Save morning check-in + trigger silent AI extraction.
    Creates a new DailyLog for today or updates existing.
    """
    today = datetime.today().date()

    existing = db.query(DailyLog).filter(
        DailyLog.user_id == user_id,
        DailyLog.log_date == today,
    ).first()

    if existing and existing.morning_text:
        raise HTTPException(status_code=400, detail="Morning log already submitted for today")

    # Silent AI extraction
    extracted = extract_journal_data(log.morning_text)

    if existing:
        # Evening was submitted first (rare), update existing
        existing.morning_feeling_score = log.morning_feeling_score
        existing.morning_text = log.morning_text
        existing.morning_extracted = extracted
        db.commit()
        db.refresh(existing)
        log_id = existing.id
    else:
        # Create new log for today
        entry = DailyLog(
            user_id=user_id,
            log_date=today,
            morning_feeling_score=log.morning_feeling_score,
            morning_text=log.morning_text,
            morning_extracted=extracted,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        log_id = entry.id

    # Store in vector memory (non-blocking, tolerates failure)
    try:
        store_memory(db, user_id, log.morning_text, "journal")
    except Exception as e:
        logger.warning(f"[MEMORY] Failed to store morning memory: {e}")

    return {
        "message": "Morning check-in saved",
        "id": log_id,
        "extracted": extracted,
    }


# ─── EVENING CHECK-IN ───────────────────────────────────────────
@router.post("/evening")
def submit_evening_log(
    log: EveningLogCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Save evening check-in + trigger silent AI extraction.
    Updates the existing DailyLog for today.
    """
    today = datetime.today().date()

    existing = db.query(DailyLog).filter(
        DailyLog.user_id == user_id,
        DailyLog.log_date == today,
    ).first()

    if existing and existing.evening_text:
        raise HTTPException(status_code=400, detail="Evening log already submitted for today")

    # Silent AI extraction
    extracted = extract_journal_data(log.evening_text)

    if existing:
        # Morning was submitted, update existing
        existing.evening_text = log.evening_text
        existing.evening_extracted = extracted
        existing.day_score = log.day_score
        db.commit()
        db.refresh(existing)
        log_id = existing.id
    else:
        # Create new log (morning was missed)
        entry = DailyLog(
            user_id=user_id,
            log_date=today,
            evening_text=log.evening_text,
            evening_extracted=extracted,
            day_score=log.day_score,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        log_id = entry.id

    # Store in vector memory
    try:
        store_memory(db, user_id, log.evening_text, "journal")
    except Exception as e:
        logger.warning(f"[MEMORY] Failed to store evening memory: {e}")

    # Run wellbeing intervention checks
    interventions = run_intervention_checks(db, user_id)

    return {
        "message": "Evening check-in saved",
        "id": log_id,
        "extracted": extracted,
        "interventions": interventions,
    }


# ─── GET TODAY'S LOG ─────────────────────────────────────────────
@router.get("/today", response_model=DailyLogOut)
def get_today_log(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Get today's full daily log."""
    today = datetime.today().date()

    log = db.query(DailyLog).filter(
        DailyLog.user_id == user_id,
        DailyLog.log_date == today,
    ).first()

    if not log:
        raise HTTPException(status_code=404, detail="No log found for today")

    return log


# ─── GET LOG BY DATE ─────────────────────────────────────────────
@router.get("/by-date/{log_date}", response_model=DailyLogOut)
def get_log_by_date(
    log_date: str,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Get daily log for a specific date."""
    from datetime import date as date_type
    try:
        parsed_date = date_type.fromisoformat(log_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    log = db.query(DailyLog).filter(
        DailyLog.user_id == user_id,
        DailyLog.log_date == parsed_date,
    ).first()

    if not log:
        raise HTTPException(status_code=404, detail=f"No log found for {log_date}")

    return log


# ─── GET LOG HISTORY ─────────────────────────────────────────────
@router.get("/history")
def get_log_history(
    days: int = 30,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Get recent daily logs (default 30 days)."""
    from datetime import timedelta

    start_date = datetime.today().date() - timedelta(days=days)

    logs = (
        db.query(DailyLog)
        .filter(
            DailyLog.user_id == user_id,
            DailyLog.log_date >= start_date,
        )
        .order_by(DailyLog.log_date.desc())
        .all()
    )

    return [
        {
            "id": log.id,
            "log_date": str(log.log_date),
            "morning_feeling_score": log.morning_feeling_score,
            "morning_text": log.morning_text,
            "morning_extracted": log.morning_extracted,
            "evening_text": log.evening_text,
            "evening_extracted": log.evening_extracted,
            "day_score": log.day_score,
        }
        for log in logs
    ]
