from app.ai_behavior import update_behavior_profile
from app.backgroundTask.celery_app import celery
from sqlalchemy import distinct
import logging
from app.database.database import SessionLocal
from app.database.models import AIFeedback

logger = logging.getLogger(__name__)

@celery.task(bind=True)
def weekly_behavior_profile_dispatcher(self):
    """
    Dispatch per-user behavior profile update tasks.
    """
    logger.info("[BEHAVIOR DISPATCHER] Starting weekly dispatch")

    with SessionLocal() as db:
        user_ids = (
            db.query(distinct(AIFeedback.user_id))
            .all()
        )

    for (user_id,) in user_ids:
        process_user_behavior_profile.delay(user_id)

    logger.info(
        f"[BEHAVIOR DISPATCHER] Dispatched {len(user_ids)} user tasks"
    )

@celery.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=1800,  # up to 30 minutes
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def process_user_behavior_profile(self, user_id: int):

    logger.info(f"[BEHAVIOR USER JOB] Start user={user_id}")

    with SessionLocal() as db:
        try:
            update_behavior_profile(db, user_id)

            logger.info(
                f"[BEHAVIOR USER JOB] Updated profile user={user_id}"
            )

        except Exception as e:
            db.rollback()

            logger.exception(
                f"[BEHAVIOR USER JOB] HARD FAIL user={user_id}"
            )

            send_to_dead_letter.delay(
                user_id=user_id,
                source="weekly_behavior_profile",
                error=str(e),
            )

            raise e

@celery.task
def send_to_dead_letter(user_id, source, error):
    logger.critical(
        f"[DLQ] {source} user={user_id} permanently failed → {error}"
    )
    # insert into dead_letter table
    # email