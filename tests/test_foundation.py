from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import Base


def test_schema_has_the_seven_planned_tables() -> None:
    assert set(Base.metadata.tables) == {
        "users",
        "centres",
        "tests",
        "offerings",
        "bookings",
        "payments",
        "webhook_events",
    }


def test_settings_reject_a_test_database_that_matches_the_application_database() -> None:
    values = {
        "DATABASE_URL": "postgresql+psycopg://user:password@localhost/eve_booking",
        "TEST_DATABASE_URL": "postgresql+psycopg://user:password@localhost/eve_booking",
        "JWT_SECRET": "jwt-secret",
        "WEBHOOK_SECRET": "webhook-secret",
        "SEED_STAFF_EMAIL": "staff@example.com",
        "SEED_STAFF_PASSWORD": "local-password",
    }

    try:
        Settings.model_validate(values)
    except ValueError as exc:
        assert "must not be the same" in str(exc)
    else:
        raise AssertionError("unsafe test database configuration was accepted")


def test_openapi_is_available_before_database_configuration() -> None:
    response = TestClient(create_app()).get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "EVE Healthcare Booking API"
