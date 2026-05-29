"""P43-06 `/api/v1/organizations/*/marketplace-events` routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.marketplace_events import MarketplaceEventIngestRequest, MarketplaceEventProcessRequest
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.marketplace_event_processing import (
    get_marketplace_event,
    ingest_marketplace_event,
    list_marketplace_events,
    list_processing_runs,
    process_marketplace_event,
)

marketplace_events_v1_router = APIRouter(prefix="/api/v1", tags=["Marketplace Events API v1 (P43-06)"])


def attach_marketplace_events_layer(app: FastAPI) -> None:
    app.include_router(marketplace_events_v1_router)


@marketplace_events_v1_router.get("/organizations/{organization_id}/marketplace-events", response_model=ScanApiV1Envelope)
def v1_list_marketplace_events(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_marketplace_events(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@marketplace_events_v1_router.get("/organizations/{organization_id}/marketplace-events/{event_id}", response_model=ScanApiV1Envelope)
def v1_get_marketplace_event(
    organization_id: int,
    event_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_marketplace_event(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        event_id=event_id,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=event_id)


@marketplace_events_v1_router.get("/organizations/{organization_id}/marketplace-events/runs", response_model=ScanApiV1Envelope)
def v1_list_marketplace_event_runs(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_processing_runs(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@marketplace_events_v1_router.post(
    "/organizations/{organization_id}/marketplace-events/ingest",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_ingest_marketplace_event(
    organization_id: int,
    payload: MarketplaceEventIngestRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = ingest_marketplace_event(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        marketplace_account_id=payload.marketplace_account_id,
        external_event_identifier=payload.external_event_identifier,
        event_type=payload.event_type,
        event_payload_json=payload.event_payload_json,
        received_at=payload.received_at,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.event.id)


@marketplace_events_v1_router.post(
    "/organizations/{organization_id}/marketplace-events/process",
    response_model=ScanApiV1Envelope,
)
def v1_process_marketplace_event(
    organization_id: int,
    payload: MarketplaceEventProcessRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = process_marketplace_event(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        marketplace_event_id=payload.marketplace_event_id,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.event.id)
