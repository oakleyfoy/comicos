"""P74-01 / P74-02 / P74-03 release intelligence monitoring API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.release_monitoring import (
    P74ReleaseChangeListResponse,
    P74ReleaseEventListResponse,
    P74WatchlistMonitoringRead,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.schemas.release_analytics import (
    P74FocAccuracyRead,
    P74ReleaseCategoryListResponse,
)
from app.schemas.release_foc_purchase import (
    P74PurchaseRecommendationListResponse,
    P74RecommendationChangeListResponse,
)
from app.services.release_analytics_service import (
    _compute_categories,
    _compute_foc_accuracy,
    _compute_quantity_accuracy,
    build_release_analytics_dashboard,
    build_release_analytics_read,
    build_release_performance,
)
from app.services.release_intelligence_certification import run_release_intelligence_certification
from app.services.foc_purchase_intelligence_service import (
    build_foc_dashboard,
    build_foc_watch,
    list_purchase_recommendations,
    list_recommendation_changes,
)
from app.services.release_monitoring_service import (
    build_release_monitoring_dashboard,
    build_upcoming_releases,
    build_watchlist_monitoring,
    list_event_history,
    list_recent_changes,
)
from app.services.release_watchlists import list_watchlists

release_monitoring_v1_router = APIRouter(
    prefix="/api/v1",
    tags=["Release Monitoring API v1 (P74-01 / P74-02 / P74-03)"],
)


def attach_release_monitoring_layer(app: FastAPI) -> None:
    app.include_router(release_monitoring_v1_router)


@release_monitoring_v1_router.get("/release-monitoring/upcoming", response_model=ScanApiV1Envelope)
def v1_release_monitoring_upcoming(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_upcoming_releases(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@release_monitoring_v1_router.get("/release-monitoring/changes", response_model=ScanApiV1Envelope)
def v1_release_monitoring_changes(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_recent_changes(
        session, owner_user_id=int(current_user.id), limit=limit, offset=offset
    )
    body = P74ReleaseChangeListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@release_monitoring_v1_router.get("/release-monitoring/history", response_model=ScanApiV1Envelope)
def v1_release_monitoring_history(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_event_history(
        session, owner_user_id=int(current_user.id), limit=limit, offset=offset
    )
    body = P74ReleaseEventListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@release_monitoring_v1_router.get("/release-monitoring/watchlist", response_model=ScanApiV1Envelope)
def v1_release_monitoring_watchlist(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    owner_id = int(current_user.id)
    activity = build_watchlist_monitoring(session, owner_user_id=owner_id)
    watchlists, _ = list_watchlists(session, owner_user_id=owner_id, limit=50, offset=0)
    body = P74WatchlistMonitoringRead(
        watchlists=watchlists,
        activity=activity,
        total_watchlists=len(watchlists),
    )
    return wrap_object(body, owner_user_id=owner_id)


@release_monitoring_v1_router.get("/release-monitoring/foc", response_model=ScanApiV1Envelope)
def v1_release_monitoring_foc(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_foc_watch(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@release_monitoring_v1_router.get("/release-monitoring/purchase-recommendations", response_model=ScanApiV1Envelope)
def v1_release_monitoring_purchase_recommendations(
    limit: int = 50,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items = list_purchase_recommendations(session, owner_user_id=int(current_user.id), limit=limit)
    body = P74PurchaseRecommendationListResponse(items=items, total_items=len(items), limit=limit, offset=0)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@release_monitoring_v1_router.get("/release-monitoring/recommendation-changes", response_model=ScanApiV1Envelope)
def v1_release_monitoring_recommendation_changes(
    limit: int = 50,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items = list_recommendation_changes(session, owner_user_id=int(current_user.id), limit=limit)
    body = P74RecommendationChangeListResponse(items=items, total_items=len(items), limit=limit, offset=0)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@release_monitoring_v1_router.get("/release-monitoring/foc-dashboard", response_model=ScanApiV1Envelope)
def v1_release_monitoring_foc_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_foc_dashboard(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@release_monitoring_v1_router.get("/release-monitoring/dashboard", response_model=ScanApiV1Envelope)
def v1_release_monitoring_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_release_monitoring_dashboard(session, owner_user_id=int(current_user.id), persist=True)
    return wrap_object(body, owner_user_id=int(current_user.id))


@release_monitoring_v1_router.get("/release-monitoring/analytics", response_model=ScanApiV1Envelope)
def v1_release_monitoring_analytics(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_release_analytics_read(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@release_monitoring_v1_router.get("/release-monitoring/performance", response_model=ScanApiV1Envelope)
def v1_release_monitoring_performance(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_release_performance(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@release_monitoring_v1_router.get("/release-monitoring/foc-accuracy", response_model=ScanApiV1Envelope)
def v1_release_monitoring_foc_accuracy(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    owner_id = int(current_user.id)
    foc, _ = _compute_foc_accuracy(session, owner_user_id=owner_id)
    analytics = build_release_analytics_read(session, owner_user_id=owner_id)
    body = P74FocAccuracyRead(
        accuracy_rate_pct=foc.accuracy_rate_pct,
        upgrade_accuracy_pct=foc.upgrade_accuracy_pct,
        downgrade_accuracy_pct=foc.downgrade_accuracy_pct,
        missed_opportunity_rate_pct=foc.missed_opportunity_rate_pct,
        snapshot_id=analytics.snapshot_id,
    )
    return wrap_object(body, owner_user_id=owner_id)


@release_monitoring_v1_router.get("/release-monitoring/categories", response_model=ScanApiV1Envelope)
def v1_release_monitoring_categories(
    limit: int = 100,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    owner_id = int(current_user.id)
    items = _compute_categories(session, owner_user_id=owner_id)
    page = items[offset : offset + limit]
    body = P74ReleaseCategoryListResponse(items=page, total_items=len(items), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=owner_id)


@release_monitoring_v1_router.get("/release-monitoring/certification", response_model=ScanApiV1Envelope)
def v1_release_monitoring_certification(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = run_release_intelligence_certification(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@release_monitoring_v1_router.get("/release-monitoring/analytics-dashboard", response_model=ScanApiV1Envelope)
def v1_release_monitoring_analytics_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    """P74-03 release intelligence analytics dashboard (monitoring dashboard remains at /dashboard)."""
    assert current_user.id is not None
    body = build_release_analytics_dashboard(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))
