import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("request_timing")


class TimingMiddleware(BaseHTTPMiddleware):
    """
    Logs request duration for every API call.
    Useful for debugging performance bottlenecks.
    """

    async def dispatch(self, request, call_next):
        start_time = time.time()

        response = await call_next(request)

        duration_ms = round((time.time() - start_time) * 1000, 2)

        logger.info(
            "request completed",
            extra={
                "path": request.url.path,
                "method": request.method,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )

        return response
