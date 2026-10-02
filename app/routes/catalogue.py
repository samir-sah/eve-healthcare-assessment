from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth import get_current_staff
from app.db import get_session
from app.models import Centre, DiagnosticTest, Offering, User
from app.schemas import (
    CentreCreate,
    CentreDetail,
    CentreRead,
    CentreUpdate,
    DiagnosticTestCreate,
    DiagnosticTestRead,
    OfferingCreate,
    OfferingRead,
    OfferingUpdate,
)
from app.services import catalogue

router = APIRouter(tags=["catalogue"])
SessionDependency = Annotated[Session, Depends(get_session)]
StaffDependency = Annotated[User, Depends(get_current_staff)]


@router.get("/centres/", response_model=list[CentreRead])
def list_centres(session: SessionDependency) -> list[Centre]:
    return catalogue.list_centres(session)


@router.get("/centres/{centre_id}/", response_model=CentreDetail)
def retrieve_centre(centre_id: uuid.UUID, session: SessionDependency) -> Centre:
    return catalogue.get_centre(session, centre_id)


@router.post("/centres/", response_model=CentreRead, status_code=status.HTTP_201_CREATED)
def create_centre(payload: CentreCreate, session: SessionDependency, _: StaffDependency) -> Centre:
    return catalogue.create_centre(session, payload)


@router.patch("/centres/{centre_id}/", response_model=CentreRead)
def patch_centre(
    centre_id: uuid.UUID, payload: CentreUpdate, session: SessionDependency, _: StaffDependency
) -> Centre:
    return catalogue.update_centre(session, centre_id, payload)


@router.get("/tests/", response_model=list[DiagnosticTestRead])
def list_tests(session: SessionDependency) -> list[DiagnosticTest]:
    return catalogue.list_diagnostic_tests(session)


@router.post("/tests/", response_model=DiagnosticTestRead, status_code=status.HTTP_201_CREATED)
def create_test(
    payload: DiagnosticTestCreate, session: SessionDependency, _: StaffDependency
) -> DiagnosticTest:
    return catalogue.create_diagnostic_test(session, payload)


@router.post(
    "/centres/{centre_id}/tests/", response_model=OfferingRead, status_code=status.HTTP_201_CREATED
)
def create_offering(
    centre_id: uuid.UUID, payload: OfferingCreate, session: SessionDependency, _: StaffDependency
) -> Offering:
    return catalogue.create_offering(session, centre_id, payload)


@router.patch("/offerings/{offering_id}/", response_model=OfferingRead)
def patch_offering(
    offering_id: uuid.UUID, payload: OfferingUpdate, session: SessionDependency, _: StaffDependency
) -> Offering:
    return catalogue.update_offering(session, offering_id, payload)
