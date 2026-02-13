from app.backgroundTask.celery_app import celery
from sqlalchemy import text
import logging
from app.database.database import SessionLocal
from app.database.models import AIValidation
from app.validation import validate_ai_advice
from datetime import datetime, timezone
from app.database.models import DeadLetterTask
from celery import Task
logger = logging.getLogger(__name__)

class DailyAIValidationTask(Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        motivation_id = args[0]
        user_id = args[1]

        logger.critical(
            f"[DAILY AI VALIDATION] FINAL FAILURE motivation_id={motivation_id} user={user_id} task_id={task_id} error={exc}"
        )

        if self.request.retries >= self.max_retries:
            send_to_dead_letter.delay(
                user_id=user_id,
                source="daily_ai_validation",
                error=str(exc),
            )

@celery.task(bind=True)
def validate_daily_ai_dispatcher(self):
    """
    Dispatch validation tasks for daily AI motivations.
    """
    logger.info("[DAILY AI VALIDATION] Dispatcher started")

    with SessionLocal() as db:
        motivations = db.execute(text("""
            SELECT id, user_id
            FROM daily_ai_motivation
            WHERE date <= CURRENT_DATE - INTERVAL '7 days'
        """)).fetchall()

    for m in motivations:
        validate_single_daily_ai.delay(m.id, m.user_id)

    logger.info(
        f"[DAILY AI VALIDATION] Dispatched {len(motivations)} validation tasks"
    )

@celery.task(
    bind=True,
    base=DailyAIValidationTask,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=900,   # up to 15 minutes
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def validate_single_daily_ai(self, motivation_id: int, user_id: int):

    logger.info(
        f"[DAILY AI VALIDATION] Start motivation_id={motivation_id}"
    )

    with SessionLocal() as db:
        try:
            # raise Exception("test failure")
            already_validated = (
                db.query(AIValidation)
                .filter_by(
                    ai_type="daily_motivation",
                    ai_ref_id=motivation_id,
                    metric="mood_score",
                )
                .first()
            )

            if already_validated:
                logger.info(
                    f"[DAILY AI VALIDATION] Already validated id={motivation_id}"
                )
                return

            validate_ai_advice(
                user_id=user_id,
                ai_type="daily_motivation",
                ai_ref_id=motivation_id,
                metric="mood_score",
                days_window=7,
            )

            logger.info(
                f"[DAILY AI VALIDATION] Success id={motivation_id}"
            )

        except Exception as e:
            db.rollback()

            logger.exception(
                f"[DAILY AI VALIDATION] HARD FAIL id={motivation_id}"
            )

            raise 

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
