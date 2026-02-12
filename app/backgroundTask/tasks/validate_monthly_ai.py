from datetime import datetime, timezone
from app.backgroundTask.celery_app import celery
from sqlalchemy import text
import logging
from app.database.database import SessionLocal
from app.database.models import AIValidation, DeadLetterTask
from app.validation import validate_ai_advice


logger = logging.getLogger(__name__)

@celery.task(bind=True)
def validate_monthly_ai_dispatcher(self):
    """
    Dispatch validation tasks for monthly AI reviews.
    """
    logger.info("[MONTHLY AI VALIDATION] Dispatcher started")

    with SessionLocal() as db:
        reviews = db.execute(text("""
            SELECT id, user_id
            FROM monthly_ai_reviews
            WHERE created_at <= CURRENT_DATE - INTERVAL '30 days'
        """)).fetchall()

    for r in reviews:
        validate_single_monthly_ai.delay(r.id, r.user_id)

    logger.info(
        f"[MONTHLY AI VALIDATION] Dispatched {len(reviews)} validation tasks"
    )


@celery.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=1800,   # up to 30 minutes
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def validate_single_monthly_ai(self, review_id: int, user_id: int):

    logger.info(
        f"[MONTHLY AI VALIDATION] Start review_id={review_id}"
    )

    with SessionLocal() as db:
        try:
            already_validated = (
                db.query(AIValidation)
                .filter_by(
                    ai_type="monthly_review",
                    ai_ref_id=review_id,
                    metric="sleep_hours",
                )
                .first()
            )

            if already_validated:
                logger.info(
                    f"[MONTHLY AI VALIDATION] Already validated id={review_id}"
                )
                return

            validate_ai_advice(
                user_id=user_id,
                ai_type="monthly_review",
                ai_ref_id=review_id,
                metric="sleep_hours",
                days_window=14,
            )

            logger.info(
                f"[MONTHLY AI VALIDATION] Success id={review_id}"
            )

        except Exception as e:
            db.rollback()

            logger.exception(
                f"[MONTHLY AI VALIDATION] HARD FAIL id={review_id}"
            )

            send_to_dead_letter.delay(
                user_id=user_id,
                source="monthly_ai_validation",
                error=f"id={review_id} | {str(e)}",
            )

            raise e


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
