from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.marketplace_operations import MarketplaceOperationsRunResponse, MarketplaceRecommendationListResponse
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.inventory_health_agent import run_inventory_health_agent
from app.services.listing_quality_agent import run_listing_quality_agent
from app.services.marketplace_audit_agent import run_marketplace_audit_agent
from app.services.marketplace_operations import (
    REVIEW_STATUS_ACCEPTED,
    REVIEW_STATUS_DISMISSED,
    REVIEW_STATUS_REVIEWED,
    append_review,
    get_operations_dashboard,
    get_recommendation_for_owner,
    list_recommendations,
)
from app.services.pricing_opportunity_agent import run_pricing_opportunity_agent
from app.services.unsold_inventory_agent import run_unsold_inventory_agent

marketplace_operations_v1_router = APIRouter(prefix="/api/v1", tags=["Marketplace Operations Agents API v1"])


def attach_marketplace_operations_layer(app: FastAPI) -> None:
    app.include_router(marketplace_operations_v1_router)


@marketplace_operations_v1_router.get("/marketplace-operations/recommendations", response_model=ScanApiV1Envelope)
def v1_list_marketplace_operations_recommendations(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    recommendation_type: str | None = Query(default=None),
    recommendation_status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_recommendations(
        session,
        owner_user_id=int(current_user.id),
        recommendation_type=recommendation_type,
        recommendation_status=recommendation_status,
        limit=limit,
        offset=offset,
    )
    dashboard = get_operations_dashboard(session, owner_user_id=int(current_user.id))
    body = MarketplaceRecommendationListResponse(
        items=body.items,
        total_items=body.total_items,
        limit=body.limit,
        offset=body.offset,
        dashboard=dashboard,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@marketplace_operations_v1_router.get("/marketplace-operations/recommendations/{recommendation_id}", response_model=ScanApiV1Envelope)
def v1_get_marketplace_operations_recommendation(
    recommendation_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_recommendation_for_owner(
        session,
        owner_user_id=int(current_user.id),
        recommendation_id=recommendation_id,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.recommendation.id)


@marketplace_operations_v1_router.post(
    "/marketplace-operations/run/listing-quality",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_run_listing_quality_agent(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = run_listing_quality_agent(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.agent_execution_id)


@marketplace_operations_v1_router.post(
    "/marketplace-operations/run/inventory-health",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_run_inventory_health_agent(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = run_inventory_health_agent(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.agent_execution_id)


@marketplace_operations_v1_router.post(
    "/marketplace-operations/run/pricing-opportunities",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_run_pricing_opportunity_agent(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = run_pricing_opportunity_agent(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.agent_execution_id)


@marketplace_operations_v1_router.post(
    "/marketplace-operations/run/unsold-inventory",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_run_unsold_inventory_agent(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = run_unsold_inventory_agent(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.agent_execution_id)


@marketplace_operations_v1_router.post(
    "/marketplace-operations/run/audit",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_run_marketplace_audit_agent(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = run_marketplace_audit_agent(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.agent_execution_id)


@marketplace_operations_v1_router.post("/marketplace-operations/recommendations/{recommendation_id}/reviewed", response_model=ScanApiV1Envelope)
def v1_marketplace_recommendation_reviewed(
    recommendation_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = append_review(
        session,
        owner_user_id=int(current_user.id),
        recommendation_id=recommendation_id,
        reviewed_by=str(int(current_user.id)),
        review_status=REVIEW_STATUS_REVIEWED,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.recommendation.id)


@marketplace_operations_v1_router.post("/marketplace-operations/recommendations/{recommendation_id}/dismissed", response_model=ScanApiV1Envelope)
def v1_marketplace_recommendation_dismissed(
    recommendation_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = append_review(
        session,
        owner_user_id=int(current_user.id),
        recommendation_id=recommendation_id,
        reviewed_by=str(int(current_user.id)),
        review_status=REVIEW_STATUS_DISMISSED,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.recommendation.id)


@marketplace_operations_v1_router.post("/marketplace-operations/recommendations/{recommendation_id}/accepted", response_model=ScanApiV1Envelope)
def v1_marketplace_recommendation_accepted(
    recommendation_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = append_review(
        session,
        owner_user_id=int(current_user.id),
        recommendation_id=recommendation_id,
        reviewed_by=str(int(current_user.id)),
        review_status=REVIEW_STATUS_ACCEPTED,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.recommendation.id)
