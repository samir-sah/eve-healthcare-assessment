from __future__ import annotations

from types import SimpleNamespace

from app.cache import Cache
from app.rate_limit import RateLimiter


def test_cache_serializes_values_and_uses_a_version_namespace(monkeypatch) -> None:
    values: dict[str, str] = {}

    class FakeRedis:
        def get(self, key: str):
            return values.get(key)

        def setex(self, key: str, _ttl: int, value: str) -> None:
            values[key] = value

        def incr(self, key: str) -> int:
            values[key] = str(int(values.get(key, "0")) + 1)
            return int(values[key])

    fake_redis = FakeRedis()
    monkeypatch.setattr("app.cache.get_redis", lambda: fake_redis)
    monkeypatch.setattr("app.cache.get_settings", lambda: SimpleNamespace(cache_ttl_seconds=60))
    cache = Cache()

    cache.set_json("catalogue:centres:0:20:0", {"items": [{"name": "EVE"}]})
    assert cache.get_json("catalogue:centres:0:20:0") == {"items": [{"name": "EVE"}]}
    assert cache.version("catalogue") == 0
    cache.invalidate("catalogue")
    assert cache.version("catalogue") == 1


def test_rate_limiter_has_a_process_local_fallback(monkeypatch) -> None:
    monkeypatch.setattr("app.rate_limit.get_redis", lambda: None)
    limiter = RateLimiter()

    assert limiter.consume("rate:login:127.0.0.1", limit=2)[0] is True
    assert limiter.consume("rate:login:127.0.0.1", limit=2)[0] is True
    allowed, retry_after = limiter.consume("rate:login:127.0.0.1", limit=2)

    assert allowed is False
    assert retry_after >= 0
