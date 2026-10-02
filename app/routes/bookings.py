from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_session
from app.models import User
from app.schemas import BookingCreate, BookingList, BookingRead, PaginationMeta
from app.services import bookings

router = APIRouter(prefix="/bookings", tags=["bookings"])
SessionDependency = Annotated[Session, Depends(get_session)]
UserDependency = Annotated[User, Depends(get_current_user)]


@router.post("/", response_model=BookingRead, status_code=status.HTTP_201_CREATED)
def create_booking(
    payload: BookingCreate, session: SessionDependency, current_user: UserDependency
) -> BookingRead:
    return bookings.serialize_booking(bookings.create_booking(session, current_user.id, payload))


@router.get("/", response_model=BookingList)
def list_bookings(
    session: SessionDependency,
    current_user: UserDependency,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> BookingList:
    booking_page, total = bookings.list_owned_bookings(
        session, current_user.id, limit, offset
    )
    return BookingList(
        items=[
            bookings.serialize_booking(booking)
            for booking in booking_page
        ],
        pagination=PaginationMeta(limit=limit, offset=offset, total=total),
    )


@router.get("/{booking_id}/", response_model=BookingRead)
def retrieve_booking(
    booking_id: uuid.UUID, session: SessionDependency, current_user: UserDependency
) -> BookingRead:
    return bookings.serialize_booking(
        bookings.get_owned_booking(session, current_user.id, booking_id)
    )


@router.post("/{booking_id}/cancel/", response_model=BookingRead)
def cancel_booking(
    booking_id: uuid.UUID, session: SessionDependency, current_user: UserDependency
) -> BookingRead:
    return bookings.serialize_booking(bookings.cancel_booking(session, current_user.id, booking_id))
