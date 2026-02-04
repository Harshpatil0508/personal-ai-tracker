import json
from sqlalchemy.orm import Session
from app.cache.redis_client import redis_client
from app.database.models import AIBehaviorProfile

CACHE_TTL = 7 * 86400  # 7 days


def get_behavior_profile_cached(db: Session, user_id: int):
    cache_key = f"behavior_profile:{user_id}"

    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    profile = db.query(AIBehaviorProfile).filter(
        AIBehaviorProfile.user_id == user_id
    ).first()

    if not profile:
        return None

    # Convert SQLAlchemy model → dict
    data = {
        "prefers_encouraging": profile.prefers_encouraging,
        "prefers_actionable": profile.prefers_actionable,
        "avoid_repeating_failed": profile.avoid_repeating_failed,
        "successful_advice": profile.successful_advice,
        "failed_advice": profile.failed_advice,
    }

    redis_client.setex(cache_key, CACHE_TTL, json.dumps(data))
    return data


def invalidate_behavior_profile_cache(user_id: int):
    cache_key = f"behavior_profile:{user_id}"
    redis_client.delete(cache_key)
