import time
import redis
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.config import REDIS_URL

redis_client = redis.from_url(REDIS_URL, decode_responses=True)

MAX_REQUESTS_PER_MIN = 100


class ThrottleMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        user_id = request.headers.get("authorization")

        if not user_id:
            return await call_next(request)

        current_minute = int(time.time() // 60)
        key = f"throttle:{user_id}:{current_minute}"

        count = redis_client.incr(key)
        if count == 1:
            redis_client.expire(key, 60)

        if count > MAX_REQUESTS_PER_MIN:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Slow down."}
            )

        return await call_next(request)
