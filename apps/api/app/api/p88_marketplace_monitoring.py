"""P88-03 marketplace monitoring APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.p88_marketplace_monitoring import (
    MarketplaceAlertListResponse,
    MarketplaceAlertUpdatePayload,
    MarketplaceMonitoringRunListResponse,
    MarketplaceSavedSearchCreatePayload,
    MarketplaceSavedSearchDeleteResponse,
    MarketplaceSavedSearchListResponse,
    MarketplaceSavedSearchRunResponse,
    MarketplaceSavedSearchUpdatePayload,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.marketplace.marketplace_alert_service import list_marketplace_alerts, update_marketplace_alert
from app.services.marketplace.marketplace_saved_search_service import (
    create_saved_search,
    delete_saved_search,
    list_monitoring_runs,
    list_saved_searches,
    run_saved_search_by_id,
    update_saved_search,
)
from app.schemas.p88_marketplace_monitoring import MarketplaceAlertRead, MarketplaceSavedSearchRead

p88_monitoring_router = APIRouter(tags=["Marketplace Monitoring (P88-03)"])


def attach_p88_marketplace_monitoring_layer(app: FastAPI) -> None:
    app.include_router(p88_monitoring_router)


@p88_monitoring_router.get("/api/v1/marketplace-monitoring/saved-searches", response_model=ScanApiV1Envelope)
def v1_list_saved_searches(
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: MarketplaceSavedSearchListResponse = list_saved_searches(
        session, owner_user_id=int(current_user.id), limit=limit, offset=offset
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@p88_monitoring_router.post("/api/v1/marketplace-monitoring/saved-searches", response_model=ScanApiV1Envelope)
def v1_create_saved_search(
    payload: MarketplaceSavedSearchCreatePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: MarketplaceSavedSearchRead = create_saved_search(
        session, owner_user_id=int(current_user.id), payload=payload
    )
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p88_monitoring_router.patch(
    "/api/v1/marketplace-monitoring/saved-searches/{saved_search_id}",
    response_model=ScanApiV1Envelope,
)
def v1_update_saved_search(
    saved_search_id: int,
    payload: MarketplaceSavedSearchUpdatePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: MarketplaceSavedSearchRead = update_saved_search(
        session,
        owner_user_id=int(current_user.id),
        saved_search_id=saved_search_id,
        payload=payload,
    )
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p88_monitoring_router.delete("/api/v1/marketplace-monitoring/saved-searches/{saved_search_id}", response_model=ScanApiV1Envelope)
def v1_delete_saved_search(
    saved_search_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    delete_saved_search(session, owner_user_id=int(current_user.id), saved_search_id=saved_search_id)
    session.commit()
    body = MarketplaceSavedSearchDeleteResponse(deleted=True, id=saved_search_id)
    return wrap_object(body, owner_user_id=int(current_user.id))


@p88_monitoring_router.post(
    "/api/v1/marketplace-monitoring/saved-searches/{saved_search_id}/run",
    response_model=ScanApiV1Envelope,
)
def v1_run_saved_search(
    saved_search_id: int,
    dry_run: bool = Query(False),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: MarketplaceSavedSearchRunResponse = run_saved_search_by_id(
        session,
        owner_user_id=int(current_user.id),
        saved_search_id=saved_search_id,
        dry_run=dry_run,
    )
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p88_monitoring_router.get("/api/v1/marketplace-monitoring/alerts", response_model=ScanApiV1Envelope)
def v1_list_marketplace_alerts(
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: MarketplaceAlertListResponse = list_marketplace_alerts(
        session,
        owner_user_id=int(current_user.id),
        status=status,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@p88_monitoring_router.patch("/api/v1/marketplace-monitoring/alerts/{alert_id}", response_model=ScanApiV1Envelope)
def v1_update_marketplace_alert(
    alert_id: int,
    payload: MarketplaceAlertUpdatePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: MarketplaceAlertRead = update_marketplace_alert(
        session,
        owner_user_id=int(current_user.id),
        alert_id=alert_id,
        payload=payload,
    )
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p88_monitoring_router.get("/api/v1/marketplace-monitoring/runs", response_model=ScanApiV1Envelope)
def v1_list_monitoring_runs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: MarketplaceMonitoringRunListResponse = list_monitoring_runs(
        session, owner_user_id=int(current_user.id), limit=limit, offset=offset
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))
