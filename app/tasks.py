from __future__ import annotations

from sqlalchemy.exc import OperationalError

from app.celery_app import celery_app
from app.db import get_session_factory
from app.schemas import WebhookPayload
from app.services.webhooks import process_webhook


@celery_app.task(
    bind=True,
    autoretry_for=(OperationalError,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=5,
)
def retry_webhook_processing(self, payload_data: dict[str, str]) -> dict[str, object]:
    """Retry transient database failures without changing webhook idempotency semantics."""

    session = get_session_factory()()
    try:
        payload = WebhookPayload.model_validate(payload_data)
        receipt = process_webhook(session, payload)
        return receipt.model_dump(mode="json")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
