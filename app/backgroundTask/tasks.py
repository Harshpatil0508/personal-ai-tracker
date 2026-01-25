from calendar import monthrange
from datetime import date, datetime, timezone

import json
import logging
from sqlalchemy import distinct, exists, text
from app.ai import generate_daily_motivation, generate_monthly_review
from app.ai_behavior import update_behavior_profile
from app.backgroundTask.celery_app import celery
from app.database.database import SessionLocal
from app.database.models import AIFeedback, AIValidation, DailyAIMotivation, DailyLog, MonthlyAIReview, User
from app.aiEmbeddings.vector_store import store_embedding
from app.utils import get_user_monthly_window
from app.validation import validate_ai_advice

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# -------- DAILY JOB --------

@celery.task(bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 30})
def daily_job(self):
    """
    Runs every day at midnight.
    Generates explainable daily AI motivation for users.
    """
    logger.info("[DAILY JOB] Starting daily motivation job")

    with SessionLocal() as db:
        try:
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
                    continue

                # Check if motivation already exists
                exists_today = (
                    db.query(DailyAIMotivation)
                    .filter(
                        DailyAIMotivation.user_id == user_id,
                        DailyAIMotivation.date == date.today(),
                    )
                    .first()
                )

                if exists_today:
                    continue

                # ---- Build context ----
                goal_completed_yesterday = logs[0].goal_completed_percentage or 0

                context = {
                    "missed_yesterday": goal_completed_yesterday < 100,
                    "consistency_days": len(logs),
                    "avg_mood": round(
                        sum(log.mood_score or 0 for log in logs) / len(logs), 2
                    ),
                    "avg_sleep_hours": round(
                        sum(log.sleep_hours or 0 for log in logs) / len(logs), 2
                    ),
                    "avg_work_hours": round(
                        sum(log.work_hours or 0 for log in logs) / len(logs), 2
                    ),
                    "avg_study_hours": round(
                        sum(log.study_hours or 0 for log in logs) / len(logs), 2
                    ),
                }

                # ---- Generate Explainable AI output ----
                try:
                    ai_output = generate_daily_motivation(
                        context=context,
                        user_id=user_id,
                    )
                except Exception as e:
                    logger.error(
                        f"[DAILY JOB] AI generation failed for user {user_id}: {e}"
                    )
                    continue

                insight = ai_output["insight"]
                explanation = ai_output["explanation"]

                # ---- Persist motivation ----
                try:
                    motivation = DailyAIMotivation(
                        user_id=user_id,
                        date=date.today(),
                        insight=insight,
                        explanation=explanation,
                    )

                    db.add(motivation)
                    db.commit()
                    db.refresh(motivation)

                    # ---- Store embedding (INSIGHT ONLY) ----
                    try:
                        store_embedding(
                            db=db,
                            user_id=user_id,
                            source="daily_motivation",
                            source_id=motivation.id,
                            content=insight,
                        )
                        logger.info(
                            f"[DAILY JOB] Stored embedding for user {user_id}"
                        )
                    except Exception as e:
                        logger.warning(
                            f"[DAILY JOB] Failed to store embedding for user {user_id}: {e}"
                        )

                    logger.info(
                        f"[DAILY JOB] Saved explainable motivation for user {user_id}"
                    )

                except Exception as e:
                    db.rollback()
                    logger.error(
                        f"[DAILY JOB] Failed to save motivation for user {user_id}: {e}"
                    )

        except Exception as e:
            logger.error(f"[DAILY JOB] Unexpected error: {e}")

    logger.info("[DAILY JOB] Completed daily motivation job")



# -------- MONTHLY AI REVIEW  JOB --------

