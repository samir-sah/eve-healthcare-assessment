from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_session
from app.models import User
from app.schemas import PaymentCreate, PaymentRead
from app.services.payments import initiate_payment

router = APIRouter(prefix="/payments", tags=["payments"])
SessionDependency = Annotated[Session, Depends(get_session)]
UserDependency = Annotated[User, Depends(get_current_user)]


@router.post("/", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
def create_payment(
    payload: PaymentCreate,
    response: Response,
    session: SessionDependency,
    current_user: UserDependency,
) -> PaymentRead:
    payment = initiate_payment(session, current_user.id, payload.booking_id)
    if payment.replayed:
        response.status_code = status.HTTP_200_OK
    return payment
