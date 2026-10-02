from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class MockPaymentMode(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    RANDOM = "random"


class Settings(BaseSettings):
    """Validated runtime configuration loaded from environment variables or `.env`."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(validation_alias="DATABASE_URL")
    test_database_url: str = Field(validation_alias="TEST_DATABASE_URL")
    jwt_secret: SecretStr = Field(validation_alias="JWT_SECRET")
    jwt_issuer: str = Field(default="eve-booking-api", validation_alias="JWT_ISSUER")
    jwt_audience: str = Field(default="eve-booking-client", validation_alias="JWT_AUDIENCE")
    jwt_expires_minutes: int = Field(
        default=60, ge=1, le=1_440, validation_alias="JWT_EXPIRES_MINUTES"
    )
    webhook_secret: SecretStr = Field(validation_alias="WEBHOOK_SECRET")
    mock_payment_mode: MockPaymentMode = Field(
        default=MockPaymentMode.SUCCESS, validation_alias="MOCK_PAYMENT_MODE"
    )
    seed_staff_email: str = Field(validation_alias="SEED_STAFF_EMAIL")
    seed_staff_password: SecretStr = Field(validation_alias="SEED_STAFF_PASSWORD")

    @field_validator("database_url", "test_database_url")
    @classmethod
    def require_postgresql(cls, value: str) -> str:
        if not value.startswith("postgresql+"):
            raise ValueError("must use a PostgreSQL SQLAlchemy URL")
        return value

    @field_validator("test_database_url")
    @classmethod
    def require_separate_test_database(cls, value: str, info) -> str:
        if value == info.data.get("database_url"):
            raise ValueError("must not be the same as DATABASE_URL")
        return value


@lru_cache
def get_settings() -> Settings:
    """Create settings lazily so imports do not expose or require local secrets."""

    return Settings()
