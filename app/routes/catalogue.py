from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth import get_current_staff
from app.cache import cache
from app.db import get_session
from app.models import Centre, DiagnosticTest, Offering, User
from app.schemas import (
    CentreCreate,
    CentreDetail,
    CentreList,
    CentreRead,
    CentreUpdate,
    DiagnosticTestCreate,
    DiagnosticTestList,
    DiagnosticTestRead,
    OfferingCreate,
    OfferingRead,
    OfferingUpdate,
    PaginationMeta,
)
from app.services import catalogue

router = APIRouter(tags=["catalogue"])
SessionDependency = Annotated[Session, Depends(get_session)]
StaffDependency = Annotated[User, Depends(get_current_staff)]


@router.get("/centres/", response_model=CentreList)
def list_centres(
    session: SessionDependency,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> CentreList:
    key = f"catalogue:centres:{cache.version('catalogue')}:{limit}:{offset}"
    cached = cache.get_json(key)
    if cached is not None:
        return CentreList.model_validate(cached)

    centres, total = catalogue.list_centres(session, limit, offset)
    response = CentreList(
        items=centres, pagination=PaginationMeta(limit=limit, offset=offset, total=total)
    )
    cache.set_json(key, response.model_dump(mode="json"))
    return response


@router.get("/centres/{centre_id}/", response_model=CentreDetail)
def retrieve_centre(centre_id: uuid.UUID, session: SessionDependency) -> CentreDetail:
    key = f"catalogue:centre:{cache.version('catalogue')}:{centre_id}"
    cached = cache.get_json(key)
    if cached is not None:
        return CentreDetail.model_validate(cached)

    centre = catalogue.get_centre(session, centre_id)
    response = CentreDetail.model_validate(centre)
    cache.set_json(key, response.model_dump(mode="json"))
    return response


@router.post("/centres/", response_model=CentreRead, status_code=status.HTTP_201_CREATED)
def create_centre(payload: CentreCreate, session: SessionDependency, _: StaffDependency) -> Centre:
    centre = catalogue.create_centre(session, payload)
    cache.invalidate("catalogue")
    return centre


@router.patch("/centres/{centre_id}/", response_model=CentreRead)
def patch_centre(
    centre_id: uuid.UUID, payload: CentreUpdate, session: SessionDependency, _: StaffDependency
) -> Centre:
    centre = catalogue.update_centre(session, centre_id, payload)
    cache.invalidate("catalogue")
    return centre


@router.get("/tests/", response_model=DiagnosticTestList)
def list_tests(
    session: SessionDependency,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> DiagnosticTestList:
    key = f"catalogue:tests:{cache.version('catalogue')}:{limit}:{offset}"
    cached = cache.get_json(key)
    if cached is not None:
        return DiagnosticTestList.model_validate(cached)

    tests, total = catalogue.list_diagnostic_tests(session, limit, offset)
    response = DiagnosticTestList(
        items=tests, pagination=PaginationMeta(limit=limit, offset=offset, total=total)
    )
    cache.set_json(key, response.model_dump(mode="json"))
    return response


@router.post("/tests/", response_model=DiagnosticTestRead, status_code=status.HTTP_201_CREATED)
def create_test(
    payload: DiagnosticTestCreate, session: SessionDependency, _: StaffDependency
) -> DiagnosticTest:
    diagnostic_test = catalogue.create_diagnostic_test(session, payload)
    cache.invalidate("catalogue")
    return diagnostic_test


@router.post(
    "/centres/{centre_id}/tests/", response_model=OfferingRead, status_code=status.HTTP_201_CREATED
)
def create_offering(
    centre_id: uuid.UUID, payload: OfferingCreate, session: SessionDependency, _: StaffDependency
) -> Offering:
    offering = catalogue.create_offering(session, centre_id, payload)
    cache.invalidate("catalogue")
    return offering


@router.patch("/offerings/{offering_id}/", response_model=OfferingRead)
def patch_offering(
    offering_id: uuid.UUID, payload: OfferingUpdate, session: SessionDependency, _: StaffDependency
) -> Offering:
    offering = catalogue.update_offering(session, offering_id, payload)
    cache.invalidate("catalogue")
    return offering
