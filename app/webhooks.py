from __future__ import annotations

import hashlib
import hmac
import json
import re
import time

from app.config import get_settings
from app.errors import ApiError
from app.schemas import WebhookPayload

MAX_WEBHOOK_BODY_BYTES = 16 * 1024
WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS = 300


def verify_webhook_signature(raw_body: bytes, timestamp: str | None, signature: str | None) -> None:
    if timestamp is None or signature is None or not re.fullmatch(r"\d+", timestamp):
        raise ApiError(401, "INVALID_WEBHOOK_SIGNATURE", "Webhook authentication is invalid")
    if not re.fullmatch(r"sha256=[0-9a-f]{64}", signature):
        raise ApiError(401, "INVALID_WEBHOOK_SIGNATURE", "Webhook authentication is invalid")

    timestamp_value = int(timestamp)
    if abs(time.time() - timestamp_value) > WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS:
        raise ApiError(401, "INVALID_WEBHOOK_SIGNATURE", "Webhook authentication is invalid")

    signed_bytes = timestamp.encode("ascii") + b"." + raw_body
    expected = hmac.new(
        get_settings().webhook_secret.get_secret_value().encode("utf-8"),
        signed_bytes,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, f"sha256={expected}"):
        raise ApiError(401, "INVALID_WEBHOOK_SIGNATURE", "Webhook authentication is invalid")


def canonical_payload_hash(payload: WebhookPayload) -> str:
    canonical = json.dumps(
        {
            "event_id": payload.event_id,
            "payment_id": str(payload.payment_id),
            "provider": "mock",
            "status": payload.status,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
