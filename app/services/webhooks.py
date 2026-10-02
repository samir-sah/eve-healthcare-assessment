from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import Booking, Payment, PaymentStatus, WebhookEvent
from app.schemas import WebhookPayload, WebhookReceipt
from app.services.payments import apply_settlement
from app.webhooks import canonical_payload_hash


def process_webhook(session: Session, payload: WebhookPayload) -> WebhookReceipt:
    """Persist one provider receipt and its permitted state change in one transaction."""

    initial_payment = session.get(Payment, payload.payment_id)
    if initial_payment is None:
        raise ApiError(404, "PAYMENT_NOT_FOUND", "Payment was not found")

    booking = session.scalar(
        select(Booking).where(Booking.id == initial_payment.booking_id).with_for_update()
    )
    payment = session.scalar(
        select(Payment).where(Payment.id == payload.payment_id).with_for_update()
    )
    if booking is None or payment is None:
        raise ApiError(500, "INVARIANT_VIOLATION", "Payment is missing its booking")

    payload_hash = canonical_payload_hash(payload)
    event = WebhookEvent(
        provider="mock",
        event_id=payload.event_id,
        payment_id=payment.id,
        outcome=payload.status,
        payload_hash=payload_hash,
    )
    session.add(event)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        existing = session.scalar(
            select(WebhookEvent).where(
                WebhookEvent.provider == "mock", WebhookEvent.event_id == payload.event_id
            )
        )
        if existing is None:
            raise exc
        if existing.payload_hash != payload_hash:
            raise ApiError(
                409, "EVENT_CONFLICT", "Event ID was reused with different content"
            ) from None
        return WebhookReceipt(duplicate=True, event_id=payload.event_id)

    apply_settlement(booking, payment, PaymentStatus(payload.status))
    session.commit()
    return WebhookReceipt(duplicate=False, event_id=payload.event_id)
