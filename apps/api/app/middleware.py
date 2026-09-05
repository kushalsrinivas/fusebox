"""Global rate-limit middleware: per API key (or IP) per minute.

Backed by process memory (Redis token bucket in prod). Skips /healthz.
Limit via PIL_RATE_LIMIT (default 1000/min). Test seam: reset().
"""

import os
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

_buckets: dict[str, list[float]] = {}


def reset() -> None:
    _buckets.clear()


def _limit() -> int:
    try:
        return max(int(os.getenv("PIL_RATE_LIMIT", "1000")), 1)
    except ValueError:
        return 1000


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.url.path == "/healthz":
            return await call_next(request)
        key = request.headers.get("x-api-key") or request.headers.get("x-admin-key") \
            or (request.client.host if request.client else "anon")
        now = time.time()
        hits = [t for t in _buckets.get(key, []) if now - t < 60]
        if len(hits) >= _limit():
            return JSONResponse(
                {"detail": {"error": "rate limited", "retry_after_s": 60}},
                status_code=429)
        hits.append(now)
        _buckets[key] = hits
        resp = await call_next(request)
        resp.headers["X-RateLimit-Remaining"] = str(_limit() - len(hits))
        return resp
