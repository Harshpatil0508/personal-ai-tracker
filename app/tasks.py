from datetime import datetime

from sqlalchemy import distinct
from app.celery_app import celery
from app.database import SessionLocal
from app.models import DailyLog, MonthlyAnalytics
from app.analytics import generate_monthly_summary


# -------- DAILY JOB --------

@celery.task(bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 30})
def daily_job(self):
    """
    Runs every day at midnight.
    Currently validates daily automation.
    """
    db = SessionLocal()

    try:
        users = db.query(distinct(DailyLog.user_id)).all()

        for user in users:
            user_id = user[0]
            # Future: daily motivation / reminders
            print(f"[DAILY JOB] Processed user {user_id}")

    finally:
        db.close()


# -------- MONTHLY JOB --------

@celery.task(bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 60})
def monthly_job(self):
    """
    Runs on the 1st of every month.
    Generates monthly analytics.
    """
    db = SessionLocal()
    current_month = datetime.today().strftime("%Y-%m")

    try:
        users = db.query(distinct(DailyLog.user_id)).all()

        for user in users:
            user_id = user[0]
            logs = (
                db.query(DailyLog)
                .filter(DailyLog.user_id == user_id)
                .all()
            )

            # Minimum data requirement
            if len(logs) < 7:
                continue

            logs_data = [
                {
                    "work_hours": log.work_hours,
                    "study_hours": log.study_hours,
                    "sleep_hours": log.sleep_hours,
                    "goal_completed": log.goal_completed,
                    "mood_score": log.mood_score,
                }
                for log in logs
            ]

            summary = generate_monthly_summary(logs_data)

            if not summary:
                continue

            exists = (
                db.query(MonthlyAnalytics)
                .filter(
                    MonthlyAnalytics.user_id == user_id,
                    MonthlyAnalytics.month == current_month,
                )
                .first()
            )

            if not exists:
                db.add(
                    MonthlyAnalytics(
                        user_id=user_id,
                        month=current_month,
                        summary=summary,
                    )
                )
                db.commit()

                print(f"[MONTHLY JOB] Analytics generated for user {user.user_id}")

    finally:
        db.close()
