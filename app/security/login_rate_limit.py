import redis
from fastapi import HTTPException
from app.config import REDIS_URL

redis_client = redis.from_url(REDIS_URL, decode_responses=True)

MAX_ATTEMPTS_PER_IP = 10
MAX_ATTEMPTS_PER_USER = 5
WINDOW_SECONDS = 15 * 60  # 15 minutes


def _hit(key: str, limit: int):
    count = redis_client.incr(key)
    if count == 1:
        redis_client.expire(key, WINDOW_SECONDS)

    if count > limit:
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Please try again later."
        )


def enforce_login_rate_limit(ip: str, email: str):
    """
    Enforces brute-force protection on login.
    """
    ip_key = f"login_attempts:ip:{ip}"
    user_key = f"login_attempts:user:{email}"

    _hit(ip_key, MAX_ATTEMPTS_PER_IP)
    _hit(user_key, MAX_ATTEMPTS_PER_USER)
