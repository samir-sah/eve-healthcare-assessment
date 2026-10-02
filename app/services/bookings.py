from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.errors import ApiError
from app.models import Booking, BookingStatus, Offering, Payment
from app.schemas import BookingCreate, BookingRead


def serialize_booking(booking: Booking) -> BookingRead:
    if booking.offering is None:
        raise RuntimeError("Booking response requires its offering")
    return BookingRead(
        id=booking.id,
        user_id=booking.user_id,
        offering_id=booking.offering_id,
        centre_id=booking.offering.centre_id,
        test_id=booking.offering.test_id,
        appointment_at=booking.appointment_at,
        amount=booking.amount,
        currency=booking.currency,
        status=booking.status,
    )


def get_owned_booking(session: Session, user_id: uuid.UUID, booking_id: uuid.UUID) -> Booking:
    booking = session.scalar(
        select(Booking)
        .where(Booking.id == booking_id, Booking.user_id == user_id)
        .options(selectinload(Booking.offering))
    )
    if booking is None:
        raise ApiError(404, "BOOKING_NOT_FOUND", "Booking was not found")
    return booking


def create_booking(session: Session, user_id: uuid.UUID, payload: BookingCreate) -> Booking:
    if payload.appointment_at <= datetime.now(UTC):
        raise ApiError(422, "VALIDATION_ERROR", "Appointment must be in the future")

    offering = session.get(Offering, payload.offering_id)
    if offering is None:
        raise ApiError(404, "OFFERING_NOT_FOUND", "Offering was not found")
    if not offering.is_active:
        raise ApiError(409, "OFFERING_INACTIVE", "Offering is not available for booking")

    booking = Booking(
        user_id=user_id,
        offering_id=offering.id,
        appointment_at=payload.appointment_at,
        amount=offering.price,
        currency=offering.currency,
        status=BookingStatus.PENDING,
    )
    session.add(booking)
    session.commit()
    session.refresh(booking)
    booking.offering = offering
    return booking


def list_owned_bookings(
    session: Session, user_id: uuid.UUID, limit: int, offset: int
) -> tuple[list[Booking], int]:
    bookings = list(
        session.scalars(
            select(Booking)
            .where(Booking.user_id == user_id)
            .options(selectinload(Booking.offering))
            .order_by(Booking.created_at.desc(), Booking.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    total = session.scalar(
        select(func.count()).select_from(Booking).where(Booking.user_id == user_id)
    ) or 0
    return bookings, total


def cancel_booking(session: Session, user_id: uuid.UUID, booking_id: uuid.UUID) -> Booking:
    booking = session.scalar(
        select(Booking)
        .where(Booking.id == booking_id, Booking.user_id == user_id)
        .options(selectinload(Booking.offering))
        .with_for_update()
    )
    if booking is None:
        raise ApiError(404, "BOOKING_NOT_FOUND", "Booking was not found")
    if booking.status == BookingStatus.CANCELLED:
        return booking

    payment = session.scalar(
        select(Payment).where(Payment.booking_id == booking.id).with_for_update()
    )
    if booking.status != BookingStatus.PENDING or payment is not None:
        raise ApiError(
            409, "STATE_CONFLICT", "Booking cannot be cancelled after payment processing"
        )

    booking.status = BookingStatus.CANCELLED
    session.commit()
    session.refresh(booking)
    return booking
