from __future__ import annotations

import uuid

import jwt
import pytest
from pydantic import ValidationError

from app.auth import create_access_token, hash_password, verify_password
from app.config import get_settings
from app.models import User
from app.schemas import DiagnosticTestCreate, SignupRequest


@pytest.fixture(autouse=True)
def configured_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:password@localhost/eve_booking")
    monkeypatch.setenv(
        "TEST_DATABASE_URL", "postgresql+psycopg://user:password@localhost/eve_booking_test"
    )
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-that-is-at-least-32-chars")
    monkeypatch.setenv("WEBHOOK_SECRET", "test-webhook-secret-that-is-at-least-32-chars")
    monkeypatch.setenv("SEED_STAFF_EMAIL", "staff@example.com")
    monkeypatch.setenv("SEED_STAFF_PASSWORD", "test-local-password")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_passwords_are_hashed_and_verified() -> None:
    password = "example-password-123"
    password_hash = hash_password(password)

    assert password_hash != password
    assert verify_password(password, password_hash)
    assert not verify_password("wrong-password", password_hash)


def test_access_token_has_expected_identity_claims() -> None:
    user = User(id=uuid.uuid4(), email="candidate@example.com", password_hash="not-used")

    token = create_access_token(user)
    payload = jwt.decode(
        token,
        "test-jwt-secret-that-is-at-least-32-chars",
        algorithms=["HS256"],
        audience="eve-booking-client",
        issuer="eve-booking-api",
    )

    assert payload["sub"] == str(user.id)
    assert payload["exp"] > payload["iat"]


def test_public_signup_rejects_role_injection() -> None:
    with pytest.raises(ValidationError):
        SignupRequest.model_validate(
            {"email": "candidate@example.com", "password": "example-password-123", "is_staff": True}
        )


def test_test_code_is_normalized_and_restrictive() -> None:
    assert DiagnosticTestCreate(code="cbc", name="Complete Blood Count").code == "CBC"

    with pytest.raises(ValidationError):
        DiagnosticTestCreate(code="cbc-test", name="Complete Blood Count")
