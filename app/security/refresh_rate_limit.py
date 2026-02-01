import redis
from fastapi import HTTPException
from app.config import REDIS_URL

redis_client = redis.from_url(REDIS_URL, decode_responses=True)

MAX_REFRESH_PER_HOUR = 20
WINDOW = 3600


def enforce_refresh_limit(user_id: int):
    key = f"refresh_attempts:{user_id}"

    count = redis_client.incr(key)
    if count == 1:
        redis_client.expire(key, WINDOW)

    if count > MAX_REFRESH_PER_HOUR:
        raise HTTPException(
            status_code=429,
            detail="Too many token refresh attempts. Please log in again."
        )
