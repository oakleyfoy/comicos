"""P82–P84 marketplace acquisition, valuation, notifications, command center APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.p82_p84_collector_expansion import (
    BriefingGenerateRead,
    CollectorBriefingRead,
    CollectorCommandCenterRead,
    CollectorExpansionCertificationRead,
    CollectorNotificationDashboardRead,
    CollectorNotificationListResponse,
    CollectorNotificationRead,
    CollectorNotificationUpdate,
    CollectionForecastRead,
    CollectionOptimizationRead,
    CollectionRiskRead,
    CollectionScenarioRead,
    CollectionScenarioRequest,
    CollectionValuationDashboardRead,
    MarketplaceAcquisitionDashboardRead,
    MarketplaceAcquisitionListResponse,
    MarketplaceAcquisitionOpportunityRead,
    MarketplaceAcquisitionScanPayload,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.collector_briefing_service import generate_daily_briefing, generate_weekly_briefing
from app.services.collector_page_load_service import (
    fast_build_collector_command_center,
    fast_get_daily_briefing,
    fast_get_weekly_briefing,
    fast_list_collector_notifications,
    safe_command_center_fallback,
    safe_notifications_fallback,
)
from app.services.collector_expansion_certification import run_collector_expansion_certification
from app.services.collector_notification_service import (
    build_notification_dashboard,
    list_collector_notifications,
    update_collector_notification,
)
from app.services.collection_scenario_service import run_collection_scenario
from app.services.collection_valuation_service import (
    build_collection_forecast,
    build_collection_optimization,
    build_collection_risk,
    build_valuation_dashboard,
)
from app.services.marketplace_acquisition_service import (
    build_acquisition_dashboard,
    get_acquisition_opportunity,
    list_acquisition_opportunities,
    scan_marketplace_listing,
)

p82_p84_router = APIRouter(tags=["Collector Expansion API v1 (P82–P84)"])


def attach_p82_p84_collector_expansion_layer(app: FastAPI) -> None:
    app.include_router(p82_p84_router)


@p82_p84_router.get("/api/v1/marketplace-acquisition/opportunities", response_model=ScanApiV1Envelope)
def v1_list_marketplace_acquisition_opportunities(
    recommendation: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    refresh: bool = Query(False),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    from app.services.nav_route_safe_get import fast_marketplace_opportunities_list

    body: MarketplaceAcquisitionListResponse = fast_marketplace_opportunities_list(
        session,
        owner_user_id=int(current_user.id),
        recommendation=recommendation,
        limit=limit,
        offset=offset,
        refresh=refresh,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@p82_p84_router.get("/api/v1/marketplace-acquisition/opportunities/{opportunity_id}", response_model=ScanApiV1Envelope)
def v1_get_marketplace_acquisition_opportunity(
    opportunity_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: MarketplaceAcquisitionOpportunityRead = get_acquisition_opportunity(
        session, owner_user_id=int(current_user.id), opportunity_id=opportunity_id
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@p82_p84_router.post("/api/v1/marketplace-acquisition/scan", response_model=ScanApiV1Envelope)
def v1_scan_marketplace_acquisition(
    payload: MarketplaceAcquisitionScanPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = scan_marketplace_listing(session, owner_user_id=int(current_user.id), payload=payload, persist=True)
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p82_p84_router.get("/api/v1/marketplace-acquisition/dashboard", response_model=ScanApiV1Envelope)
def v1_marketplace_acquisition_dashboard(
    refresh: bool = Query(True),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: MarketplaceAcquisitionDashboardRead = build_acquisition_dashboard(
        session, owner_user_id=int(current_user.id), refresh=refresh
    )
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p82_p84_router.get("/api/v1/collection-valuation/forecast", response_model=ScanApiV1Envelope)
def v1_collection_forecast(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: CollectionForecastRead = build_collection_forecast(session, owner_user_id=int(current_user.id), persist=True)
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p82_p84_router.get("/api/v1/collection-valuation/risk", response_model=ScanApiV1Envelope)
def v1_collection_risk(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: CollectionRiskRead = build_collection_risk(session, owner_user_id=int(current_user.id), persist=True)
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p82_p84_router.post("/api/v1/collection-valuation/scenario", response_model=ScanApiV1Envelope)
def v1_collection_scenario(
    payload: CollectionScenarioRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: CollectionScenarioRead = run_collection_scenario(
        session, owner_user_id=int(current_user.id), scenario_type=payload.scenario_type
    )
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p82_p84_router.get("/api/v1/collection-valuation/optimization", response_model=ScanApiV1Envelope)
def v1_collection_optimization(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: CollectionOptimizationRead = build_collection_optimization(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@p82_p84_router.get("/api/v1/collection-valuation/dashboard", response_model=ScanApiV1Envelope)
def v1_collection_valuation_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    from app.services.nav_route_safe_get import fast_valuation_dashboard

    body: CollectionValuationDashboardRead = fast_valuation_dashboard(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@p82_p84_router.get("/api/v1/notifications", response_model=ScanApiV1Envelope)
def v1_list_notifications(
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    refresh: bool = Query(False),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    owner_user_id = int(current_user.id)
    if refresh:
        body = safe_notifications_fallback(
            limit=limit,
            offset=offset,
            message="Live notification refresh disabled on page load; use ops jobs or POST flows.",
        )
    else:
        try:
            body = fast_list_collector_notifications(
                session,
                owner_user_id=owner_user_id,
                status=status,
                limit=limit,
                offset=offset,
            )
        except Exception as exc:  # noqa: BLE001
            body = safe_notifications_fallback(limit=limit, offset=offset, message=str(exc))
    return wrap_standard_list(body, owner_user_id=owner_user_id)


@p82_p84_router.put("/api/v1/notifications/{notification_id}", response_model=ScanApiV1Envelope)
def v1_update_notification(
    notification_id: int,
    payload: CollectorNotificationUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: CollectorNotificationRead = update_collector_notification(
        session,
        owner_user_id=int(current_user.id),
        notification_id=notification_id,
        payload=payload,
    )
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p82_p84_router.get("/api/v1/notifications/dashboard", response_model=ScanApiV1Envelope)
def v1_notifications_dashboard(
    refresh: bool = Query(True),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: CollectorNotificationDashboardRead = build_notification_dashboard(
        session, owner_user_id=int(current_user.id), refresh=refresh
    )
    if refresh:
        session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p82_p84_router.get("/api/v1/briefings/daily", response_model=ScanApiV1Envelope)
def v1_daily_briefing(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: CollectorBriefingRead = fast_get_daily_briefing(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@p82_p84_router.get("/api/v1/briefings/weekly", response_model=ScanApiV1Envelope)
def v1_weekly_briefing(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: CollectorBriefingRead = fast_get_weekly_briefing(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@p82_p84_router.post("/api/v1/briefings/generate", response_model=ScanApiV1Envelope)
def v1_generate_briefings(
    briefing_type: str = Query("BOTH"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    kind = briefing_type.strip().upper()
    daily_body = None
    weekly_body = None
    if kind in {"DAILY", "BOTH"}:
        daily_body = generate_daily_briefing(session, owner_user_id=int(current_user.id))
    if kind in {"WEEKLY", "BOTH"}:
        weekly_body = generate_weekly_briefing(session, owner_user_id=int(current_user.id))
    session.commit()
    body = BriefingGenerateRead(daily=daily_body, weekly=weekly_body)
    return wrap_object(body, owner_user_id=int(current_user.id))


@p82_p84_router.get("/api/v1/collector-command-center", response_model=ScanApiV1Envelope)
def v1_collector_command_center(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    owner_user_id = int(current_user.id)
    try:
        body: CollectorCommandCenterRead = fast_build_collector_command_center(session, owner_user_id=owner_user_id)
    except Exception as exc:  # noqa: BLE001
        body = safe_command_center_fallback(str(exc))
    return wrap_object(body, owner_user_id=owner_user_id)


@p82_p84_router.get("/api/v1/collector-expansion/certification", response_model=ScanApiV1Envelope)
def v1_collector_expansion_certification(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: CollectorExpansionCertificationRead = run_collector_expansion_certification(
        session, owner_user_id=int(current_user.id)
    )
    return wrap_object(body, owner_user_id=int(current_user.id))
