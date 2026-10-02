from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import create_access_token, hash_password, normalize_email, verify_password
from app.config import get_settings
from app.db import get_session
from app.errors import ApiError
from app.models import User
from app.schemas import LoginRequest, SignupRequest, TokenResponse, UserRead

router = APIRouter(prefix="/auth", tags=["authentication"])
SessionDependency = Annotated[Session, Depends(get_session)]


@router.post("/signup/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, session: SessionDependency) -> User:
    email = normalize_email(str(payload.email))
    if session.scalar(select(User.id).where(User.email == email)) is not None:
        raise ApiError(409, "EMAIL_EXISTS", "An account with this email already exists")

    user = User(email=email, password_hash=hash_password(payload.password))
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if "uq_users_email" in str(exc.orig):
            raise ApiError(
                409, "EMAIL_EXISTS", "An account with this email already exists"
            ) from None
        raise
    session.refresh(user)
    return user


@router.post("/login/", response_model=TokenResponse)
def login(payload: LoginRequest, session: SessionDependency) -> TokenResponse:
    email = normalize_email(str(payload.email))
    user = session.scalar(select(User).where(User.email == email))
    if (
        user is None
        or not verify_password(payload.password, user.password_hash)
        or not user.is_active
    ):
        raise ApiError(401, "INVALID_CREDENTIALS", "Email or password is incorrect")

    return TokenResponse(
        access_token=create_access_token(user), expires_in=get_settings().jwt_expires_minutes
    )
