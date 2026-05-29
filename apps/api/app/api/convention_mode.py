"""P44-04 `/api/v1/organizations/*/convention-mode` layered routes with deterministic envelopes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.convention_mode import (
    ConventionBoothCreateRequest,
    ConventionBoothUpdateRequest,
    ConventionInventoryStageRequest,
    ConventionSessionCreateRequest,
    ConventionSessionUpdateRequest,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.convention_mode_service import (
    build_convention_mode_dashboard,
    create_booth,
    create_convention_session,
    list_activities,
    list_booths,
    list_sessions,
    list_staged_inventory,
    stage_inventory,
    update_booth,
    update_convention_session,
)

convention_mode_v1_router = APIRouter(prefix="/api/v1", tags=["Convention Mode API v1 (P44-04)"])


def attach_convention_mode_layer(app: FastAPI) -> None:
    app.include_router(convention_mode_v1_router)


@convention_mode_v1_router.get("/organizations/{organization_id}/convention-mode", response_model=ScanApiV1Envelope)
def v1_get_convention_mode_dashboard(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_convention_mode_dashboard(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=organization_id)


@convention_mode_v1_router.get("/organizations/{organization_id}/convention-mode/sessions", response_model=ScanApiV1Envelope)
def v1_list_convention_sessions(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_sessions(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@convention_mode_v1_router.post(
    "/organizations/{organization_id}/convention-mode/sessions",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_create_convention_session(
    organization_id: int,
    payload: ConventionSessionCreateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = create_convention_session(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@convention_mode_v1_router.patch(
    "/organizations/{organization_id}/convention-mode/sessions/{session_id}",
    response_model=ScanApiV1Envelope,
)
def v1_update_convention_session(
    organization_id: int,
    session_id: int,
    payload: ConventionSessionUpdateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = update_convention_session(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        session_id=session_id,
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@convention_mode_v1_router.get("/organizations/{organization_id}/convention-mode/booths", response_model=ScanApiV1Envelope)
def v1_list_convention_booths(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_booths(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@convention_mode_v1_router.post(
    "/organizations/{organization_id}/convention-mode/booths",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_create_convention_booth(
    organization_id: int,
    payload: ConventionBoothCreateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = create_booth(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@convention_mode_v1_router.patch(
    "/organizations/{organization_id}/convention-mode/booths/{booth_id}",
    response_model=ScanApiV1Envelope,
)
def v1_update_convention_booth(
    organization_id: int,
    booth_id: int,
    payload: ConventionBoothUpdateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = update_booth(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        booth_id=booth_id,
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@convention_mode_v1_router.get("/organizations/{organization_id}/convention-mode/inventory", response_model=ScanApiV1Envelope)
def v1_list_convention_staged_inventory(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_staged_inventory(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@convention_mode_v1_router.post(
    "/organizations/{organization_id}/convention-mode/inventory",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_stage_convention_inventory(
    organization_id: int,
    payload: ConventionInventoryStageRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = stage_inventory(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@convention_mode_v1_router.get("/organizations/{organization_id}/convention-mode/activities", response_model=ScanApiV1Envelope)
def v1_list_convention_activities(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_activities(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))
