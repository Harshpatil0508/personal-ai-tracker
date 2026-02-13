import logging
from datetime import datetime, timezone, date

from app.aiEmbeddings.vector_store import store_embedding
from app.backgroundTask.celery_app import celery
from app.database.database import SessionLocal
from app.database.models import DailyLog, DeadLetterTask, MonthlyAIReview
from app.ai import generate_monthly_review
from app.utils.utils import get_user_monthly_window
from celery import Task
from app.cache.ai_output_cache import (
    get_monthly_ai_cache,
    set_monthly_ai_cache,
)

logger = logging.getLogger(__name__)

class MonthlyReviewTask(Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        user_id = args[0]

        logger.critical(
            f"[USER MONTHLY JOB] FINAL FAILURE user={user_id} task_id={task_id} error={exc}"
        )

        send_to_dead_letter.delay(
            user_id=user_id,
            source="monthly_review",
            error=str(exc),
        )

@celery.task(bind=True)
def monthly_job_dispatcher(self):
    """
    Runs monthly.
    Dispatches per-user monthly review tasks.
    """
    logger.info("[MONTHLY JOB] Dispatcher started")

    with SessionLocal() as db:
        user_ids = (
            db.query(DailyLog.user_id)
            .distinct()
            .all()
        )

    for (user_id,) in user_ids:
        process_user_monthly_review.delay(user_id)

    logger.info(f"[MONTHLY JOB] Dispatched {len(user_ids)} user monthly tasks")


@celery.task(
    bind=True,
    base=MonthlyReviewTask,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=1800,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def process_user_monthly_review(self, user_id: int):
    logger.info(f"[MONTHLY USER JOB] Start user={user_id}")

    with SessionLocal() as db:
        try:
            # raise Exception("test failure")
            today = date.today()

            first_log = (
                db.query(DailyLog)
                .filter(DailyLog.user_id == user_id)
                .order_by(DailyLog.date.asc())
                .first()
            )

            if not first_log:
                return

            start_date, end_date, window_label = get_user_monthly_window(
                first_log.date,
                today
            )

            # Check DB first
            exists_review = (
                db.query(MonthlyAIReview)
                .filter(
                    MonthlyAIReview.user_id == user_id,
                    MonthlyAIReview.month == window_label,
                )
                .first()
            )

            if exists_review:
                logger.info(f"[MONTHLY USER JOB] Already exists in DB user={user_id}")
                return

            # Check Redis AI cache
            cached_ai = get_monthly_ai_cache(user_id, window_label)
            if cached_ai:
                logger.info(f"[MONTHLY USER JOB] Redis cache hit user={user_id}")
                ai_output = cached_ai
            else:
                logger.info(f"[MONTHLY USER JOB] Redis cache miss user={user_id}")

                logs = (
                    db.query(DailyLog)
                    .filter(
                        DailyLog.user_id == user_id,
                        DailyLog.date.between(start_date, end_date),
                    )
                    .order_by(DailyLog.date)
                    .all()
                )

                if len(logs) < 5:
                    logger.info(f"[MONTHLY USER JOB] Insufficient logs user={user_id}")
                    return

                timeline = build_monthly_timeline(logs)

                ai_output = safe_generate_monthly_review(
                    user_id=user_id,
                    start_date=start_date,
                    end_date=end_date,
                    timeline=timeline,
                )

                # Store AI output in Redis (40 days)
                set_monthly_ai_cache(user_id, window_label, ai_output)

            # Save DB record
            review = MonthlyAIReview(
                user_id=user_id,
                month=window_label,
                insight=ai_output.get("insight", ""),
                explanation=ai_output.get("explanation", {}),
                created_at=datetime.now(timezone.utc),
            )

            db.add(review)
            db.commit()
            db.refresh(review)

            # Store embedding
            try:
                store_embedding(
                    db=db,
                    user_id=user_id,
                    source="monthly_review",
                    source_id=review.id,
                    content=review.insight,
                )
                logger.info(f"[MONTHLY EMBED] Stored embedding user={user_id}")

            except Exception as e:
                logger.warning(f"[MONTHLY EMBED FAIL] user={user_id}: {e}")

            logger.info(f"[MONTHLY USER JOB] Success user={user_id}")

        except Exception as e:
            db.rollback()
            logger.exception(f"[MONTHLY USER JOB] HARD FAIL user={user_id}")
            raise


def build_monthly_timeline(logs):
    return [
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


def safe_generate_monthly_review(user_id: int, start_date, end_date, timeline):
    try:
        return generate_monthly_review(
            summary={
                "window": f"{start_date} to {end_date}",
                "timeline": timeline,
            },
            user_id=user_id,
        )

    except Exception:
        logger.error(f"[MONTHLY AI FAIL] user={user_id} → fallback used")

        return {
            "insight": (
                "This month showed mixed progress. "
                "Consistency mattered more than intensity."
            ),
            "explanation": {
                "why": [
                    "AI service unavailable",
                    "Fallback summary used",
                ],
                "data_used": ["monthly_timeline"],
                "confidence": 0.3,
                "what_would_change_this": [
                    "More consistent daily logging",
                    "Improved sleep or focus patterns",
                ],
            },
        }


@celery.task
def send_to_dead_letter(user_id: int, source: str, error: str):
    """
    Stores failed Celery tasks into DB for monitoring + debugging.
    """

    logger.critical(f"[DLQ] source={source} user={user_id} error={error}")

    with SessionLocal() as db:
        dlq = DeadLetterTask(
            user_id=user_id,
            source=source,
            error=error,
            status="failed",
            created_at=datetime.now(timezone.utc),
        )

        db.add(dlq)
        db.commit()
