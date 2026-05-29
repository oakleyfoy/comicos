"""P43-05 `/api/v1/organizations/*/marketplace-pricing` routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.marketplace_pricing import (
    MarketplaceOfferIngestRequest,
    MarketplaceOfferStatusUpdateRequest,
    MarketplacePriceRecommendationGenerateRequest,
    MarketplacePriceRecommendationReviewRequest,
    MarketplacePricingRuleCreateRequest,
    MarketplacePricingRuleUpdateRequest,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.marketplace_offer_service import (
    generate_offer_summary,
    get_marketplace_offer,
    ingest_marketplace_offer,
    list_marketplace_offers,
    update_offer_status,
)
from app.services.marketplace_pricing_service import (
    create_pricing_rule,
    generate_price_recommendation,
    list_price_recommendations,
    list_pricing_rules,
    review_price_recommendation,
    update_pricing_rule,
)

marketplace_pricing_v1_router = APIRouter(prefix="/api/v1", tags=["Marketplace Pricing API v1 (P43-05)"])


def attach_marketplace_pricing_layer(app: FastAPI) -> None:
    app.include_router(marketplace_pricing_v1_router)


@marketplace_pricing_v1_router.get("/organizations/{organization_id}/marketplace-pricing/recommendations", response_model=ScanApiV1Envelope)
def v1_list_marketplace_pricing_recommendations(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_price_recommendations(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@marketplace_pricing_v1_router.get("/organizations/{organization_id}/marketplace-pricing/offers", response_model=ScanApiV1Envelope)
def v1_list_marketplace_pricing_offers(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_marketplace_offers(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@marketplace_pricing_v1_router.get("/organizations/{organization_id}/marketplace-pricing/rules", response_model=ScanApiV1Envelope)
def v1_list_marketplace_pricing_rules(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_pricing_rules(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@marketplace_pricing_v1_router.post(
    "/organizations/{organization_id}/marketplace-pricing/recommendations/generate",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_generate_marketplace_pricing_recommendation(
    organization_id: int,
    payload: MarketplacePriceRecommendationGenerateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = generate_price_recommendation(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@marketplace_pricing_v1_router.post(
    "/organizations/{organization_id}/marketplace-pricing/offers/ingest",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_ingest_marketplace_offer(
    organization_id: int,
    payload: MarketplaceOfferIngestRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = ingest_marketplace_offer(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@marketplace_pricing_v1_router.post(
    "/organizations/{organization_id}/marketplace-pricing/rules",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_create_marketplace_pricing_rule(
    organization_id: int,
    payload: MarketplacePricingRuleCreateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = create_pricing_rule(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@marketplace_pricing_v1_router.patch("/organizations/{organization_id}/marketplace-pricing/recommendations/{recommendation_id}/review", response_model=ScanApiV1Envelope)
def v1_review_marketplace_pricing_recommendation(
    organization_id: int,
    recommendation_id: int,
    payload: MarketplacePriceRecommendationReviewRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = review_price_recommendation(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        recommendation_id=recommendation_id,
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@marketplace_pricing_v1_router.patch("/organizations/{organization_id}/marketplace-pricing/offers/{offer_id}/status", response_model=ScanApiV1Envelope)
def v1_update_marketplace_pricing_offer_status(
    organization_id: int,
    offer_id: int,
    payload: MarketplaceOfferStatusUpdateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = update_offer_status(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        offer_id=offer_id,
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@marketplace_pricing_v1_router.patch("/organizations/{organization_id}/marketplace-pricing/rules/{rule_id}", response_model=ScanApiV1Envelope)
def v1_update_marketplace_pricing_rule(
    organization_id: int,
    rule_id: int,
    payload: MarketplacePricingRuleUpdateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = update_pricing_rule(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        rule_id=rule_id,
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)
