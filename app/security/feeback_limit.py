import redis
from datetime import date
from fastapi import HTTPException
from app.config import REDIS_URL

redis_client = redis.from_url(REDIS_URL, decode_responses=True)

MAX_FEEDBACK_PER_DAY = 50


def enforce_feedback_limit(user_id: int):
    # Prevent excessive AI feedback requests per user per day
    key = f"ai_feedback_count:{user_id}:{date.today()}"

    count = redis_client.incr(key)

    # First hit : set expiry for the day
    if count == 1:
        redis_client.expire(key, 86400)

    if count > MAX_FEEDBACK_PER_DAY:
        raise HTTPException(
            status_code=429,
            detail="Daily AI feedback limit exceeded. Please try tomorrow."
        )
