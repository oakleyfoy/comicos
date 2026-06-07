"""P68 Market Pricing Engine APIs (/api/v1/market-pricing/*)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.ebay_comp_import import EbayCompImportRequest, EbayCompImportSummaryResponse
from app.schemas.ebay_sold_search import EbaySoldSearchPreviewResponse
from app.schemas.market_pricing_engine import (
    P68CertificationRead,
    P68ManualObservationWrite,
    P68ObservationRead,
    P68ObservationsListRead,
    P68ProviderRead,
    P68ProvidersListRead,
    P68SnapshotRead,
    P68SnapshotsBuildRead,
    P68SnapshotsListRead,
    P70MarketRefreshHistoryRead,
    P70MarketRefreshRunRead,
    P70MarketTrendPointRead,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.services.ebay_oauth import EbayOAuthAuthenticationError, EbayOAuthConfigurationError
from app.services.ebay_sold_search_service import (
    EbaySoldSearchApiError,
    EbaySoldSearchConfigurationError,
    EbaySoldSearchError,
    fetch_ebay_sold_search_payload,
    search_ebay_sold_listings,
)
from app.services.ebay_comp_import_service import import_ebay_comp_results
from app.services.market_pricing_provider_health import provider_readiness
from app.services.market_pricing_provider_registry import ensure_provider_registry
from app.services.market_pricing_engine_service import (
    add_manual_observation,
    build_market_price_snapshots,
    get_latest_p68_snapshots,
    list_observations,
)
from app.services.market_refresh_service import list_refresh_runs, run_market_refresh_for_owner
from app.services.market_trend_history_service import list_trend_points_for_copy
from app.services.p68_certification_service import certify_p68_market_pricing
from app.services.p68_feature_flags import p68_manual_fmv_enabled, p68_market_pricing_enabled
from app.services.p68_snapshot_read import p68_snapshot_to_read

p68_pricing_router = APIRouter(prefix="/api/v1/market-pricing", tags=["P68 Market Pricing"])


def attach_market_pricing_engine_layer(app: FastAPI) -> None:
    app.include_router(p68_pricing_router)


def _guard() -> None:
    if not p68_market_pricing_enabled():
        raise HTTPException(status_code=403, detail="P68_MARKET_PRICING_DISABLED")


@p68_pricing_router.get("/providers", response_model=ScanApiV1Envelope)
def providers(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> ScanApiV1Envelope:
    _guard()
    assert current_user.id is not None
    rows = ensure_provider_registry(session, owner_user_id=int(current_user.id))
    session.commit()
    body = [P68ProviderRead.model_validate(r) for r in rows]
    return wrap_object(P68ProvidersListRead(providers=body), owner_user_id=int(current_user.id))


@p68_pricing_router.get("/providers/health", response_model=ScanApiV1Envelope)
def providers_health(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> ScanApiV1Envelope:
    _guard()
    assert current_user.id is not None
    rows = provider_readiness(session, owner_user_id=int(current_user.id))
    session.commit()
    body = [P68ProviderRead.model_validate(row) for row in rows]
    return wrap_object(P68ProvidersListRead(providers=body), owner_user_id=int(current_user.id))


@p68_pricing_router.get("/ebay/sold-search", response_model=ScanApiV1Envelope)
def ebay_sold_search(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    q: str | None = None,
    title: str | None = None,
    series: str | None = None,
    issue_number: str | None = None,
    variant: str | None = None,
    publisher: str | None = None,
    upc: str | None = None,
    condition: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> ScanApiV1Envelope:
    _guard()
    assert current_user.id is not None
    try:
        body = search_ebay_sold_listings(
            q=q,
            title=title,
            series=series,
            issue_number=issue_number,
            variant=variant,
            publisher=publisher,
            upc=upc,
            condition=condition,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (EbayOAuthConfigurationError, EbayOAuthAuthenticationError, EbaySoldSearchConfigurationError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (EbaySoldSearchApiError, EbaySoldSearchError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return wrap_object(EbaySoldSearchPreviewResponse.model_validate(body), owner_user_id=int(current_user.id))


@p68_pricing_router.post("/ebay/import", response_model=ScanApiV1Envelope)
def ebay_comp_import(
    payload: EbayCompImportRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    _guard()
    assert current_user.id is not None
    try:
        raw_payload, search_request = fetch_ebay_sold_search_payload(
            title=payload.title,
            series=payload.series,
            issue_number=payload.issue_number,
            variant=payload.variant,
            publisher=payload.publisher,
            upc=payload.upc,
            condition=payload.condition,
            limit=payload.limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (EbayOAuthConfigurationError, EbayOAuthAuthenticationError, EbaySoldSearchConfigurationError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (EbaySoldSearchApiError, EbaySoldSearchError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    summary = import_ebay_comp_results(
        session,
        owner_user_id=int(current_user.id),
        search_request=search_request,
        search_payload=raw_payload,
        search_criteria=payload.model_dump(mode="json", exclude_none=True),
    )
    session.commit()
    return wrap_object(EbayCompImportSummaryResponse.model_validate(summary), owner_user_id=int(current_user.id))


@p68_pricing_router.get("/observations", response_model=ScanApiV1Envelope)
def observations(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> ScanApiV1Envelope:
    _guard()
    assert current_user.id is not None
    rows = list_observations(session, owner_user_id=int(current_user.id))
    body = [P68ObservationRead.model_validate(r) for r in rows]
    return wrap_object(P68ObservationsListRead(items=body, total=len(body)), owner_user_id=int(current_user.id))


@p68_pricing_router.get("/snapshots/latest", response_model=ScanApiV1Envelope)
def snapshots_latest(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> ScanApiV1Envelope:
    _guard()
    assert current_user.id is not None
    from app.services.collector_page_load_service import _short_error

    try:
        rows = get_latest_p68_snapshots(session, owner_user_id=int(current_user.id))
        body_items = [p68_snapshot_to_read(r) for r in rows]
        status = "OK" if body_items else "EMPTY"
        message = "" if body_items else "No market pricing snapshots yet."
        payload = P68SnapshotsListRead(status=status, message=message, items=body_items, total=len(body_items))
    except Exception as exc:  # noqa: BLE001
        payload = P68SnapshotsListRead(
            status="EMPTY",
            message=_short_error(exc),
            items=[],
            total=0,
        )
    return wrap_object(payload, owner_user_id=int(current_user.id))


@p68_pricing_router.post("/snapshots/build", response_model=ScanApiV1Envelope)
def snapshots_build(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> ScanApiV1Envelope:
    _guard()
    assert current_user.id is not None
    from app.services.collector_page_load_service import _short_error

    try:
        snaps = build_market_price_snapshots(session, owner_user_id=int(current_user.id))
        session.commit()
        body = [p68_snapshot_to_read(s) for s in snaps]
        payload = P68SnapshotsBuildRead(status="OK", message="", built=len(body), items=body)
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        payload = P68SnapshotsBuildRead(
            status="ERROR",
            message=_short_error(exc),
            built=0,
            items=[],
        )
    return wrap_object(payload, owner_user_id=int(current_user.id))


@p68_pricing_router.post("/refresh/run", response_model=ScanApiV1Envelope)
def market_refresh_run(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> ScanApiV1Envelope:
    _guard()
    assert current_user.id is not None
    run = run_market_refresh_for_owner(session, owner_user_id=int(current_user.id), trigger_type="MANUAL")
    session.commit()
    return wrap_object(P70MarketRefreshRunRead.model_validate(run), owner_user_id=int(current_user.id))


@p68_pricing_router.get("/refresh/history", response_model=ScanApiV1Envelope)
def market_refresh_history(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ScanApiV1Envelope:
    _guard()
    assert current_user.id is not None
    rows = list_refresh_runs(session, owner_user_id=int(current_user.id), limit=limit)
    items = [P70MarketRefreshRunRead.model_validate(r) for r in rows]
    return wrap_object(P70MarketRefreshHistoryRead(items=items, total=len(items)), owner_user_id=int(current_user.id))


@p68_pricing_router.get("/trend/{inventory_copy_id}", response_model=ScanApiV1Envelope)
def market_trend_history(
    inventory_copy_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: Annotated[int, Query(ge=1, le=365)] = 90,
) -> ScanApiV1Envelope:
    _guard()
    assert current_user.id is not None
    rows = list_trend_points_for_copy(
        session,
        owner_user_id=int(current_user.id),
        inventory_copy_id=inventory_copy_id,
        limit=limit,
    )
    items = [P70MarketTrendPointRead.model_validate(r) for r in rows]
    return wrap_object({"items": items, "total": len(items)}, owner_user_id=int(current_user.id))


@p68_pricing_router.post("/manual", response_model=ScanApiV1Envelope)
def manual_observation(
    payload: P68ManualObservationWrite,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    _guard()
    if not p68_manual_fmv_enabled():
        raise HTTPException(status_code=403, detail="P68_MANUAL_FMV_DISABLED")
    assert current_user.id is not None
    obs = add_manual_observation(session, owner_user_id=int(current_user.id), **payload.model_dump())
    session.commit()
    return wrap_object(P68ObservationRead.model_validate(obs), owner_user_id=int(current_user.id))


@p68_pricing_router.get("/certification", response_model=ScanApiV1Envelope)
def certification(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> ScanApiV1Envelope:
    _guard()
    assert current_user.id is not None
    cert = certify_p68_market_pricing(session, owner_user_id=int(current_user.id))
    return wrap_object(P68CertificationRead(**cert), owner_user_id=int(current_user.id))
