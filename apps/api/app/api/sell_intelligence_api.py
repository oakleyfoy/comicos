"""P71 Sell Intelligence Platform APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.schemas.sell_intelligence import (
    P71CertificationRead,
    P71ExitQueueItemRead,
    P71ExitQueueListRead,
    P71ExitRecommendationItemRead,
    P71ExitRecommendationSnapshotRead,
    P71ExitRecommendationsListRead,
    P71LiquidityItemRead,
    P71LiquidityListRead,
    P71ListingItemRead,
    P71ListingListRead,
    P71PlatformBuildRead,
    P71SellDashboardRead,
)
from app.services.exit_queue_service import get_latest_exit_queue_snapshot, list_exit_queue_items
from app.services.exit_recommendation_service import (
    get_latest_exit_recommendation_snapshot,
    list_exit_recommendation_items,
)
from app.services.investor_sell_dashboard_service import get_latest_investor_sell_dashboard
from app.services.liquidity_intelligence_service import get_latest_liquidity_snapshot, list_liquidity_items
from app.services.listing_intelligence_service import get_latest_listing_snapshot, list_listing_items
from app.services.p71_certification_service import certify_p71_sell_intelligence
from app.services.p71_feature_flags import (
    p71_exit_queue_enabled,
    p71_exit_recommendations_enabled,
    p71_liquidity_enabled,
    p71_listing_intelligence_enabled,
    p71_sell_dashboard_enabled,
)
from app.services.p71_platform_service import run_p71_platform_build

sell_intel_router = APIRouter(prefix="/api/v1/sell-intelligence", tags=["P71 Sell Intelligence"])


def attach_sell_intelligence_layer(app: FastAPI) -> None:
    app.include_router(sell_intel_router)


@sell_intel_router.post("/platform/build", response_model=ScanApiV1Envelope)
def platform_build(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> ScanApiV1Envelope:
    assert current_user.id is not None
    payload = run_p71_platform_build(session, owner_user_id=int(current_user.id))
    session.commit()
    cert = certify_p71_sell_intelligence(session, owner_user_id=int(current_user.id))
    return wrap_object(
        P71PlatformBuildRead(steps=payload["steps"] + [{"step": "certification", "certified": cert["certified"]}]),
        owner_user_id=int(current_user.id),
    )


@sell_intel_router.get("/platform/certification", response_model=ScanApiV1Envelope)
def platform_certification(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> ScanApiV1Envelope:
    assert current_user.id is not None
    cert = certify_p71_sell_intelligence(session, owner_user_id=int(current_user.id))
    return wrap_object(P71CertificationRead(**cert), owner_user_id=int(current_user.id))


@sell_intel_router.get("/exit-recommendations", response_model=ScanApiV1Envelope)
def exit_recommendations(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> ScanApiV1Envelope:
    if not p71_exit_recommendations_enabled():
        raise HTTPException(status_code=403, detail="P71_EXIT_RECOMMENDATIONS_DISABLED")
    assert current_user.id is not None
    snap = get_latest_exit_recommendation_snapshot(session, owner_user_id=int(current_user.id))
    if snap is None:
        raise HTTPException(status_code=404, detail="NO_EXIT_RECOMMENDATION_SNAPSHOT")
    items = list_exit_recommendation_items(session, snapshot_id=int(snap.id or 0))
    body = P71ExitRecommendationsListRead(
        snapshot=P71ExitRecommendationSnapshotRead.model_validate(snap),
        items=[P71ExitRecommendationItemRead.model_validate(i) for i in items],
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@sell_intel_router.get("/listing-intelligence", response_model=ScanApiV1Envelope)
def listing_intelligence(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> ScanApiV1Envelope:
    if not p71_listing_intelligence_enabled():
        raise HTTPException(status_code=403, detail="P71_LISTING_INTELLIGENCE_DISABLED")
    assert current_user.id is not None
    snap = get_latest_listing_snapshot(session, owner_user_id=int(current_user.id))
    if snap is None:
        raise HTTPException(status_code=404, detail="NO_LISTING_SNAPSHOT")
    items = list_listing_items(session, snapshot_id=int(snap.id or 0))
    body = P71ListingListRead(
        snapshot_id=int(snap.id or 0),
        items=[P71ListingItemRead.model_validate(i) for i in items],
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@sell_intel_router.get("/liquidity", response_model=ScanApiV1Envelope)
def liquidity(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> ScanApiV1Envelope:
    if not p71_liquidity_enabled():
        raise HTTPException(status_code=403, detail="P71_LIQUIDITY_DISABLED")
    assert current_user.id is not None
    snap = get_latest_liquidity_snapshot(session, owner_user_id=int(current_user.id))
    if snap is None:
        raise HTTPException(status_code=404, detail="NO_LIQUIDITY_SNAPSHOT")
    items = list_liquidity_items(session, snapshot_id=int(snap.id or 0))
    body = P71LiquidityListRead(
        snapshot_id=int(snap.id or 0),
        items=[P71LiquidityItemRead.model_validate(i) for i in items],
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@sell_intel_router.get("/exit-queue", response_model=ScanApiV1Envelope)
def exit_queue(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> ScanApiV1Envelope:
    if not p71_exit_queue_enabled():
        raise HTTPException(status_code=403, detail="P71_EXIT_QUEUE_DISABLED")
    assert current_user.id is not None
    snap = get_latest_exit_queue_snapshot(session, owner_user_id=int(current_user.id))
    if snap is None:
        raise HTTPException(status_code=404, detail="NO_EXIT_QUEUE_SNAPSHOT")
    items = list_exit_queue_items(session, snapshot_id=int(snap.id or 0))
    body = P71ExitQueueListRead(
        snapshot_id=int(snap.id or 0),
        items=[P71ExitQueueItemRead.model_validate(i) for i in items],
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@sell_intel_router.get("/dashboard", response_model=ScanApiV1Envelope)
def dashboard(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> ScanApiV1Envelope:
    if not p71_sell_dashboard_enabled():
        raise HTTPException(status_code=403, detail="P71_SELL_DASHBOARD_DISABLED")
    assert current_user.id is not None
    snap = get_latest_investor_sell_dashboard(session, owner_user_id=int(current_user.id))
    if snap is None:
        raise HTTPException(status_code=404, detail="NO_SELL_DASHBOARD_SNAPSHOT")
    return wrap_object(P71SellDashboardRead.model_validate(snap), owner_user_id=int(current_user.id))
