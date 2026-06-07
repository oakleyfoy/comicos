"""P67 Portfolio Analytics Platform APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.portfolio_analytics import (
    P67CertificationRead,
    P67CollectionAnalyticsLatestRead,
    P67CollectionAnalyticsSnapshotRead,
    P67InvestorDashboardLatestRead,
    P67GradingOpportunityItemRead,
    P67GradingOpportunityListRead,
    P67GradingOpportunitySnapshotRead,
    P67InvestorDashboardSnapshotRead,
    P67PlatformBuildRead,
    P67PortfolioPerformanceItemRead,
    P67PortfolioPerformanceListRead,
    P67PortfolioPerformanceSnapshotRead,
    P67RecommendationPerformanceItemRead,
    P67RecommendationPerformanceListRead,
    P67RecommendationPerformanceSnapshotRead,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.services.collection_analytics_service import (
    build_collection_analytics_snapshot,
    get_latest_collection_analytics_snapshot,
)
from app.services.grading_analytics_service import (
    build_grading_opportunity_snapshot,
    get_latest_grading_opportunity_snapshot,
    list_grading_opportunity_items,
)
from app.services.investor_dashboard_service import (
    build_investor_dashboard_snapshot,
    get_latest_investor_dashboard_snapshot,
)
from app.services.p67_certification_service import certify_p67_platform
from app.services.p67_feature_flags import (
    p67_collection_analytics_enabled,
    p67_grading_analytics_enabled,
    p67_investor_dashboard_enabled,
    p67_portfolio_analytics_enabled,
    p67_recommendation_performance_enabled,
)
from app.services.p67_platform_service import run_p67_platform_build
from app.services.portfolio_analytics_service import (
    build_portfolio_analytics_snapshot,
    get_latest_portfolio_analytics_snapshot,
    list_portfolio_analytics_items,
)
from app.services.recommendation_performance_service import (
    build_recommendation_performance_snapshot,
    get_latest_recommendation_performance_snapshot,
    list_recommendation_performance_items,
)

portfolio_router = APIRouter(prefix="/api/v1/portfolio-analytics", tags=["P67 Portfolio Analytics"])
collection_router = APIRouter(prefix="/api/v1/collection-analytics", tags=["P67 Collection Analytics"])
recommendation_perf_router = APIRouter(prefix="/api/v1/recommendation-performance", tags=["P67 Recommendation Performance"])
grading_router = APIRouter(prefix="/api/v1/grading-analytics", tags=["P67 Grading Analytics"])
investor_router = APIRouter(prefix="/api/v1/investor-dashboard", tags=["P67 Investor Dashboard"])


def attach_portfolio_analytics_layer(app: FastAPI) -> None:
    app.include_router(portfolio_router)
    app.include_router(collection_router)
    app.include_router(recommendation_perf_router)
    app.include_router(grading_router)
    app.include_router(investor_router)


def _port_guard() -> None:
    if not p67_portfolio_analytics_enabled():
        raise HTTPException(status_code=403, detail="P67_PORTFOLIO_ANALYTICS_DISABLED")


def _coll_guard() -> None:
    if not p67_collection_analytics_enabled():
        raise HTTPException(status_code=403, detail="P67_COLLECTION_ANALYTICS_DISABLED")


def _rec_guard() -> None:
    if not p67_recommendation_performance_enabled():
        raise HTTPException(status_code=403, detail="P67_RECOMMENDATION_PERFORMANCE_DISABLED")


def _grade_guard() -> None:
    if not p67_grading_analytics_enabled():
        raise HTTPException(status_code=403, detail="P67_GRADING_ANALYTICS_DISABLED")


def _inv_guard() -> None:
    if not p67_investor_dashboard_enabled():
        raise HTTPException(status_code=403, detail="P67_INVESTOR_DASHBOARD_DISABLED")


@portfolio_router.get("/latest", response_model=ScanApiV1Envelope)
def portfolio_latest(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> ScanApiV1Envelope:
    _port_guard()
    assert current_user.id is not None
    snap = get_latest_portfolio_analytics_snapshot(session, owner_user_id=int(current_user.id))
    items = list_portfolio_analytics_items(session, snapshot_id=int(snap.id or 0)) if snap else []
    body = P67PortfolioPerformanceListRead(
        snapshot=P67PortfolioPerformanceSnapshotRead.model_validate(snap) if snap else None,
        items=[P67PortfolioPerformanceItemRead.model_validate(i) for i in items],
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@portfolio_router.post("/build", response_model=ScanApiV1Envelope)
def portfolio_build(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> ScanApiV1Envelope:
    _port_guard()
    assert current_user.id is not None
    snap = build_portfolio_analytics_snapshot(session, owner_user_id=int(current_user.id))
    session.commit()
    return wrap_object(P67PortfolioPerformanceSnapshotRead.model_validate(snap), owner_user_id=int(current_user.id))


@portfolio_router.get("/platform/build", response_model=ScanApiV1Envelope)
def portfolio_platform_build_get(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> ScanApiV1Envelope:
    return portfolio_platform_build_post(session, current_user)


@portfolio_router.post("/platform/build", response_model=ScanApiV1Envelope)
def portfolio_platform_build_post(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> ScanApiV1Envelope:
    _port_guard()
    assert current_user.id is not None
    from app.services.collector_page_load_service import _short_error

    try:
        raw = run_p67_platform_build(session, owner_user_id=int(current_user.id))
        cert = certify_p67_platform(session, owner_user_id=int(current_user.id))
        session.commit()
        body = P67PlatformBuildRead(status="OK", message="", steps=raw["steps"], certification=cert)
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        body = P67PlatformBuildRead(
            status="ERROR",
            message=_short_error(exc),
            steps=[],
            certification={},
        )
    return wrap_object(body, owner_user_id=int(current_user.id))


@portfolio_router.get("/platform/certification", response_model=ScanApiV1Envelope)
def portfolio_platform_certification(
    session: Session = Depends(get_session), current_user: User = Depends(get_current_user)
) -> ScanApiV1Envelope:
    _port_guard()
    assert current_user.id is not None
    cert = certify_p67_platform(session, owner_user_id=int(current_user.id))
    return wrap_object(P67CertificationRead(**cert), owner_user_id=int(current_user.id))


@collection_router.get("/latest", response_model=ScanApiV1Envelope)
def collection_latest(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> ScanApiV1Envelope:
    _coll_guard()
    assert current_user.id is not None
    snap = get_latest_collection_analytics_snapshot(session, owner_user_id=int(current_user.id))
    if snap is None:
        body = P67CollectionAnalyticsLatestRead(
            status="EMPTY",
            message="No collection analytics snapshot yet.",
        )
        return wrap_object(body, owner_user_id=int(current_user.id))
    read = P67CollectionAnalyticsSnapshotRead.model_validate(snap)
    body = P67CollectionAnalyticsLatestRead(
        status="OK",
        message="",
        total_holdings=read.total_holdings,
        concentration_score=read.concentration_score,
        metadata_json=dict(read.metadata_json or {}),
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@collection_router.post("/build", response_model=ScanApiV1Envelope)
def collection_build(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> ScanApiV1Envelope:
    _coll_guard()
    assert current_user.id is not None
    snap = build_collection_analytics_snapshot(session, owner_user_id=int(current_user.id))
    session.commit()
    return wrap_object(P67CollectionAnalyticsSnapshotRead.model_validate(snap), owner_user_id=int(current_user.id))


@recommendation_perf_router.get("/latest", response_model=ScanApiV1Envelope)
def recommendation_perf_latest(
    session: Session = Depends(get_session), current_user: User = Depends(get_current_user)
) -> ScanApiV1Envelope:
    _rec_guard()
    assert current_user.id is not None
    snap = get_latest_recommendation_performance_snapshot(session, owner_user_id=int(current_user.id))
    items = list_recommendation_performance_items(session, snapshot_id=int(snap.id or 0)) if snap else []
    body = P67RecommendationPerformanceListRead(
        snapshot=P67RecommendationPerformanceSnapshotRead.model_validate(snap) if snap else None,
        items=[P67RecommendationPerformanceItemRead.model_validate(i) for i in items],
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@recommendation_perf_router.post("/build", response_model=ScanApiV1Envelope)
def recommendation_perf_build(
    session: Session = Depends(get_session), current_user: User = Depends(get_current_user)
) -> ScanApiV1Envelope:
    _rec_guard()
    assert current_user.id is not None
    snap = build_recommendation_performance_snapshot(session, owner_user_id=int(current_user.id))
    session.commit()
    return wrap_object(P67RecommendationPerformanceSnapshotRead.model_validate(snap), owner_user_id=int(current_user.id))


@grading_router.get("/latest", response_model=ScanApiV1Envelope)
def grading_latest(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> ScanApiV1Envelope:
    _grade_guard()
    assert current_user.id is not None
    snap = get_latest_grading_opportunity_snapshot(session, owner_user_id=int(current_user.id))
    items = list_grading_opportunity_items(session, snapshot_id=int(snap.id or 0)) if snap else []
    body = P67GradingOpportunityListRead(
        snapshot=P67GradingOpportunitySnapshotRead.model_validate(snap) if snap else None,
        items=[P67GradingOpportunityItemRead.model_validate(i) for i in items],
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@grading_router.post("/build", response_model=ScanApiV1Envelope)
def grading_build(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> ScanApiV1Envelope:
    _grade_guard()
    assert current_user.id is not None
    snap = build_grading_opportunity_snapshot(session, owner_user_id=int(current_user.id))
    session.commit()
    return wrap_object(P67GradingOpportunitySnapshotRead.model_validate(snap), owner_user_id=int(current_user.id))


@investor_router.get("/latest", response_model=ScanApiV1Envelope)
def investor_latest(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> ScanApiV1Envelope:
    _inv_guard()
    assert current_user.id is not None
    snap = get_latest_investor_dashboard_snapshot(session, owner_user_id=int(current_user.id))
    if snap is None:
        body = P67InvestorDashboardLatestRead(
            status="EMPTY",
            message="No investor dashboard snapshot yet.",
        )
        return wrap_object(body, owner_user_id=int(current_user.id))
    read = P67InvestorDashboardSnapshotRead.model_validate(snap)
    body = P67InvestorDashboardLatestRead(
        status="OK",
        message="",
        collection_value=read.collection_value,
        cost_basis=read.cost_basis,
        unrealized_gain=read.unrealized_gain,
        realized_gain=read.realized_gain,
        portfolio_health_score=read.portfolio_health_score,
        cards_json=dict(read.cards_json or {}),
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@investor_router.post("/build", response_model=ScanApiV1Envelope)
def investor_build(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> ScanApiV1Envelope:
    _inv_guard()
    assert current_user.id is not None
    snap = build_investor_dashboard_snapshot(session, owner_user_id=int(current_user.id))
    session.commit()
    return wrap_object(P67InvestorDashboardSnapshotRead.model_validate(snap), owner_user_id=int(current_user.id))
