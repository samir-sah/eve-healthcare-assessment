from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.errors import ApiError
from app.models import Booking, BookingStatus, Payment, PaymentStatus
from app.schemas import BookingCreate
from app.services.payments import apply_settlement


def make_pending_pair() -> tuple[Booking, Payment]:
    booking = Booking(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        offering_id=uuid.uuid4(),
        appointment_at=datetime.now(UTC) + timedelta(days=1),
        amount=Decimal("750.00"),
        currency="INR",
        status=BookingStatus.PENDING,
    )
    payment = Payment(id=uuid.uuid4(), booking_id=booking.id, status=PaymentStatus.PENDING)
    return booking, payment


@pytest.mark.parametrize(
    ("outcome", "booking_status"),
    [
        (PaymentStatus.SUCCESS, BookingStatus.CONFIRMED),
        (PaymentStatus.FAILED, BookingStatus.FAILED),
    ],
)
def test_settlement_updates_the_pair_together(
    outcome: PaymentStatus, booking_status: BookingStatus
) -> None:
    booking, payment = make_pending_pair()

    apply_settlement(booking, payment, outcome)

    assert payment.status == outcome
    assert booking.status == booking_status


def test_terminal_payment_cannot_be_reversed() -> None:
    booking, payment = make_pending_pair()
    apply_settlement(booking, payment, PaymentStatus.SUCCESS)

    with pytest.raises(ApiError) as exc_info:
        apply_settlement(booking, payment, PaymentStatus.FAILED)

    assert exc_info.value.status_code == 409
    assert booking.status == BookingStatus.CONFIRMED
    assert payment.status == PaymentStatus.SUCCESS


def test_booking_requires_an_offset_aware_appointment() -> None:
    with pytest.raises(ValidationError):
        BookingCreate(offering_id=uuid.uuid4(), appointment_at="2030-01-15T09:30:00")

    payload = BookingCreate(offering_id=uuid.uuid4(), appointment_at="2030-01-15T15:00:00+05:30")
    assert payload.appointment_at == datetime(2030, 1, 15, 9, 30, tzinfo=UTC)
