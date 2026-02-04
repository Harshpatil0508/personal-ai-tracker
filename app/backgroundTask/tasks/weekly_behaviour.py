import logging
from sqlalchemy import distinct

from app.ai_behavior import update_behavior_profile
from app.backgroundTask.celery_app import celery
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
        user_ids = [
            user_id for (user_id,) in
            db.query(distinct(AIFeedback.user_id)).all()
        ]

    if not user_ids:
        logger.info("[BEHAVIOR DISPATCHER] No users found, skipping dispatch")
        return {"dispatched": 0}

    for user_id in user_ids:
        process_user_behavior_profile.delay(user_id)

    logger.info(f"[BEHAVIOR DISPATCHER] Dispatched {len(user_ids)} user tasks")
    return {"dispatched": len(user_ids)}


@celery.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=1800,  # up to 30 minutes
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def process_user_behavior_profile(self, user_id: int):
    """
    Runs update_behavior_profile for a single user.
    """
    logger.info(f"[BEHAVIOR USER JOB] Start user={user_id}")

    with SessionLocal() as db:
        try:
            update_behavior_profile(db, user_id)

            logger.info(f"[BEHAVIOR USER JOB] Updated profile user={user_id}")
            return {"status": "success", "user_id": user_id}

        except Exception as e:
            db.rollback()

            logger.exception(
                f"[BEHAVIOR USER JOB] HARD FAIL user={user_id} error={str(e)}"
            )

            send_to_dead_letter.delay(
                user_id=user_id,
                source="weekly_behavior_profile",
                error=str(e),
            )

            raise


@celery.task(bind=True)
def send_to_dead_letter(self, user_id: int, source: str, error: str):
    """
    Dead letter handler (future: store in DB + send email)
    """
    logger.critical(
        f"[DLQ] {source} user={user_id} permanently failed → {error}"
    )

    # TODO:
    # 1) Insert into dead_letter table
    # 2) Send async email alert
    return {"status": "stored", "user_id": user_id, "source": source}
