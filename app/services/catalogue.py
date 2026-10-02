from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.errors import ApiError
from app.models import Centre, DiagnosticTest, Offering
from app.schemas import (
    CentreCreate,
    CentreUpdate,
    DiagnosticTestCreate,
    OfferingCreate,
    OfferingUpdate,
)


def create_centre(session: Session, payload: CentreCreate) -> Centre:
    centre = Centre(name=payload.name, location=payload.location)
    session.add(centre)
    session.commit()
    session.refresh(centre)
    return centre


def get_centre(session: Session, centre_id: uuid.UUID) -> Centre:
    centre = session.scalar(
        select(Centre)
        .where(Centre.id == centre_id)
        .options(selectinload(Centre.offerings).selectinload(Offering.diagnostic_test))
    )
    if centre is None:
        raise ApiError(404, "CENTRE_NOT_FOUND", "Centre was not found")
    return centre


def update_centre(session: Session, centre_id: uuid.UUID, payload: CentreUpdate) -> Centre:
    if not payload.has_changes():
        raise ApiError(422, "VALIDATION_ERROR", "At least one field must be provided")
    centre = get_centre(session, centre_id)
    if payload.name is not None:
        centre.name = payload.name
    if payload.location is not None:
        centre.location = payload.location
    session.commit()
    session.refresh(centre)
    return centre


def list_centres(session: Session) -> list[Centre]:
    return list(session.scalars(select(Centre).order_by(Centre.name, Centre.id)))


def create_diagnostic_test(session: Session, payload: DiagnosticTestCreate) -> DiagnosticTest:
    diagnostic_test = DiagnosticTest(code=payload.code, name=payload.name)
    session.add(diagnostic_test)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if "uq_tests_code" in str(exc.orig):
            raise ApiError(
                409, "TEST_CODE_EXISTS", "A test with this code already exists"
            ) from None
        raise
    session.refresh(diagnostic_test)
    return diagnostic_test


def list_diagnostic_tests(session: Session) -> list[DiagnosticTest]:
    return list(session.scalars(select(DiagnosticTest).order_by(DiagnosticTest.code)))


def create_offering(session: Session, centre_id: uuid.UUID, payload: OfferingCreate) -> Offering:
    if session.get(Centre, centre_id) is None:
        raise ApiError(404, "CENTRE_NOT_FOUND", "Centre was not found")
    if session.get(DiagnosticTest, payload.test_id) is None:
        raise ApiError(404, "TEST_NOT_FOUND", "Diagnostic test was not found")

    offering = Offering(centre_id=centre_id, test_id=payload.test_id, price=payload.price)
    session.add(offering)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if "uq_offerings_centre_test" in str(exc.orig):
            raise ApiError(409, "OFFERING_EXISTS", "This centre already offers that test") from None
        raise
    session.refresh(offering)
    return offering


def update_offering(session: Session, offering_id: uuid.UUID, payload: OfferingUpdate) -> Offering:
    if not payload.has_changes():
        raise ApiError(422, "VALIDATION_ERROR", "At least one field must be provided")
    offering = session.get(Offering, offering_id)
    if offering is None:
        raise ApiError(404, "OFFERING_NOT_FOUND", "Offering was not found")
    if payload.price is not None:
        offering.price = payload.price
    if payload.is_active is not None:
        offering.is_active = payload.is_active
    session.commit()
    session.refresh(offering)
    return offering
