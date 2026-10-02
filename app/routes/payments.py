from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_session
from app.errors import ApiError
from app.models import User
from app.schemas import PaymentCreate, PaymentRead, WebhookPayload, WebhookReceipt
from app.services.payments import initiate_payment
from app.services.webhooks import process_webhook
from app.webhooks import MAX_WEBHOOK_BODY_BYTES, verify_webhook_signature

router = APIRouter(prefix="/payments", tags=["payments"])
SessionDependency = Annotated[Session, Depends(get_session)]
UserDependency = Annotated[User, Depends(get_current_user)]


@router.post("/", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
def create_payment(
    payload: PaymentCreate,
    response: Response,
    session: SessionDependency,
    current_user: UserDependency,
) -> PaymentRead:
    payment = initiate_payment(session, current_user.id, payload.booking_id)
    if payment.replayed:
        response.status_code = status.HTTP_200_OK
    return payment


@router.post("/webhook/", response_model=WebhookReceipt)
async def receive_webhook(
    request: Request, response: Response, session: SessionDependency
) -> WebhookReceipt:
    raw_body = await request.body()
    if len(raw_body) > MAX_WEBHOOK_BODY_BYTES:
        raise ApiError(413, "PAYLOAD_TOO_LARGE", "Webhook payload is too large")

    verify_webhook_signature(
        raw_body,
        request.headers.get("X-Webhook-Timestamp"),
        request.headers.get("X-Webhook-Signature"),
    )
    try:
        payload = WebhookPayload.model_validate_json(raw_body)
    except ValidationError:
        raise ApiError(422, "VALIDATION_ERROR", "Webhook payload is invalid") from None

    try:
        return process_webhook(session, payload)
    except OperationalError:
        session.rollback()
        try:
            from app.tasks import retry_webhook_processing

            retry_webhook_processing.delay(payload.model_dump(mode="json"))
        except Exception:
            raise ApiError(
                503,
                "WEBHOOK_RETRY_UNAVAILABLE",
                "Webhook processing is temporarily unavailable",
            ) from None
        response.status_code = status.HTTP_202_ACCEPTED
        return WebhookReceipt(duplicate=False, event_id=payload.event_id, queued=True)
