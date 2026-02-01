import redis
from fastapi import HTTPException
from app.config import REDIS_URL

redis_client = redis.from_url(REDIS_URL, decode_responses=True)

HOURLY_LIMIT = 3
DAILY_LIMIT = 5
HOUR = 3600
DAY = 86400


def enforce_register_limit(ip: str):
    hourly_key = f"register:hour:{ip}"
    daily_key = f"register:day:{ip}"

    hourly_count = redis_client.incr(hourly_key)
    daily_count = redis_client.incr(daily_key)

    if hourly_count == 1:
        redis_client.expire(hourly_key, HOUR)
    if daily_count == 1:
        redis_client.expire(daily_key, DAY)

    if hourly_count > HOURLY_LIMIT or daily_count > DAILY_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Too many registration attempts. Please try later."
        )
