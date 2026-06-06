"""P78-01 sell queue and listing drafts (`/api/v1/sell-queue`, `/api/v1/listing-drafts`)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.p78_sell_workflow import (
    P78ListingDraftCreate,
    P78ListingDraftListResponse,
    P78ListingDraftUpdate,
    P78ListingPricingRead,
    P78SellBundleListResponse,
    P78SellQueueListResponse,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.p78_bundle_service import list_sell_bundles
from app.services.p78_listing_draft_service import (
    generate_listing_draft,
    list_listing_drafts,
    pricing_for_draft,
    update_listing_draft,
)
from app.services.p78_sell_queue_service import build_sell_queue

p78_sell_workflow_v1_router = APIRouter(tags=["Sell Workflow API v1 (P78-01)"])


def attach_p78_sell_workflow_layer(app: FastAPI) -> None:
    app.include_router(p78_sell_workflow_v1_router)


@p78_sell_workflow_v1_router.get("/api/v1/sell-queue", response_model=ScanApiV1Envelope)
def v1_sell_queue(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    refresh: bool = Query(True),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P78SellQueueListResponse = build_sell_queue(
        session,
        owner_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
        refresh_upstream=refresh,
    )
    session.commit()
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@p78_sell_workflow_v1_router.get("/api/v1/sell-queue/bundles", response_model=ScanApiV1Envelope)
def v1_sell_queue_bundles(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P78SellBundleListResponse = list_sell_bundles(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@p78_sell_workflow_v1_router.get("/api/v1/listing-drafts", response_model=ScanApiV1Envelope)
def v1_list_listing_drafts(
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P78ListingDraftListResponse = list_listing_drafts(
        session,
        owner_user_id=int(current_user.id),
        status=status,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@p78_sell_workflow_v1_router.post("/api/v1/listing-drafts", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_create_listing_draft(
    payload: P78ListingDraftCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = generate_listing_draft(session, owner_user_id=int(current_user.id), payload=payload)
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p78_sell_workflow_v1_router.put("/api/v1/listing-drafts/{draft_id}", response_model=ScanApiV1Envelope)
def v1_update_listing_draft(
    draft_id: int,
    payload: P78ListingDraftUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = update_listing_draft(session, owner_user_id=int(current_user.id), draft_id=draft_id, payload=payload)
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p78_sell_workflow_v1_router.get("/api/v1/listing-drafts/{draft_id}/pricing", response_model=ScanApiV1Envelope)
def v1_listing_draft_pricing(
    draft_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P78ListingPricingRead = pricing_for_draft(session, owner_user_id=int(current_user.id), draft_id=draft_id)
    return wrap_object(body, owner_user_id=int(current_user.id))
