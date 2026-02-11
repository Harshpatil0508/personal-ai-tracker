from app.cache.redis_client import redis_client

def invalidate_daily_logs_cache(user_id: int):
    keys = redis_client.keys(f"daily_logs:{user_id}:*")
    if keys:
        redis_client.delete(*keys)
