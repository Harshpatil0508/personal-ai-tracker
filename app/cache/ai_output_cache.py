import json
from datetime import date
from app.cache.redis_client import redis_client


DAILY_TTL = 24 * 60 * 60          # 1 day
MONTHLY_TTL = 40 * 24 * 60 * 60   # 40 days


def daily_ai_key(user_id: int, log_date: date) -> str:
    return f"daily_ai:{user_id}:{log_date.isoformat()}"


def monthly_ai_key(user_id: int, month_key: str) -> str:
    return f"monthly_ai:{user_id}:{month_key}"


# ---------------- DAILY ----------------

def get_daily_ai_cache(user_id: int, log_date: date):
    key = daily_ai_key(user_id, log_date)
    cached = redis_client.get(key)
    if not cached:
        return None
    return json.loads(cached)


def set_daily_ai_cache(user_id: int, log_date: date, data: dict):
    key = daily_ai_key(user_id, log_date)
    redis_client.setex(key, DAILY_TTL, json.dumps(data, default=str))


def invalidate_daily_ai_cache(user_id: int, log_date: date):
    key = daily_ai_key(user_id, log_date)
    redis_client.delete(key)


# ---------------- MONTHLY ----------------

def get_monthly_ai_cache(user_id: int, month_key: str):
    key = monthly_ai_key(user_id, month_key)
    cached = redis_client.get(key)
    if not cached:
        return None
    return json.loads(cached)


def set_monthly_ai_cache(user_id: int, month_key: str, data: dict):
    key = monthly_ai_key(user_id, month_key)
    redis_client.setex(key, MONTHLY_TTL, json.dumps(data, default=str))


def invalidate_monthly_ai_cache(user_id: int, month_key: str):
    key = monthly_ai_key(user_id, month_key)
    redis_client.delete(key)
