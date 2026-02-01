import time
import redis
from app.config import REDIS_URL

redis_client = redis.from_url(REDIS_URL, decode_responses=True)

FAIL_LIMIT = 5        # failures before opening circuit
COOLDOWN = 60         # seconds


def is_circuit_open(service: str) -> bool:
    failures = int(redis_client.get(f"{service}:failures") or 0)
    last_fail = int(redis_client.get(f"{service}:last_fail") or 0)

    if failures >= FAIL_LIMIT:
        if time.time() - last_fail < COOLDOWN:
            return True
    return False


def record_failure(service: str):
    redis_client.incr(f"{service}:failures")
    redis_client.set(f"{service}:last_fail", int(time.time()))


def record_success(service: str):
    redis_client.delete(f"{service}:failures")
    redis_client.delete(f"{service}:last_fail")
