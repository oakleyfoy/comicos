"""P63 Market Intelligence Platform API."""

from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.market_intelligence_platform import (
    AcquisitionBuildResultRead,
    AcquisitionItemRead,
    AcquisitionListRead,
    AcquisitionStatusUpdate,
    MarketComponentCertificationRead,
    MarketPlatformBuildRead,
    MarketPlatformCertificationRead,
    MarketSignalBuildResultRead,
    MarketSignalItemRead,
    MarketSignalListRead,
    PortfolioBuildResultRead,
    PortfolioPerformanceItemRead,
    PortfolioPerformanceSnapshotRead,
    SellBuildResultRead,
    SellSignalItemRead,
    SellSignalListRead,
    SellSignalStatusUpdate,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.services.market_intelligence_automation import run_market_intelligence_platform_build
from app.services.market_intelligence_certification import (
    certify_acquisition_opportunities,
    certify_market_signals,
    certify_portfolio_performance,
    certify_sell_signals,
    get_market_platform_certification,
)
from app.services.market_signal_service import build_market_signals, get_latest_market_signal_snapshot, list_market_signal_items
from app.services.p63_acquisition_opportunity_service import (
    build_acquisition_opportunities,
    get_latest_acquisition_snapshot,
    list_acquisition_items,
    update_acquisition_item_status,
)
from app.services.p63_feature_flags import p63_market_intelligence_enabled
from app.services.portfolio_performance_service import (
    build_portfolio_performance_snapshot,
    get_latest_portfolio_snapshot,
    list_portfolio_items,
)
from app.services.sell_signal_service import (
    build_sell_signals,
    get_latest_sell_signal_snapshot,
    list_sell_signal_items,
    update_sell_signal_item_status,
)

market_intelligence_platform_router = APIRouter(
    prefix="/api/v1/market-intelligence",
    tags=["P63 Market Intelligence Platform"],
)


def attach_market_intelligence_platform_layer(app: FastAPI) -> None:
    app.include_router(market_intelligence_platform_router)


def _guard() -> None:
    if not p63_market_intelligence_enabled():
        raise HTTPException(status_code=403, detail="P63_MARKET_INTELLIGENCE_DISABLED")


def register_market_intelligence_platform_routes(router: APIRouter) -> None:
    @router.get("/portfolio/latest", response_model=ScanApiV1Envelope)
    def v1_portfolio_latest(
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ) -> ScanApiV1Envelope:
        _guard()
        assert current_user.id is not None
        snap = get_latest_portfolio_snapshot(session, owner_user_id=int(current_user.id))
        if snap is None:
            return wrap_object(
                PortfolioPerformanceSnapshotRead(
                    snapshot_id=0,
                    snapshot_date=date.today(),
                    generated_at=datetime.now(timezone.utc),
                    total_items=0,
                    total_cost_basis=0,
                    total_current_value=0,
                    total_unrealized_gain=0,
                    total_unrealized_gain_pct=0,
                    top_gainers_count=0,
                    top_losers_count=0,
                ),
                owner_user_id=int(current_user.id),
            )
        items, _ = list_portfolio_items(session, snapshot_id=int(snap.id or 0))
        body = PortfolioPerformanceSnapshotRead(
            snapshot_id=int(snap.id or 0),
            snapshot_date=snap.snapshot_date,
            generated_at=snap.generated_at,
            total_items=snap.total_items,
            total_cost_basis=float(snap.total_cost_basis),
            total_current_value=float(snap.total_current_value),
            total_unrealized_gain=float(snap.total_unrealized_gain),
            total_unrealized_gain_pct=float(snap.total_unrealized_gain_pct),
            top_gainers_count=snap.top_gainers_count,
            top_losers_count=snap.top_losers_count,
            items=[
                PortfolioPerformanceItemRead(
                    id=int(i.id or 0),
                    owner_id=int(i.owner_user_id),
                    inventory_copy_id=int(i.inventory_copy_id),
                    title=i.title,
                    publisher=i.publisher,
                    issue_number=i.issue_number,
                    quantity=i.quantity,
                    cost_basis=float(i.cost_basis),
                    current_value=float(i.current_value),
                    unrealized_gain=float(i.unrealized_gain),
                    unrealized_gain_pct=float(i.unrealized_gain_pct),
                    demand_score=i.demand_score,
                    velocity_score=i.velocity_score,
                    recommendation_score=i.recommendation_score,
                    performance_tier=i.performance_tier,
                    notes_json=i.notes_json or {},
                )
                for i in items
            ],
        )
        return wrap_object(body, owner_user_id=int(current_user.id))

    @router.post("/portfolio/build", response_model=ScanApiV1Envelope)
    def v1_portfolio_build(
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ) -> ScanApiV1Envelope:
        _guard()
        assert current_user.id is not None
        snap = build_portfolio_performance_snapshot(session, owner_user_id=int(current_user.id))
        return wrap_object(
            PortfolioBuildResultRead(snapshot_id=int(snap.id or 0), total_items=snap.total_items),
            owner_user_id=int(current_user.id),
        )

    @router.get("/portfolio/certification", response_model=ScanApiV1Envelope)
    def v1_portfolio_certification(
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ) -> ScanApiV1Envelope:
        _guard()
        assert current_user.id is not None
        cert = certify_portfolio_performance(session, owner_user_id=int(current_user.id))
        return wrap_object(MarketComponentCertificationRead(**cert), owner_user_id=int(current_user.id))

    @router.get("/sell-signals/latest", response_model=ScanApiV1Envelope)
    def v1_sell_latest(
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ) -> ScanApiV1Envelope:
        _guard()
        assert current_user.id is not None
        snap = get_latest_sell_signal_snapshot(session, owner_user_id=int(current_user.id))
        if snap is None:
            return wrap_object(SellSignalListRead(), owner_user_id=int(current_user.id))
        items, total = list_sell_signal_items(session, snapshot_id=int(snap.id or 0))
        body = SellSignalListRead(
            snapshot_id=int(snap.id or 0),
            total_items=total,
            strong_sell_count=snap.strong_sell_count,
            consider_sell_count=snap.consider_sell_count,
            hold_count=snap.hold_count,
            items=[
                SellSignalItemRead(
                    id=int(i.id or 0),
                    owner_id=int(i.owner_user_id),
                    inventory_copy_id=int(i.inventory_copy_id),
                    title=i.title,
                    publisher=i.publisher,
                    issue_number=i.issue_number,
                    sell_score=i.sell_score,
                    hold_score=i.hold_score,
                    recommended_action=i.recommended_action,
                    sell_reason=i.sell_reason,
                    confidence=i.confidence,
                    status=i.status,
                    unrealized_gain_pct=i.unrealized_gain_pct,
                )
                for i in items
            ],
        )
        return wrap_object(body, owner_user_id=int(current_user.id))

    @router.post("/sell-signals/build", response_model=ScanApiV1Envelope)
    def v1_sell_build(
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ) -> ScanApiV1Envelope:
        _guard()
        assert current_user.id is not None
        snap = build_sell_signals(session, owner_user_id=int(current_user.id))
        return wrap_object(
            SellBuildResultRead(snapshot_id=int(snap.id or 0), total_items=snap.total_items),
            owner_user_id=int(current_user.id),
        )

    @router.patch("/sell-signals/item/{item_id}", response_model=ScanApiV1Envelope)
    def v1_sell_patch(
        item_id: int,
        payload: SellSignalStatusUpdate,
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ) -> ScanApiV1Envelope:
        _guard()
        assert current_user.id is not None
        try:
            row = update_sell_signal_item_status(
                session,
                item_id=item_id,
                owner_user_id=int(current_user.id),
                status=payload.status,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return wrap_object(
            SellSignalItemRead(
                id=int(row.id or 0),
                owner_id=int(row.owner_user_id),
                inventory_copy_id=int(row.inventory_copy_id),
                title=row.title,
                publisher=row.publisher,
                issue_number=row.issue_number,
                sell_score=row.sell_score,
                hold_score=row.hold_score,
                recommended_action=row.recommended_action,
                sell_reason=row.sell_reason,
                confidence=row.confidence,
                status=row.status,
                unrealized_gain_pct=row.unrealized_gain_pct,
            ),
            owner_user_id=int(current_user.id),
        )

    @router.get("/sell-signals/certification", response_model=ScanApiV1Envelope)
    def v1_sell_certification(
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ) -> ScanApiV1Envelope:
        _guard()
        assert current_user.id is not None
        cert = certify_sell_signals(session, owner_user_id=int(current_user.id))
        return wrap_object(MarketComponentCertificationRead(**cert), owner_user_id=int(current_user.id))

    @router.get("/acquisition/latest", response_model=ScanApiV1Envelope)
    def v1_acquisition_latest(
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ) -> ScanApiV1Envelope:
        _guard()
        assert current_user.id is not None
        snap = get_latest_acquisition_snapshot(session, owner_user_id=int(current_user.id))
        if snap is None:
            return wrap_object(AcquisitionListRead(), owner_user_id=int(current_user.id))
        items, total = list_acquisition_items(session, snapshot_id=int(snap.id or 0))
        body = AcquisitionListRead(
            snapshot_id=int(snap.id or 0),
            total_items=total,
            high_priority_count=snap.high_priority_count,
            watch_count=snap.watch_count,
            items=[
                AcquisitionItemRead(
                    id=int(i.id or 0),
                    owner_id=int(i.owner_user_id),
                    title=i.title,
                    publisher=i.publisher,
                    issue_number=i.issue_number,
                    opportunity_score=i.opportunity_score,
                    demand_score=i.demand_score,
                    velocity_score=i.velocity_score,
                    spec_score=i.spec_score,
                    recommendation_score=i.recommendation_score,
                    estimated_market_price=float(i.estimated_market_price) if i.estimated_market_price is not None else None,
                    target_buy_price=float(i.target_buy_price) if i.target_buy_price is not None else None,
                    reason=i.reason,
                    action=i.action,
                    status=i.status,
                )
                for i in items
            ],
        )
        return wrap_object(body, owner_user_id=int(current_user.id))

    @router.post("/acquisition/build", response_model=ScanApiV1Envelope)
    def v1_acquisition_build(
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ) -> ScanApiV1Envelope:
        _guard()
        assert current_user.id is not None
        snap = build_acquisition_opportunities(session, owner_user_id=int(current_user.id))
        return wrap_object(
            AcquisitionBuildResultRead(snapshot_id=int(snap.id or 0), total_items=snap.total_items),
            owner_user_id=int(current_user.id),
        )

    @router.patch("/acquisition/item/{item_id}", response_model=ScanApiV1Envelope)
    def v1_acquisition_patch(
        item_id: int,
        payload: AcquisitionStatusUpdate,
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ) -> ScanApiV1Envelope:
        _guard()
        assert current_user.id is not None
        try:
            row = update_acquisition_item_status(
                session,
                item_id=item_id,
                owner_user_id=int(current_user.id),
                status=payload.status,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return wrap_object(
            AcquisitionItemRead(
                id=int(row.id or 0),
                owner_id=int(row.owner_user_id),
                title=row.title,
                publisher=row.publisher,
                issue_number=row.issue_number,
                opportunity_score=row.opportunity_score,
                demand_score=row.demand_score,
                velocity_score=row.velocity_score,
                spec_score=row.spec_score,
                recommendation_score=row.recommendation_score,
                estimated_market_price=float(row.estimated_market_price) if row.estimated_market_price is not None else None,
                target_buy_price=float(row.target_buy_price) if row.target_buy_price is not None else None,
                reason=row.reason,
                action=row.action,
                status=row.status,
            ),
            owner_user_id=int(current_user.id),
        )

    @router.get("/acquisition/certification", response_model=ScanApiV1Envelope)
    def v1_acquisition_certification(
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ) -> ScanApiV1Envelope:
        _guard()
        assert current_user.id is not None
        cert = certify_acquisition_opportunities(session, owner_user_id=int(current_user.id))
        return wrap_object(MarketComponentCertificationRead(**cert), owner_user_id=int(current_user.id))

    @router.get("/signals/latest", response_model=ScanApiV1Envelope)
    def v1_signals_latest(
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ) -> ScanApiV1Envelope:
        _guard()
        assert current_user.id is not None
        snap = get_latest_market_signal_snapshot(session, owner_user_id=int(current_user.id))
        if snap is None:
            return wrap_object(MarketSignalListRead(), owner_user_id=int(current_user.id))
        items, total = list_market_signal_items(session, snapshot_id=int(snap.id or 0))
        body = MarketSignalListRead(
            snapshot_id=int(snap.id or 0),
            scope=snap.scope,
            total_items=total,
            items=[
                MarketSignalItemRead(
                    id=int(i.id or 0),
                    title=i.title,
                    publisher=i.publisher,
                    issue_number=i.issue_number,
                    market_score=i.market_score,
                    signal_type=i.signal_type,
                    signal_reason=i.signal_reason,
                    confidence=i.confidence,
                    demand_score=i.demand_score,
                    velocity_score=i.velocity_score,
                    opportunity_score=i.opportunity_score,
                    risk_score=i.risk_score,
                )
                for i in items
            ],
        )
        return wrap_object(body, owner_user_id=int(current_user.id))

    @router.post("/signals/build", response_model=ScanApiV1Envelope)
    def v1_signals_build(
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ) -> ScanApiV1Envelope:
        _guard()
        assert current_user.id is not None
        snap = build_market_signals(session, owner_user_id=int(current_user.id))
        return wrap_object(
            MarketSignalBuildResultRead(snapshot_id=int(snap.id or 0), total_items=snap.total_items),
            owner_user_id=int(current_user.id),
        )

    @router.get("/signals/certification", response_model=ScanApiV1Envelope)
    def v1_signals_certification(
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ) -> ScanApiV1Envelope:
        _guard()
        assert current_user.id is not None
        cert = certify_market_signals(session, owner_user_id=int(current_user.id))
        return wrap_object(MarketComponentCertificationRead(**cert), owner_user_id=int(current_user.id))

    @router.get("/platform/certification", response_model=ScanApiV1Envelope)
    def v1_platform_certification(
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ) -> ScanApiV1Envelope:
        _guard()
        assert current_user.id is not None
        cert = get_market_platform_certification(session, owner_user_id=int(current_user.id))
        return wrap_object(MarketPlatformCertificationRead(**cert), owner_user_id=int(current_user.id))

    @router.post("/platform/build", response_model=ScanApiV1Envelope)
    def v1_platform_build(
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ) -> ScanApiV1Envelope:
        _guard()
        assert current_user.id is not None
        raw = run_market_intelligence_platform_build(session, owner_user_id=int(current_user.id))
        body = MarketPlatformBuildRead(
            steps=raw["steps"],
            certification=MarketPlatformCertificationRead(**raw["certification"]),
        )
        return wrap_object(body, owner_user_id=int(current_user.id))


register_market_intelligence_platform_routes(market_intelligence_platform_router)
