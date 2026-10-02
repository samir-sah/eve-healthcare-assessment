from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr


class SignupRequest(StrictModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(SignupRequest):
    pass


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class CentreCreate(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    location: str = Field(min_length=1, max_length=255)


class CentreUpdate(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    location: str | None = Field(default=None, min_length=1, max_length=255)

    def has_changes(self) -> bool:
        return self.name is not None or self.location is not None


class DiagnosticTestCreate(StrictModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=120)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        normalized = value.upper()
        if not all(
            character.isupper() or character.isdigit() or character == "_"
            for character in normalized
        ):
            raise ValueError("must contain only uppercase letters, digits, or underscores")
        return normalized


class OfferingCreate(StrictModel):
    test_id: uuid.UUID
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)


class OfferingUpdate(StrictModel):
    price: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    is_active: bool | None = None

    def has_changes(self) -> bool:
        return self.price is not None or self.is_active is not None


class OfferingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    centre_id: uuid.UUID
    test_id: uuid.UUID
    price: Decimal
    currency: str
    is_active: bool


class CentreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    location: str


class CentreDetail(CentreRead):
    offerings: list[OfferingRead]


class DiagnosticTestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
