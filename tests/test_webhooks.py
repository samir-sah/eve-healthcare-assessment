from __future__ import annotations

import hashlib
import hmac
import time
import uuid

import pytest

from app.config import get_settings
from app.errors import ApiError
from app.schemas import WebhookPayload
from app.webhooks import canonical_payload_hash, verify_webhook_signature

WEBHOOK_SECRET = "test-webhook-secret-that-is-at-least-32-chars"


@pytest.fixture(autouse=True)
def configured_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:password@localhost/eve_booking")
    monkeypatch.setenv(
        "TEST_DATABASE_URL", "postgresql+psycopg://user:password@localhost/eve_booking_test"
    )
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-that-is-at-least-32-chars")
    monkeypatch.setenv("WEBHOOK_SECRET", WEBHOOK_SECRET)
    monkeypatch.setenv("SEED_STAFF_EMAIL", "staff@example.com")
    monkeypatch.setenv("SEED_STAFF_PASSWORD", "test-local-password")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def sign(raw_body: bytes, timestamp: str) -> str:
    digest = hmac.new(
        WEBHOOK_SECRET.encode("utf-8"), timestamp.encode("ascii") + b"." + raw_body, hashlib.sha256
    ).hexdigest()
    return f"sha256={digest}"


def test_webhook_signature_covers_timestamp_and_exact_body() -> None:
    raw_body = b'{"event_id":"evt-001"}'
    timestamp = str(int(time.time()))

    verify_webhook_signature(raw_body, timestamp, sign(raw_body, timestamp))

    with pytest.raises(ApiError) as exc_info:
        verify_webhook_signature(raw_body + b" ", timestamp, sign(raw_body, timestamp))
    assert exc_info.value.status_code == 401


def test_webhook_rejects_stale_timestamps() -> None:
    raw_body = b'{"event_id":"evt-001"}'
    stale_timestamp = str(int(time.time()) - 301)

    with pytest.raises(ApiError) as exc_info:
        verify_webhook_signature(raw_body, stale_timestamp, sign(raw_body, stale_timestamp))
    assert exc_info.value.status_code == 401


def test_semantic_fingerprint_ignores_json_key_order() -> None:
    payment_id = uuid.uuid4()
    first = WebhookPayload(event_id="evt-001", payment_id=payment_id, status="SUCCESS")
    second = WebhookPayload.model_validate(
        {"status": "SUCCESS", "payment_id": str(payment_id), "event_id": "evt-001"}
    )

    assert canonical_payload_hash(first) == canonical_payload_hash(second)
