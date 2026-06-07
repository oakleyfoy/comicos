"""P81 discovery feed, personalization, watchlists, and alerts APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.p81_discovery import P81DiscoveryFeedRead, P81DiscoveryOpportunityListResponse
from app.schemas.p81_discovery_personalization import (
    P81DiscoveryAlertListResponse,
    P81DiscoveryAlertUpdate,
    P81DiscoveryWatchlistCreate,
    P81DiscoveryWatchlistListResponse,
    P81DiscoveryWatchlistUpdate,
    P81FuturePullListResponse,
    P81PersonalizedDiscoveryDashboardRead,
    P81PersonalizedDiscoveryListResponse,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.schemas.p81_discovery_analytics import (
    P81DiscoveryAlertAnalyticsRead,
    P81DiscoveryAnalyticsDashboardRead,
    P81DiscoveryAnalyticsRead,
    P81DiscoveryCertificationRead,
    P81DiscoveryOpportunityAnalyticsRead,
    P81DiscoveryRoiAnalyticsRead,
)
from app.services.discovery_certification import run_discovery_certification
from app.services.p81_discovery_analytics_service import (
    build_alert_analytics,
    build_analytics_dashboard,
    build_discovery_analytics,
    build_opportunity_analytics,
    build_roi_analytics,
)
from app.services.p81_discovery_personalization_service import (
    build_personalized_discovery_dashboard,
    create_watchlist,
    list_alerts,
    list_future_pull_list,
    list_personalized_discovery,
    list_watchlists,
    update_alert,
    update_watchlist,
)
from app.services.p81_discovery_service import build_discovery_feed, get_opportunity, list_opportunities

p81_discovery_v1_router = APIRouter(tags=["Discovery API v1 (P81)"])


def attach_p81_discovery_layer(app: FastAPI) -> None:
    app.include_router(p81_discovery_v1_router)


@p81_discovery_v1_router.get("/api/v1/discovery/feed", response_model=ScanApiV1Envelope)
def v1_discovery_feed(
    refresh: bool = Query(False),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    from app.services.nav_route_safe_get import fast_discovery_feed

    body: P81DiscoveryFeedRead = fast_discovery_feed(session, owner_user_id=int(current_user.id), refresh=refresh)
    return wrap_object(body, owner_user_id=int(current_user.id))


@p81_discovery_v1_router.get("/api/v1/discovery/opportunities", response_model=ScanApiV1Envelope)
def v1_discovery_opportunities(
    opportunity_type: str | None = Query(None),
    score_category: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    refresh: bool = Query(False),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P81DiscoveryOpportunityListResponse = list_opportunities(
        session,
        owner_user_id=int(current_user.id),
        opportunity_type=opportunity_type,
        score_category=score_category,
        limit=limit,
        offset=offset,
        refresh=refresh,
    )
    if refresh:
        session.commit()
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@p81_discovery_v1_router.get("/api/v1/discovery/opportunities/{opportunity_id}", response_model=ScanApiV1Envelope)
def v1_discovery_opportunity_detail(
    opportunity_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_opportunity(session, owner_user_id=int(current_user.id), opportunity_id=opportunity_id)
    return wrap_object(body, owner_user_id=int(current_user.id))


@p81_discovery_v1_router.get("/api/v1/discovery/personalized", response_model=ScanApiV1Envelope)
def v1_discovery_personalized(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    refresh: bool = Query(False),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    from app.services.nav_route_safe_get import fast_discovery_personalized_list

    body: P81PersonalizedDiscoveryListResponse = fast_discovery_personalized_list(
        session,
        owner_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
        refresh=refresh,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@p81_discovery_v1_router.post("/api/v1/discovery/personalized/refresh", response_model=ScanApiV1Envelope)
def v1_discovery_personalized_refresh(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P81PersonalizedDiscoveryListResponse = list_personalized_discovery(
        session,
        owner_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
        refresh=True,
    )
    session.commit()
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@p81_discovery_v1_router.get("/api/v1/discovery/dashboard", response_model=ScanApiV1Envelope)
def v1_discovery_dashboard(
    refresh: bool = Query(False),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    from app.services.nav_route_safe_get import fast_discovery_dashboard

    body: P81PersonalizedDiscoveryDashboardRead = fast_discovery_dashboard(
        session, owner_user_id=int(current_user.id), refresh=refresh
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@p81_discovery_v1_router.post("/api/v1/discovery/dashboard/refresh", response_model=ScanApiV1Envelope)
def v1_discovery_dashboard_refresh(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P81PersonalizedDiscoveryDashboardRead = build_personalized_discovery_dashboard(
        session, owner_user_id=int(current_user.id), refresh=True
    )
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p81_discovery_v1_router.get("/api/v1/discovery/watchlists", response_model=ScanApiV1Envelope)
def v1_discovery_watchlists(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P81DiscoveryWatchlistListResponse = list_watchlists(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@p81_discovery_v1_router.post(
    "/api/v1/discovery/watchlists",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_create_discovery_watchlist(
    payload: P81DiscoveryWatchlistCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = create_watchlist(session, owner_user_id=int(current_user.id), payload=payload)
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p81_discovery_v1_router.put("/api/v1/discovery/watchlists/{watchlist_id}", response_model=ScanApiV1Envelope)
def v1_update_discovery_watchlist(
    watchlist_id: int,
    payload: P81DiscoveryWatchlistUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = update_watchlist(
        session, owner_user_id=int(current_user.id), watchlist_id=watchlist_id, payload=payload
    )
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p81_discovery_v1_router.get("/api/v1/discovery/alerts", response_model=ScanApiV1Envelope)
def v1_discovery_alerts(
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P81DiscoveryAlertListResponse = list_alerts(
        session,
        owner_user_id=int(current_user.id),
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@p81_discovery_v1_router.put("/api/v1/discovery/alerts/{alert_id}", response_model=ScanApiV1Envelope)
def v1_update_discovery_alert(
    alert_id: int,
    payload: P81DiscoveryAlertUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = update_alert(session, owner_user_id=int(current_user.id), alert_id=alert_id, payload=payload)
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p81_discovery_v1_router.get("/api/v1/discovery/future-pull-list", response_model=ScanApiV1Envelope)
def v1_future_pull_list(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    refresh: bool = Query(False),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    from app.services.nav_route_safe_get import fast_future_pull_list

    body: P81FuturePullListResponse = fast_future_pull_list(
        session,
        owner_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
        refresh=refresh,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@p81_discovery_v1_router.get("/api/v1/discovery/analytics", response_model=ScanApiV1Envelope)
def v1_discovery_analytics(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P81DiscoveryAnalyticsRead = build_discovery_analytics(session, owner_user_id=int(current_user.id), persist=True)
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p81_discovery_v1_router.get("/api/v1/discovery/opportunity-analytics", response_model=ScanApiV1Envelope)
def v1_discovery_opportunity_analytics(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P81DiscoveryOpportunityAnalyticsRead = build_opportunity_analytics(
        session, owner_user_id=int(current_user.id), persist=True
    )
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p81_discovery_v1_router.get("/api/v1/discovery/alert-analytics", response_model=ScanApiV1Envelope)
def v1_discovery_alert_analytics(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P81DiscoveryAlertAnalyticsRead = build_alert_analytics(session, owner_user_id=int(current_user.id), persist=True)
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p81_discovery_v1_router.get("/api/v1/discovery/roi-analytics", response_model=ScanApiV1Envelope)
def v1_discovery_roi_analytics(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P81DiscoveryRoiAnalyticsRead = build_roi_analytics(session, owner_user_id=int(current_user.id), persist=True)
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p81_discovery_v1_router.get("/api/v1/discovery/analytics-dashboard", response_model=ScanApiV1Envelope)
def v1_discovery_analytics_dashboard(
    refresh: bool = Query(False),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    from app.services.nav_route_safe_get import fast_discovery_analytics_dashboard

    body: P81DiscoveryAnalyticsDashboardRead = fast_discovery_analytics_dashboard(
        session, owner_user_id=int(current_user.id), refresh=refresh
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@p81_discovery_v1_router.post("/api/v1/discovery/analytics-dashboard/refresh", response_model=ScanApiV1Envelope)
def v1_discovery_analytics_dashboard_refresh(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P81DiscoveryAnalyticsDashboardRead = build_analytics_dashboard(
        session, owner_user_id=int(current_user.id), refresh=True
    )
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p81_discovery_v1_router.get("/api/v1/discovery/certification", response_model=ScanApiV1Envelope)
def v1_discovery_certification(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P81DiscoveryCertificationRead = run_discovery_certification(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))
