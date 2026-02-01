import redis
from datetime import date
from app.config import REDIS_URL

redis_client = redis.from_url(REDIS_URL, decode_responses=True)

MAX_LOGS_PER_DAY = 10


def enforce_daily_log_limit(user_id: int):
    key = f"daily_log_limit:{user_id}:{date.today()}"
    count = redis_client.incr(key)

    if count == 1:
        redis_client.expire(key, 86400)

    if count > MAX_LOGS_PER_DAY:
        raise Exception("Daily log limit exceeded (10/day)")
