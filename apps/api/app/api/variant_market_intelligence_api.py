"""P66 Variant & Market Intelligence APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.schemas.variant_market_intelligence import (
    MarketPriceObservationRead,
    MarketPriceSnapshotRead,
    P66BuildResultEnvelope,
    P66BuildResultRead,
    P66CertificationRead,
    P66SnapshotBuildRead,
    P66IntegrationRead,
    QuantityRecommendationItemRead,
    QuantityRecommendationSnapshotRead,
    VariantDecisionItemRead,
    VariantDecisionSnapshotRead,
    VariantIntelligenceItemRead,
    VariantIntelligenceSnapshotRead,
)
from app.services.market_pricing_service import (
    build_market_prices,
    get_latest_market_price_snapshot,
    list_market_observations,
)
from app.services.p66_certification_service import certify_p66_platform
from app.services.p66_feature_flags import (
    p66_market_pricing_enabled,
    p66_quantity_intelligence_enabled,
    p66_variant_decision_enabled,
    p66_variant_intelligence_enabled,
)
from app.services.p66_platform_service import build_p66_platform
from app.services.quantity_intelligence_service import (
    build_quantity_recommendations,
    get_latest_quantity_snapshot,
    list_quantity_items,
)
from app.services.variant_decision_engine import (
    build_variant_decisions,
    get_latest_variant_decision_snapshot,
    list_variant_decision_items,
)
from app.services.variant_intelligence_service import (
    build_variant_intelligence,
    get_latest_variant_intelligence_snapshot,
    list_variant_intelligence_items,
)

READINESS_SUCCESS = "SUCCESS"
READINESS_NOT_READY = "NOT_READY"

variant_router = APIRouter(prefix="/api/v1/variant-intelligence", tags=["P66 Variant Intelligence"])
quantity_router = APIRouter(prefix="/api/v1/quantity-intelligence", tags=["P66 Quantity Intelligence"])
pricing_router = APIRouter(prefix="/api/v1/market-pricing", tags=["P66 Market Pricing"])
decision_router = APIRouter(prefix="/api/v1/variant-decision", tags=["P66 Variant Decision"])


def attach_variant_market_intelligence_layer(app: FastAPI) -> None:
    app.include_router(variant_router)
    app.include_router(quantity_router)
    app.include_router(pricing_router)
    app.include_router(decision_router)


def _vi_guard() -> None:
    if not p66_variant_intelligence_enabled():
        raise HTTPException(status_code=403, detail="P66_VARIANT_INTELLIGENCE_DISABLED")


def _qty_guard() -> None:
    if not p66_quantity_intelligence_enabled():
        raise HTTPException(status_code=403, detail="P66_QUANTITY_INTELLIGENCE_DISABLED")


def _price_guard() -> None:
    if not p66_market_pricing_enabled():
        raise HTTPException(status_code=403, detail="P66_MARKET_PRICING_DISABLED")


def _dec_guard() -> None:
    if not p66_variant_decision_enabled():
        raise HTTPException(status_code=403, detail="P66_VARIANT_DECISION_DISABLED")


@variant_router.get("/latest", response_model=ScanApiV1Envelope)
def variant_latest(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> ScanApiV1Envelope:
    _vi_guard()
    assert current_user.id is not None
    snap = get_latest_variant_intelligence_snapshot(session, owner_user_id=int(current_user.id))
    if snap is None:
        return wrap_object(VariantIntelligenceSnapshotRead(readiness_status=READINESS_NOT_READY), owner_user_id=int(current_user.id))
    items = list_variant_intelligence_items(session, snapshot_id=int(snap.id or 0))
    body = VariantIntelligenceSnapshotRead(
        snapshot_id=int(snap.id or 0),
        readiness_status=READINESS_SUCCESS,
        generated_at=snap.generated_at,
        total_items=snap.total_items,
        items=[
            VariantIntelligenceItemRead(
                id=int(i.id or 0),
                cover_label=i.cover_label,
                variant_name=i.variant_name,
                variant_score=i.variant_score,
                variant_tier=i.variant_tier,
                variant_reason=i.variant_reason,
                external_catalog_issue_id=i.external_catalog_issue_id,
                factors_json=i.factors_json or {},
            )
            for i in items
        ],
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@variant_router.post("/build", response_model=ScanApiV1Envelope)
def variant_build(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> ScanApiV1Envelope:
    _vi_guard()
    assert current_user.id is not None
    snap = build_variant_intelligence(session, owner_user_id=int(current_user.id))
    return wrap_object(
        P66SnapshotBuildRead(snapshot_id=int(snap.id or 0), total_items=snap.total_items),
        owner_user_id=int(current_user.id),
    )


@quantity_router.get("/latest", response_model=ScanApiV1Envelope)
def quantity_latest(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> ScanApiV1Envelope:
    _qty_guard()
    assert current_user.id is not None
    snap = get_latest_quantity_snapshot(session, owner_user_id=int(current_user.id))
    if snap is None:
        return wrap_object(QuantityRecommendationSnapshotRead(readiness_status=READINESS_NOT_READY), owner_user_id=int(current_user.id))
    items = list_quantity_items(session, snapshot_id=int(snap.id or 0))
    body = QuantityRecommendationSnapshotRead(
        snapshot_id=int(snap.id or 0),
        readiness_status=READINESS_SUCCESS,
        total_items=snap.total_items,
        items=[
            QuantityRecommendationItemRead(
                id=int(i.id or 0),
                title=i.title,
                collection_quantity=i.collection_quantity,
                spec_quantity=i.spec_quantity,
                flip_quantity=i.flip_quantity,
                total_quantity=i.total_quantity,
                confidence=i.confidence,
                reason=i.reason,
                buy_queue_item_id=i.buy_queue_item_id,
            )
            for i in items
        ],
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@quantity_router.post("/build", response_model=ScanApiV1Envelope)
def quantity_build(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> ScanApiV1Envelope:
    _qty_guard()
    assert current_user.id is not None
    snap = build_quantity_recommendations(session, owner_user_id=int(current_user.id))
    return wrap_object(
        P66SnapshotBuildRead(snapshot_id=int(snap.id or 0), total_items=snap.total_items),
        owner_user_id=int(current_user.id),
    )


@pricing_router.get("/latest", response_model=ScanApiV1Envelope)
def pricing_latest(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> ScanApiV1Envelope:
    _price_guard()
    assert current_user.id is not None
    snap = get_latest_market_price_snapshot(session, owner_user_id=int(current_user.id))
    if snap is None:
        return wrap_object(MarketPriceSnapshotRead(), owner_user_id=int(current_user.id))
    obs = list_market_observations(session, snapshot_id=int(snap.id or 0))
    body = MarketPriceSnapshotRead(
        snapshot_id=int(snap.id or 0),
        provider=snap.provider,
        total_observations=snap.total_observations,
        observations=[
            MarketPriceObservationRead(
                id=int(o.id or 0),
                fmv=o.fmv,
                price_trend=o.price_trend,
                liquidity=o.liquidity,
                market_confidence=o.market_confidence,
                external_catalog_variant_id=o.external_catalog_variant_id,
            )
            for o in obs
        ],
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@pricing_router.post("/build", response_model=ScanApiV1Envelope)
def pricing_build(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> ScanApiV1Envelope:
    _price_guard()
    assert current_user.id is not None
    snap = build_market_prices(session, owner_user_id=int(current_user.id))
    return wrap_object(
        P66SnapshotBuildRead(snapshot_id=int(snap.id or 0), total_observations=snap.total_observations),
        owner_user_id=int(current_user.id),
    )


@decision_router.get("/latest", response_model=ScanApiV1Envelope)
def decision_latest(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> ScanApiV1Envelope:
    _dec_guard()
    assert current_user.id is not None
    snap = get_latest_variant_decision_snapshot(session, owner_user_id=int(current_user.id))
    if snap is None:
        return wrap_object(VariantDecisionSnapshotRead(readiness_status=READINESS_NOT_READY), owner_user_id=int(current_user.id))
    items = list_variant_decision_items(session, snapshot_id=int(snap.id or 0))
    body = VariantDecisionSnapshotRead(
        snapshot_id=int(snap.id or 0),
        readiness_status=READINESS_SUCCESS,
        total_issues=snap.total_issues,
        items=[
            VariantDecisionItemRead(
                id=int(i.id or 0),
                title=i.title,
                issue_number=i.issue_number,
                recommendation_summary=i.recommendation_summary,
                cover_ranking_json=list(i.cover_ranking_json or []),
                buy_plan_json=list(i.buy_plan_json or []),
                skip_covers_json=list(i.skip_covers_json or []),
                quantity_plan_json=dict(i.quantity_plan_json or {}),
            )
            for i in items
        ],
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@decision_router.post("/build", response_model=ScanApiV1Envelope)
def decision_build(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> ScanApiV1Envelope:
    _dec_guard()
    assert current_user.id is not None
    snap = build_variant_decisions(session, owner_user_id=int(current_user.id))
    return wrap_object(
        P66SnapshotBuildRead(snapshot_id=int(snap.id or 0), total_issues=snap.total_issues),
        owner_user_id=int(current_user.id),
    )


@decision_router.post("/platform/build", response_model=ScanApiV1Envelope)
def platform_build(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> ScanApiV1Envelope:
    _vi_guard()
    assert current_user.id is not None
    result = build_p66_platform(session, owner_user_id=int(current_user.id))
    body = P66BuildResultEnvelope(
        snapshot_ids=P66BuildResultRead(
            variant_intelligence_snapshot_id=result["variant_intelligence_snapshot_id"],
            market_price_snapshot_id=result["market_price_snapshot_id"],
            quantity_snapshot_id=result["quantity_snapshot_id"],
            variant_decision_snapshot_id=result["variant_decision_snapshot_id"],
        )
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@decision_router.get("/integration/latest", response_model=ScanApiV1Envelope)
def integration_latest(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> ScanApiV1Envelope:
    _dec_guard()
    assert current_user.id is not None
    dec = get_latest_variant_decision_snapshot(session, owner_user_id=int(current_user.id))
    qty = get_latest_quantity_snapshot(session, owner_user_id=int(current_user.id))
    if dec is None:
        return wrap_object(P66IntegrationRead(readiness_status=READINESS_NOT_READY), owner_user_id=int(current_user.id))
    decisions = list_variant_decision_items(session, snapshot_id=int(dec.id or 0))
    qitems = list_quantity_items(session, snapshot_id=int(qty.id or 0)) if qty else []
    body = P66IntegrationRead(
        readiness_status=READINESS_SUCCESS,
        decisions=[
            VariantDecisionItemRead(
                id=int(i.id or 0),
                title=i.title,
                issue_number=i.issue_number,
                recommendation_summary=i.recommendation_summary,
                cover_ranking_json=list(i.cover_ranking_json or []),
                buy_plan_json=list(i.buy_plan_json or []),
                skip_covers_json=list(i.skip_covers_json or []),
                quantity_plan_json=dict(i.quantity_plan_json or {}),
            )
            for i in decisions
        ],
        quantity_items=[
            QuantityRecommendationItemRead(
                id=int(i.id or 0),
                title=i.title,
                collection_quantity=i.collection_quantity,
                spec_quantity=i.spec_quantity,
                flip_quantity=i.flip_quantity,
                total_quantity=i.total_quantity,
                confidence=i.confidence,
                reason=i.reason,
                buy_queue_item_id=i.buy_queue_item_id,
            )
            for i in qitems
        ],
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@decision_router.get("/platform/certification", response_model=ScanApiV1Envelope)
def platform_certification(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> ScanApiV1Envelope:
    _vi_guard()
    assert current_user.id is not None
    data = certify_p66_platform(session, owner_user_id=int(current_user.id))
    return wrap_object(P66CertificationRead(**data), owner_user_id=int(current_user.id))
