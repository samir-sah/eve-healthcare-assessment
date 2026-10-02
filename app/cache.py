from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

from app.config import get_settings


@lru_cache
def get_redis() -> Redis | None:
    redis_url = get_settings().redis_url
    if not redis_url:
        return None
    try:
        return Redis.from_url(redis_url, decode_responses=True)
    except (RedisError, ValueError):
        return None


class Cache:
    """Best-effort Redis cache; cache outages never block the transactional API."""

    def get_json(self, key: str) -> dict[str, Any] | None:
        client = get_redis()
        if client is None:
            return None
        try:
            value = client.get(key)
            return json.loads(value) if value is not None else None
        except (RedisError, json.JSONDecodeError):
            return None

    def set_json(self, key: str, value: dict[str, Any]) -> None:
        client = get_redis()
        if client is None:
            return
        try:
            client.setex(
                key,
                get_settings().cache_ttl_seconds,
                json.dumps(value, separators=(",", ":")),
            )
        except RedisError:
            return

    def version(self, namespace: str) -> int:
        client = get_redis()
        if client is None:
            return 0
        try:
            value = client.get(f"{namespace}:version")
            return int(value or 0)
        except (RedisError, ValueError):
            return 0

    def invalidate(self, namespace: str) -> None:
        client = get_redis()
        if client is None:
            return
        try:
            client.incr(f"{namespace}:version")
        except RedisError:
            return


cache = Cache()
