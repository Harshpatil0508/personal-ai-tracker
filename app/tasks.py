from calendar import monthrange
from datetime import date, datetime, timezone

import json
import logging
from sqlalchemy import distinct, exists
from app.ai import generate_daily_motivation, generate_monthly_review
from app.celery_app import celery
from app.database import SessionLocal
from app.models import DailyAIMotivation, DailyLog, MonthlyAIReview
from app.vector_store import store_embedding

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# -------- DAILY JOB --------

@celery.task(bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 30})
def daily_job(self):
    """
    Runs every day at midnight.
    Generates daily AI motivation for users based on recent logs.
    """
    logger.info("[DAILY JOB] Starting daily motivation job")
    with SessionLocal() as db:
        try:
            # Fetch users who have daily logs
            users = db.query(distinct(DailyLog.user_id)).all()

            for (user_id,) in users:
                logs = (
                    db.query(DailyLog)
                    .filter(DailyLog.user_id == user_id)
                    .order_by(DailyLog.date.desc())
                    .limit(5)
                    .all()
                )

                if not logs:
                    logger.info(f"[DAILY JOB] No logs for user {user_id}, skipping")
                    continue

                # Check if motivation already exists for today
                exists_today = db.query(DailyAIMotivation).filter(
                        DailyAIMotivation.user_id == user_id,
                        DailyAIMotivation.date == date.today()
                ).first()
                if exists_today:
                    logger.info(f"[DAILY JOB] Motivation already exists for user {user_id}, skipping.")
                    continue
                # Prepare context safely
                goal_completed_yesterday = (
                    logs[0].goal_completed_percentage if logs[0].goal_completed_percentage is not None else 0
                )
                
                context = {
                    "missed_yesterday": goal_completed_yesterday < 100,
                    "avg_mood": round(sum(log.mood_score or 0 for log in logs) / len(logs), 2),
                    "consistency_days": len(logs),
                    "avg_sleep_hours": round(sum(log.sleep_hours or 0 for log in logs) / len(logs), 2),
                    "avg_work_hours": round(sum(log.work_hours or 0 for log in logs) / len(logs), 2),
                    "avg_study_hours": round(sum(log.study_hours or 0 for log in logs) / len(logs), 2),
                }

                # Generate AI motivation
                try:
                    message = generate_daily_motivation(context=context, user_id=user_id)
                except Exception as e:
                    logger.error(f"[DAILY JOB] AI generation failed for user {user_id}: {e}")
                    continue

                # Save motivation
                try:
                    motivation = DailyAIMotivation(
                        user_id=user_id,
                        date=date.today(),
                        message=message
                    )

                    db.add(motivation)
                    db.commit()
                    db.refresh(motivation)

                    try:
                        store_embedding(db=db,user_id=user_id,source="daily_motivation",source_id=motivation.id,content=message,)
                        logger.info(f"[DAILY JOB] Stored embedding for user {user_id}")
                    except Exception as e:
                        logger.warning(f"[DAILY JOB] Failed to store embedding for user {user_id}: {e}")

                    logger.info(f"[DAILY JOB] Saved motivation for user {user_id}")
                except Exception as e:
                    db.rollback()
                    logger.error(f"[DAILY JOB] Failed to save motivation for user {user_id}: {e}")

        except Exception as e:
            logger.error(f"[DAILY JOB] Unexpected error: {e}")
    
    logger.info("[DAILY JOB] Completed daily motivation job")


# -------- MONTHLY AI REVIEW  JOB --------

@celery.task(bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 60})
def monthly_job(self):
    """
    Runs at the start of each month to generate structured AI review for last month.
    """
    logger.info("[MONTHLY AI REVIEW] Starting monthly AI review job")
    with SessionLocal() as db:
        now = datetime.now(timezone.utc)
        current_month_str = now.strftime("%Y-%m")
        year, month = now.year, now.month

        start_date = datetime(year, month, 1).date()
        end_date = datetime(year, month, monthrange(year, month)[1]).date()
        logger.info(f"[MONTHLY AI REVIEW] Processing logs from {start_date} to {end_date}")

        try:
            # Users with logs in the current month only
            users = (
                db.query(DailyLog.user_id)
                .filter(DailyLog.date.between(start_date, end_date))
                .distinct()
                .all()
            )

            for (user_id,) in users:
                logs = (
                    db.query(DailyLog)
                    .filter(
                        DailyLog.user_id == user_id,
                        DailyLog.date.between(start_date, end_date)
                    )
                    .order_by(DailyLog.date)
                    .all()
                )

                if len(logs) < 1:
                    logger.info(f"[MONTHLY AI REVIEW] Skipping user {user_id}, not enough logs ({len(logs)})")
                    continue

                # Check if review already exists
                exists_review = db.query(
                    exists().where(
                        (MonthlyAIReview.user_id == user_id) &
                        (MonthlyAIReview.month == current_month_str)
                    )
                ).scalar()

                if exists_review:
                    logger.info(f"[MONTHLY AI REVIEW] Review already exists for user {user_id}")
                    continue

                # Build timeline safely
                timeline = [
                    {
                        "date": log.date.isoformat(),
                        "work_hours": log.work_hours or 0,
                        "study_hours": log.study_hours or 0,
                        "sleep_hours": log.sleep_hours or 0,
                        "mood_score": log.mood_score or 0,
                        "goal_completion": float(log.goal_completed_percentage or 0),
                    }
                    for log in logs
                ]

                try:
                    # Generate AI review
                    review_dict = generate_monthly_review(
                        summary={
                            "month": current_month_str,
                            "timeline": timeline
                        },
                        user_id=user_id
                    )

                    review_text = (
                        f"Patterns: {review_dict.get('patterns', '')}. "
                        f"Root causes: {review_dict.get('root_causes', '')}. "
                        f"Recommendations: {'; '.join(review_dict.get('recommendations', []))}. "
                        f"Notable: {review_dict.get('notable', '')}."
                    )

                    motivation_monthly = MonthlyAIReview(
                            user_id=user_id,
                            month=current_month_str,
                            content=json.dumps(review_dict, ensure_ascii=False),
                            created_at=datetime.now(timezone.utc)
                        )
                    db.add(motivation_monthly)
                    db.commit()
                    db.refresh(motivation_monthly)

                    try:
                        store_embedding(
                            db=db,
                            user_id=user_id,
                            source="monthly_review",
                            source_id=motivation_monthly.id,
                            content=review_text,
                        )   
                    except Exception as e:
                        logger.warning(
                            f"[MONTHLY JOB] Failed to store embedding for user {user_id}: {e}"
                        )
                    logger.info(f"[MONTHLY AI REVIEW] Generated review for user {user_id}")

                except Exception as e:
                    db.rollback()
                    logger.error(f"[MONTHLY AI REVIEW] Failed for user {user_id}: {e}")
                
        except Exception as e:
            logger.error(f"[MONTHLY AI REVIEW] Unexpected error: {e}")

    logger.info("[MONTHLY AI REVIEW] Completed monthly AI review job")