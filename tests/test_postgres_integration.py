from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import create_access_token, hash_password
from app.models import User

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