@celery.task(bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 60})
def monthly_job(self):
    """
    Runs monthly.
    Generates explainable AI review based on user-relative monthly windows.
    """
    logger.info("[MONTHLY AI REVIEW] Starting monthly AI review job")

    with SessionLocal() as db:
        today = date.today()

        try:
            # Users who have at least one daily log
            users = (
                db.query(DailyLog.user_id)
                .distinct()
                .all()
            )

            for (user_id,) in users:
                # ---- Get first daily log date ----
                first_log = (
                    db.query(DailyLog)
                    .filter(DailyLog.user_id == user_id)
                    .order_by(DailyLog.date.asc())
                    .first()
                )

                if not first_log:
                    continue

                start_date, end_date, window_label = get_user_monthly_window(
                    first_log.date,
                    today
                )

                logger.info(
                    f"[MONTHLY AI REVIEW] User {user_id} window: {start_date} → {end_date}"
                )

                # ---- Check if review already exists ----
                exists_review = db.query(
                    exists().where(
                        (MonthlyAIReview.user_id == user_id) &
                        (MonthlyAIReview.month == window_label)
                    )
                ).scalar()

                if exists_review:
                    logger.info(
                        f"[MONTHLY AI REVIEW] Review already exists for user {user_id} ({window_label})"
                    )
                    continue

                # ---- Fetch logs for this window ----
                logs = (
                    db.query(DailyLog)
                    .filter(
                        DailyLog.user_id == user_id,
                        DailyLog.date.between(start_date, end_date)
                    )
                    .order_by(DailyLog.date)
                    .all()
                )

                if len(logs) < 5:
                    logger.info(
                        f"[MONTHLY AI REVIEW] Skipping user {user_id}, insufficient logs ({len(logs)})"
                    )
                    continue

                # ---- Build timeline ----
                timeline = [
                    {
                        "date": log.date.isoformat(),
                        "work_hours": log.work_hours or 0,
                        "study_hours": log.study_hours or 0,
                        "sleep_hours": log.sleep_hours or 0,
                        "mood_score": log.mood_score or 0,
                        "goal_completion": float(log.goal_completed_percentage or 0),
                        "is_auto": log.is_auto,
                    }
                    for log in logs
                ]

                try:
                    # ---- Generate Explainable AI Review ----
                    ai_output = generate_monthly_review(
                        summary={
                            "window": f"{start_date} to {end_date}",
                            "timeline": timeline,
                        },
                        user_id=user_id,
                    )

                    review = MonthlyAIReview(
                        user_id=user_id,
                        month=window_label,
                        insight=ai_output["insight"],
                        explanation=ai_output["explanation"],
                        created_at=datetime.now(timezone.utc),
                    )

                    db.add(review)
                    db.commit()

                    # ---- Store embedding (insight only) ----
                    try:
                        store_embedding(
                            db=db,
                            user_id=user_id,
                            source="monthly_review",
                            source_id=review.id,
                            content=ai_output["insight"],
                        )
                    except Exception as e:
                        logger.warning(
                            f"[MONTHLY JOB] Failed to store embedding for user {user_id}: {e}"
                        )

                    logger.info(
                        f"[MONTHLY AI REVIEW] Generated review for user {user_id} ({window_label})"
                    )

                except Exception as e:
                    db.rollback()
                    logger.error(
                        f"[MONTHLY AI REVIEW] Failed for user {user_id}: {e}"
                    )

        except Exception as e:
            logger.error(f"[MONTHLY AI REVIEW] Unexpected error: {e}")

    logger.info("[MONTHLY AI REVIEW] Completed monthly AI review job")

# -------- WEEKLY BEHAVIOR PROFILE JOB --------
@celery.task(bind=True,autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 60})
def weekly_behavior_profile_job(self):
    """
    Runs weekly.
    Updates AIBehaviorProfile for users based on feedback patterns.
    """
    logger.info("[BEHAVIOR JOB] Starting weekly behavior update")

    with SessionLocal() as db:
        # Only users who actually gave feedback
        user_ids = (
            db.query(distinct(AIFeedback.user_id))
            .all()
        )

        for (user_id,) in user_ids:
            try:
                update_behavior_profile(db, user_id)
                logger.info(f"[BEHAVIOR JOB] Updated profile for user {user_id}")
            except Exception as e:
                logger.error(f"[BEHAVIOR JOB] Failed for user {user_id}: {e}")

    logger.info("[BEHAVIOR JOB] Completed weekly behavior update")


@celery.task(bind=True,autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 60})
def auto_fill_daily_logs(self):
    """
    Creates a default DailyLog for users who did not add one today.
    Marks it as system-generated (is_auto=True).
    """
    today = date.today()
    logger.info(f"[AUTO LOG JOB] Starting auto-fill for {today}")

    with SessionLocal() as db:
        users = db.query(User.id).all()

        for (user_id,) in users:
            exists_today = db.query(
                exists().where(
                    (DailyLog.user_id == user_id) &
                    (DailyLog.date == today)
                )
            ).scalar()

            if exists_today:
                logger.info(f"Logs already exist for user {user_id}, skipping.")
                continue

            auto_log = DailyLog(
                user_id=user_id,
                date=today,
                work_hours=0.0,
                study_hours=0.0,
                sleep_hours=None,
                mood_score=None,
                goal_completed_percentage=0.0,
                notes="Auto-generated: no entry for this day",
                is_auto=True,
            )

            try:
                db.add(auto_log)
                db.commit()
                logger.info(f"[AUTO LOG JOB] Created auto log for user {user_id}")
            except Exception as e:
                db.rollback()
                logger.error(
                    f"[AUTO LOG JOB] Failed for user {user_id}: {e}"
                )

    logger.info("[AUTO LOG JOB] Completed auto-fill job")


@celery.task(bind=True)
def validate_daily_ai(self):
    db = SessionLocal()

    motivations = db.execute(text("""
        SELECT id, user_id
        FROM daily_ai_motivation
        WHERE date <= CURRENT_DATE - INTERVAL '7 days'
    """)).fetchall()

    for m in motivations:
        already_validated = (
            db.query(AIValidation)
            .filter_by(
                ai_type="daily_motivation",
                ai_ref_id=m.id,
                metric="mood_score",
            )
            .first()
        )

        if already_validated:
            continue  # ✅ skip safely
        validate_ai_advice(
            user_id=m.user_id,
            ai_type="daily_motivation",
            ai_ref_id=m.id,
            metric="mood_score",
            days_window=7
        )

    db.close()

@celery.task(bind=True)
def validate_monthly_ai(self):
    db = SessionLocal()

    reviews = db.execute("""
        SELECT id, user_id
        FROM monthly_ai_reviews
        WHERE created_at <= CURRENT_DATE - INTERVAL '30 days'
    """).fetchall()

    for r in reviews:
        validate_ai_advice(
            user_id=r.user_id,
            ai_type="monthly_review",
            ai_ref_id=r.id,
            metric="sleep_hours",
            days_window=14
        )

    db.close()
