from __future__ import annotations

import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import MockPaymentMode, get_settings
from app.errors import ApiError
from app.models import Booking, BookingStatus, Payment, PaymentStatus
from app.schemas import PaymentRead


def select_mock_outcome() -> PaymentStatus:
    mode = get_settings().mock_payment_mode
    if mode == MockPaymentMode.SUCCESS:
        return PaymentStatus.SUCCESS
    if mode == MockPaymentMode.FAILURE:
        return PaymentStatus.FAILED
    return PaymentStatus.SUCCESS if secrets.randbelow(2) else PaymentStatus.FAILED


def apply_settlement(booking: Booking, payment: Payment, outcome: PaymentStatus) -> None:
    """Apply a permitted payment/booking pair transition without committing."""

    if booking.status == BookingStatus.PENDING and payment.status == PaymentStatus.PENDING:
        payment.status = outcome
        booking.status = (
            BookingStatus.CONFIRMED if outcome == PaymentStatus.SUCCESS else BookingStatus.FAILED
        )
        return

    expected_booking_status = (
        BookingStatus.CONFIRMED if outcome == PaymentStatus.SUCCESS else BookingStatus.FAILED
    )
    if payment.status == outcome and booking.status == expected_booking_status:
        return
    if payment.status in {PaymentStatus.SUCCESS, PaymentStatus.FAILED}:
        raise ApiError(409, "STATE_CONFLICT", "A terminal payment outcome cannot be reversed")
    raise ApiError(500, "INVARIANT_VIOLATION", "Stored booking and payment states are inconsistent")


def serialize_payment(payment: Payment, booking: Booking, replayed: bool) -> PaymentRead:
    return PaymentRead(
        id=payment.id,
        booking_id=payment.booking_id,
        status=payment.status,
        booking_status=booking.status,
        amount=booking.amount,
        currency=booking.currency,
        replayed=replayed,
    )


def initiate_payment(session: Session, user_id: uuid.UUID, booking_id: uuid.UUID) -> PaymentRead:
    booking = session.scalar(
        select(Booking)
        .where(Booking.id == booking_id, Booking.user_id == user_id)
        .options(selectinload(Booking.payment))
        .with_for_update()
    )
    if booking is None:
        raise ApiError(404, "BOOKING_NOT_FOUND", "Booking was not found")

    payment = booking.payment
    if payment is not None:
        if payment.status == PaymentStatus.PENDING:
            raise ApiError(409, "PAYMENT_IN_PROGRESS", "Payment is already processing")
        apply_settlement(booking, payment, PaymentStatus(payment.status))
        return serialize_payment(payment, booking, replayed=True)

    if booking.status != BookingStatus.PENDING:
        raise ApiError(409, "STATE_CONFLICT", "Payment cannot be started for this booking")

    payment = Payment(booking_id=booking.id, provider="mock", status=PaymentStatus.PENDING)
    session.add(payment)
    session.flush()
    apply_settlement(booking, payment, select_mock_outcome())
    session.commit()
    session.refresh(booking)
    session.refresh(payment)
    return serialize_payment(payment, booking, replayed=False)
