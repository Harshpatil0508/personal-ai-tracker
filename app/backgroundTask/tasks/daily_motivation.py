import logging
from datetime import date
from sqlalchemy import distinct
from celery.signals import task_failure

from app.backgroundTask.celery_app import celery
from app.ai import generate_daily_motivation
from app.aiEmbeddings.vector_store import store_embedding
from app.database.database import SessionLocal
from app.database.models import DailyAIMotivation, DailyLog

from app.cache.ai_output_cache import (
    get_daily_ai_cache,
    set_daily_ai_cache,
)

logger = logging.getLogger(__name__)


@celery.task(bind=True)
def daily_job_dispatcher(self):
    """
    Runs daily.
    Dispatches one task per user.
    """
    logger.info("[DAILY JOB] Dispatcher started")

    with SessionLocal() as db:
        user_ids = db.query(distinct(DailyLog.user_id)).all()

    for (user_id,) in user_ids:
        process_user_daily_motivation.delay(user_id)

    logger.info(f"[DAILY JOB] Dispatched {len(user_ids)} user tasks")


@celery.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def process_user_daily_motivation(self, user_id: int):
    logger.info(f"[USER DAILY JOB] Start user={user_id}")

    today = date.today()

    with SessionLocal() as db:
        try:
            # Check DB if already exists
            exists_today = (
                db.query(DailyAIMotivation)
                .filter(
                    DailyAIMotivation.user_id == user_id,
                    DailyAIMotivation.date == today,
                )
                .first()
            )

            if exists_today:
                logger.info(f"[USER DAILY JOB] Already exists in DB user={user_id}")
                return

            # Check Redis AI output cache
            cached_ai = get_daily_ai_cache(user_id, today)
            if cached_ai:
                logger.info(f"[USER DAILY JOB] Redis cache hit user={user_id}")
                ai_output = cached_ai
            else:
                logger.info(f"[USER DAILY JOB] Redis cache miss user={user_id}")

                logs = (
                    db.query(DailyLog)
                    .filter(DailyLog.user_id == user_id)
                    .order_by(DailyLog.date.desc())
                    .limit(5)
                    .all()
                )

                if not logs:
                    logger.warning(f"[USER DAILY JOB] No logs user={user_id}")
                    return

                context = build_context(logs)

                ai_output = safe_generate_ai(context, user_id)

                # Store AI output in Redis for 24h
                set_daily_ai_cache(user_id, today, ai_output)

            # Save in DB + store embedding
            save_motivation_and_embedding(db, user_id, ai_output, today)

            logger.info(f"[USER DAILY JOB] Success user={user_id}")

        except Exception as e:
            db.rollback()
            logger.exception(f"[USER DAILY JOB] HARD FAIL user={user_id}")

            send_to_dead_letter.delay(user_id, str(e))
            raise


def build_context(logs):
    return {
        "missed_yesterday": (logs[0].goal_completed_percentage or 0) < 100,
        "consistency_days": len(logs),
        "avg_mood": round(sum(l.mood_score or 0 for l in logs) / len(logs), 2),
        "avg_sleep_hours": round(sum(l.sleep_hours or 0 for l in logs) / len(logs), 2),
        "avg_work_hours": round(sum(l.work_hours or 0 for l in logs) / len(logs), 2),
        "avg_study_hours": round(sum(l.study_hours or 0 for l in logs) / len(logs), 2),
    }


def safe_generate_ai(context, user_id):
    try:
        return generate_daily_motivation(
            context=context,
            user_id=user_id,
        )
    except Exception:
        logger.error(f"[DAILY AI FAIL] user={user_id} → fallback used")

        return {
            "insight": fallback_motivation(context),
            "explanation": {
                "why": ["AI service unavailable"],
                "data_used": list(context.keys()),
                "confidence": 0.3,
                "what_would_change_this": [
                    "More consistent daily logs",
                    "More feedback on AI advice"
                ]
            },
        }


def fallback_motivation(context):
    if context["missed_yesterday"]:
        return "Yesterday slipped — today is your reset. Show up and execute."

    if context["consistency_days"] >= 5:
        return "Consistency beats intensity. Stay steady and win the day."

    if context["avg_sleep_hours"] < 6:
        return "Better sleep tonight — strong days are built on strong rest."

    if context["avg_study_hours"] < 2:
        return "Small focused study blocks today will compound fast."

    return "Do the important work first. Discipline before motivation."


def save_motivation_and_embedding(db, user_id, ai_output, today):
    motivation = DailyAIMotivation(
        user_id=user_id,
        date=today,
        insight=ai_output.get("insight", ""),
        explanation=ai_output.get("explanation", {}),
    )

    db.add(motivation)
    db.commit()
    db.refresh(motivation)

    try:
        store_embedding(
            db=db,
            user_id=user_id,
            source="daily_motivation",
            source_id=motivation.id,
            content=motivation.insight,
        )
        logger.info(f"[DAILY EMBED] Stored embedding user={user_id}")

    except Exception as e:
        logger.warning(f"[DAILY EMBED FAIL] user={user_id}: {e}")


@celery.task
def send_to_dead_letter(user_id, error):
    logger.critical(f"[DAILY DEAD LETTER] user={user_id} permanently failed → {error}")


@task_failure.connect
def celery_failure_alert(**kwargs):
    logger.critical(f"[CELERY FAILURE SIGNAL] {kwargs}")
