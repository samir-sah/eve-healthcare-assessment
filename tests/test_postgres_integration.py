from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import create_access_token, hash_password
from app.models import (
    Booking,
    BookingStatus,
    Centre,
    DiagnosticTest,
    Offering,
    Payment,
    PaymentStatus,
    User,
    WebhookEvent,
)
from app.schemas import WebhookPayload
from app.services.payments import initiate_payment
from app.services.webhooks import process_webhook

pytestmark = pytest.mark.postgres


def authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def add_staff(session: Session) -> str:
    staff = User(
        email="staff@example.com", password_hash=hash_password("staff-password-123"), is_staff=True
    )
    session.add(staff)
    session.commit()
    return create_access_token(staff)


def sign_webhook(payload: dict[str, str]) -> tuple[bytes, dict[str, str]]:
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    timestamp = str(int(time.time()))
    secret = "test-webhook-secret-that-is-at-least-32-chars"
    digest = hmac.new(
        secret.encode("utf-8"), timestamp.encode("ascii") + b"." + raw_body, hashlib.sha256
    ).hexdigest()
    return raw_body, {
        "Content-Type": "application/json",
        "X-Webhook-Timestamp": timestamp,
        "X-Webhook-Signature": f"sha256={digest}",
    }


def test_auth_catalogue_booking_payment_and_idempotent_webhook(
    client: TestClient, postgres_engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MOCK_PAYMENT_MODE", "success")
    session = Session(postgres_engine)
    staff_token = add_staff(session)
    session.close()

    centre = client.post(
        "/centres/",
        json={"name": "EVE Central", "location": "Koramangala"},
        headers=authorization(staff_token),
    )
    assert centre.status_code == 201
    diagnostic_test = client.post(
        "/tests/",
        json={"code": "cbc", "name": "Complete Blood Count"},
        headers=authorization(staff_token),
    )
    assert diagnostic_test.status_code == 201
    offering = client.post(
        f"/centres/{centre.json()['id']}/tests/",
        json={"test_id": diagnostic_test.json()["id"], "price": "750.00"},
        headers=authorization(staff_token),
    )
    assert offering.status_code == 201

    signup = client.post(
        "/auth/signup/",
        json={"email": "candidate@example.com", "password": "candidate-password-123"},
    )
    assert signup.status_code == 201
    login = client.post(
        "/auth/login/",
        json={"email": "candidate@example.com", "password": "candidate-password-123"},
    )
    token = login.json()["access_token"]
    booking = client.post(
        "/bookings/",
        json={"offering_id": offering.json()["id"], "appointment_at": "2030-01-15T09:30:00Z"},
        headers=authorization(token),
    )
    assert booking.status_code == 201
    assert booking.json()["amount"] == "750.00"

    payment = client.post(
        "/payments/", json={"booking_id": booking.json()["id"]}, headers=authorization(token)
    )
    assert payment.status_code == 201
    assert payment.json()["status"] == "SUCCESS"
    replay = client.post(
        "/payments/", json={"booking_id": booking.json()["id"]}, headers=authorization(token)
    )
    assert replay.status_code == 200
    assert replay.json()["id"] == payment.json()["id"]
    assert replay.json()["replayed"] is True

    webhook_payload = {
        "event_id": "evt-001",
        "payment_id": payment.json()["id"],
        "status": "SUCCESS",
    }
    raw_body, headers = sign_webhook(webhook_payload)
    accepted = client.post("/payments/webhook/", content=raw_body, headers=headers)
    assert accepted.status_code == 200
    assert accepted.json()["duplicate"] is False
    duplicate = client.post("/payments/webhook/", content=raw_body, headers=headers)
    assert duplicate.status_code == 200
    assert duplicate.json()["duplicate"] is True


def test_other_user_cannot_read_an_owned_booking(client: TestClient, postgres_engine) -> None:
    session = Session(postgres_engine)
    owner = User(email="owner@example.com", password_hash=hash_password("owner-password-123"))
    session.add(owner)
    session.commit()
    token = create_access_token(owner)
    session.close()

    response = client.get(f"/bookings/{uuid.uuid4()}/", headers=authorization(token))

    assert response.status_code == 404


def create_pending_booking(postgres_engine) -> tuple[uuid.UUID, uuid.UUID]:
    session = Session(postgres_engine)
    user = User(
        email=f"user-{uuid.uuid4()}@example.com", password_hash=hash_password("user-password-123")
    )
    centre = Centre(name=f"Centre {uuid.uuid4()}", location="Koramangala")
    diagnostic_test = DiagnosticTest(code=f"TEST_{uuid.uuid4().hex[:12].upper()}", name="Test")
    session.add_all([user, centre, diagnostic_test])
    session.flush()
    offering = Offering(centre_id=centre.id, test_id=diagnostic_test.id, price="750.00")
    session.add(offering)
    session.flush()
    booking = Booking(
        user_id=user.id,
        offering_id=offering.id,
        appointment_at=datetime(2030, 1, 15, 9, 30, tzinfo=UTC),
        amount="750.00",
        currency="INR",
        status=BookingStatus.PENDING,
    )
    session.add(booking)
    session.commit()
    user_id, booking_id = user.id, booking.id
    session.close()
    return user_id, booking_id


def test_concurrent_payment_initiation_creates_one_payment(postgres_engine) -> None:
    user_id, booking_id = create_pending_booking(postgres_engine)
    barrier = Barrier(2)

    def initiate() -> tuple[str, bool]:
        with Session(postgres_engine) as session:
            barrier.wait(timeout=5)
            result = initiate_payment(session, user_id, booking_id)
            return str(result.id), result.replayed

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            future.result(timeout=10) for future in [pool.submit(initiate), pool.submit(initiate)]
        ]

    session = Session(postgres_engine)
    count = session.scalar(
        select(func.count()).select_from(Payment).where(Payment.booking_id == booking_id)
    )
    booking = session.get(Booking, booking_id)
    session.close()

    assert {result[0] for result in results} and len({result[0] for result in results}) == 1
    assert sorted(result[1] for result in results) == [False, True]
    assert count == 1
    assert booking.status == BookingStatus.CONFIRMED


def test_concurrent_identical_webhooks_create_one_receipt(postgres_engine) -> None:
    _, booking_id = create_pending_booking(postgres_engine)
    session = Session(postgres_engine)
    payment = Payment(booking_id=booking_id, provider="mock", status=PaymentStatus.PENDING)
    session.add(payment)
    session.commit()
    payment_id = payment.id
    session.close()
    payload = WebhookPayload(event_id="evt-concurrent-001", payment_id=payment_id, status="SUCCESS")
    barrier = Barrier(2)

    def deliver() -> bool:
        with Session(postgres_engine) as worker_session:
            barrier.wait(timeout=5)
            return process_webhook(worker_session, payload).duplicate

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            future.result(timeout=10) for future in [pool.submit(deliver), pool.submit(deliver)]
        ]

    session = Session(postgres_engine)
    event_count = session.scalar(
        select(func.count())
        .select_from(WebhookEvent)
        .where(WebhookEvent.provider == "mock", WebhookEvent.event_id == payload.event_id)
    )
    booking = session.get(Booking, booking_id)
    persisted_payment = session.get(Payment, payment_id)
    session.close()

    assert sorted(results) == [False, True]
    assert event_count == 1
    assert booking.status == BookingStatus.CONFIRMED
    assert persisted_payment.status == PaymentStatus.SUCCESS
