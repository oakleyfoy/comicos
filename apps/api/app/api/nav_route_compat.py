"""GET compatibility routes for visible nav smoke tests (aliases only; no duplicate business logic)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.models.photo_import import PhotoImportSession
from app.models.receiving import ReceivingSession
from app.schemas.p89_market_pricing import P89MarketPriceSnapshotRead, P89MarketPricingDashboardRead
from app.schemas.p90_fmv_v2 import P90FmvIntelligenceDashboardRead
from app.schemas.release_lifecycle import P86ReleaseLifecycleDashboardRead
from app.schemas.p82_p84_collector_expansion import MarketplaceAcquisitionListResponse
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list, build_meta
from app.services.fmv_v2_dashboard_service import build_fmv_intelligence_dashboard
from app.services.gmail_ingestion import get_gmail_status_for_user
from app.services.nav_route_safe_get import fast_marketplace_opportunities_list
from app.services.p89_market_pricing_service import latest_snapshots_for_owner, snapshot_to_read_dict
from app.services.photo_import_session_service import session_to_read
from app.services.release_lifecycle_service import build_lifecycle_dashboard
from app.services.marketplace.marketplace_alert_service import list_marketplace_alerts
from app.services.marketplace.marketplace_saved_search_service import list_saved_searches
from app.services.retailer_accounts import list_retailer_accounts

nav_compat_router = APIRouter(tags=["Nav route GET compatibility"])


def attach_nav_route_compat_layer(app: FastAPI) -> None:
    app.include_router(nav_compat_router)


@nav_compat_router.get("/api/v1/buy-opportunities", response_model=ScanApiV1Envelope)
def v1_buy_opportunities_nav_get(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: MarketplaceAcquisitionListResponse = fast_marketplace_opportunities_list(
        session,
        owner_user_id=int(current_user.id),
        recommendation=None,
        limit=limit,
        offset=offset,
        refresh=False,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@nav_compat_router.get("/api/v1/marketplace-monitoring", response_model=ScanApiV1Envelope)
def v1_marketplace_monitoring_nav_get(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    uid = int(current_user.id)
    searches = list_saved_searches(session, owner_user_id=uid, limit=20, offset=0)
    alerts = list_marketplace_alerts(session, owner_user_id=uid, limit=20, offset=0, status=None)
    data = {
        "saved_searches": [s.model_dump(mode="json") for s in searches.items],
        "saved_search_count": searches.total_items,
        "alerts": [a.model_dump(mode="json") for a in alerts.items],
        "alert_count": alerts.total_items,
        "status": "OK",
    }
    return ScanApiV1Envelope(data=data, meta=build_meta(owner_user_id=uid))


@nav_compat_router.get("/api/v1/fmv-intelligence/dashboard", response_model=ScanApiV1Envelope)
def v1_fmv_intelligence_dashboard_alias(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P90FmvIntelligenceDashboardRead = build_fmv_intelligence_dashboard(
        session, owner_user_id=int(current_user.id)
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@nav_compat_router.get("/api/v1/market-pricing", response_model=ScanApiV1Envelope)
def v1_market_pricing_nav_get(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(8, ge=1, le=50),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    uid = int(current_user.id)
    rows = latest_snapshots_for_owner(session, owner_user_id=uid, limit=500)

    def _read(row) -> P89MarketPriceSnapshotRead:
        return P89MarketPriceSnapshotRead(**snapshot_to_read_dict(row))

    body = P89MarketPricingDashboardRead(
        highest_value_books=[_read(r) for r in sorted(rows, key=lambda x: x.market_price, reverse=True)[:limit]],
        fastest_selling_books=[],
    )
    return wrap_object(body, owner_user_id=uid)


@nav_compat_router.get("/api/v1/release-lifecycle", response_model=ScanApiV1Envelope)
def v1_release_lifecycle_nav_get(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P86ReleaseLifecycleDashboardRead = build_lifecycle_dashboard(session, owner_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@nav_compat_router.get("/api/v1/settings/integrations")
def v1_settings_integrations_get(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    gmail = get_gmail_status_for_user(session=session, current_user=current_user)
    return {"gmail": gmail.model_dump(), "status": "OK"}


@nav_compat_router.get("/api/v1/settings/connected-retailers")
def v1_settings_connected_retailers_get(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    assert current_user.id is not None
    accounts = list_retailer_accounts(session, owner_user_id=int(current_user.id))
    return {
        "items": [{"id": int(a.id or 0), "retailer": a.retailer, "display_name": a.display_name} for a in accounts],
        "total_items": len(accounts),
        "status": "OK",
    }


@nav_compat_router.get("/api/v1/photo-import/sessions")
def v1_photo_import_sessions_list_get(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    assert current_user.id is not None
    rows = session.exec(
        select(PhotoImportSession)
        .where(PhotoImportSession.user_id == int(current_user.id))
        .order_by(PhotoImportSession.created_at.desc())
        .limit(limit)
    ).all()
    return {
        "items": [session_to_read(r).model_dump() for r in rows],
        "total_items": len(rows),
        "status": "OK",
    }


@nav_compat_router.get("/api/v1/gpt-comic-read")
def v1_gpt_comic_read_status_get(
    current_user: User = Depends(get_current_user),
) -> dict:
    del current_user
    return {
        "status": "OK",
        "method": "POST",
        "message": "Upload a cover image via POST multipart/form-data field image.",
    }


@nav_compat_router.get("/api/v1/receiving/session")
def v1_receiving_session_list_get(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(10, ge=1, le=50),
) -> dict:
    assert current_user.id is not None
    rows = session.exec(
        select(ReceivingSession)
        .where(ReceivingSession.owner_user_id == int(current_user.id))
        .order_by(ReceivingSession.created_at.desc())
        .limit(limit)
    ).all()
    return {
        "items": [{"id": int(r.id or 0), "status": r.status} for r in rows],
        "total_items": len(rows),
        "status": "OK",
    }
