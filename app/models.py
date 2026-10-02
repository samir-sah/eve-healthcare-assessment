from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class BookingStatus(StrEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PaymentStatus(StrEnum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_staff: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    bookings: Mapped[list[Booking]] = relationship(back_populates="user")


class Centre(Base):
    __tablename__ = "centres"
    __table_args__ = (
        CheckConstraint("length(btrim(name)) > 0", name="ck_centres_name_nonempty"),
        CheckConstraint("length(btrim(location)) > 0", name="ck_centres_location_nonempty"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    offerings: Mapped[list[Offering]] = relationship(back_populates="centre")


class DiagnosticTest(Base):
    __tablename__ = "tests"
    __table_args__ = (
        UniqueConstraint("code", name="uq_tests_code"),
        CheckConstraint("length(btrim(code)) > 0", name="ck_tests_code_nonempty"),
        CheckConstraint("length(btrim(name)) > 0", name="ck_tests_name_nonempty"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    offerings: Mapped[list[Offering]] = relationship(back_populates="diagnostic_test")


class Offering(Base):
    __tablename__ = "offerings"
    __table_args__ = (
        UniqueConstraint("centre_id", "test_id", name="uq_offerings_centre_test"),
        CheckConstraint("price > 0", name="ck_offerings_price_positive"),
        Index("ix_offerings_centre_id", "centre_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    centre_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("centres.id"), nullable=False)
    test_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tests.id"), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    centre: Mapped[Centre] = relationship(back_populates="offerings")
    diagnostic_test: Mapped[DiagnosticTest] = relationship(back_populates="offerings")
    bookings: Mapped[list[Booking]] = relationship(back_populates="offering")


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_bookings_amount_positive"),
        CheckConstraint(
            "status IN ('PENDING', 'CONFIRMED', 'FAILED', 'CANCELLED')",
            name="ck_bookings_valid_status",
        ),
        Index("ix_bookings_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    offering_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("offerings.id"), nullable=False)
    appointment_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=BookingStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="bookings")
    offering: Mapped[Offering] = relationship(back_populates="bookings")
    payment: Mapped[Payment | None] = relationship(back_populates="booking", uselist=False)


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("booking_id", name="uq_payments_booking"),
        CheckConstraint("provider = 'mock'", name="ck_payments_mock_provider"),
        CheckConstraint(
            "status IN ('PENDING', 'SUCCESS', 'FAILED')", name="ck_payments_valid_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="mock")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=PaymentStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    booking: Mapped[Booking] = relationship(back_populates="payment")
    webhook_events: Mapped[list[WebhookEvent]] = relationship(back_populates="payment")


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="uq_webhook_events_provider_event"),
        CheckConstraint("provider = 'mock'", name="ck_webhook_events_mock_provider"),
        CheckConstraint("outcome IN ('SUCCESS', 'FAILED')", name="ck_webhook_events_valid_outcome"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="mock")
    event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    payment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payments.id"), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    payment: Mapped[Payment] = relationship(back_populates="webhook_events")
