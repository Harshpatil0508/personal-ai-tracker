import json
from datetime import date
from app.cache.redis_client import redis_client

# 30 days cache (monthly analytics rarely change)
CACHE_TTL = 30 * 24 * 60 * 60  # 2592000 seconds


def _cache_key(user_id: int, year: int, month: int) -> str:
    """
    Internal helper to generate redis key.
    """
    return f"monthly_analytics:{user_id}:{year}:{month}"


def get_monthly_analytics_cache(user_id: int, year: int, month: int):
    """
    Fetch monthly analytics from Redis cache.
    Returns dict or None.
    """
    key = _cache_key(user_id, year, month)
    cached = redis_client.get(key)

    if not cached:
        return None

    try:
        return json.loads(cached)
    except json.JSONDecodeError:
        # Corrupt cache safety
        redis_client.delete(key)
        return None


def set_monthly_analytics_cache(
    user_id: int,
    year: int,
    month: int,
    data: dict
):
    """
    Store monthly analytics in Redis.
    """
    key = _cache_key(user_id, year, month)
    redis_client.setex(
        key,
        CACHE_TTL,
        json.dumps(data, default=str)
    )


def invalidate_monthly_analytics_cache(user_id: int, log_date: date):
    """
    Invalidate analytics cache for the month affected by a daily log change.
    """
    key = _cache_key(user_id, log_date.year, log_date.month)
    redis_client.delete(key)


def invalidate_all_monthly_analytics(user_id: int):
    """
    Invalidate ALL monthly analytics caches for a user
    (used when deleting all logs).
    """
    pattern = f"monthly_analytics:{user_id}:*"
    keys = redis_client.keys(pattern)

    if keys:
        redis_client.delete(*keys)
