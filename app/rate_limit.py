from __future__ import annotations

import time
from collections import defaultdict

from fastapi import Request
from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from app.cache import get_redis
from app.config import get_settings


class RateLimiter:
    def __init__(self) -> None:
        self.local_buckets: dict[str, tuple[int, float]] = defaultdict(lambda: (0, 0.0))

    def consume(self, key: str, limit: int, window_seconds: int = 60) -> tuple[bool, int]:
        redis = get_redis()
        if redis is not None:
            try:
                count = redis.incr(key)
                if count == 1:
                    redis.expire(key, window_seconds)
                ttl = max(redis.ttl(key), 0)
                return count <= limit, ttl
            except RedisError:
                pass

        count, reset_at = self.local_buckets[key]
        now = time.monotonic()
        if now >= reset_at:
            count, reset_at = 0, now + window_seconds
        count += 1
        self.local_buckets[key] = (count, reset_at)
        return count <= limit, max(int(reset_at - now), 0)


limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    protected_paths = {
        "/auth/login/": "login",
        "/auth/signup/": "login",
        "/payments/webhook/": "webhook",
    }

    async def dispatch(self, request: Request, call_next) -> Response:
        category = self.protected_paths.get(request.url.path)
        if category is None:
            return await call_next(request)
        settings = get_settings()
        limit = settings.login_rate_limit if category == "login" else settings.webhook_rate_limit
        client_host = request.client.host if request.client else "unknown"
        allowed, retry_after = limiter.consume(f"rate:{category}:{client_host}", limit)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"error": {"code": "RATE_LIMITED", "message": "Too many requests"}},
                headers={"Retry-After": str(retry_after)},
            )
        return await call_next(request)
