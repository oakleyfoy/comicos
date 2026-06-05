"""P68 Market Pricing Engine APIs (/api/v1/market-pricing/*)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
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
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.services.market_pricing_provider_registry import ensure_provider_registry
from app.services.market_pricing_engine_service import (
    add_manual_observation,
    build_market_price_snapshots,
    get_latest_p68_snapshots,
    list_observations,
)
from app.services.p68_certification_service import certify_p68_market_pricing
from app.services.p68_feature_flags import p68_manual_fmv_enabled, p68_market_pricing_enabled

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
    rows = get_latest_p68_snapshots(session, owner_user_id=int(current_user.id))
    body = [P68SnapshotRead.model_validate(r) for r in rows]
    return wrap_object(P68SnapshotsListRead(items=body, total=len(body)), owner_user_id=int(current_user.id))


@p68_pricing_router.post("/snapshots/build", response_model=ScanApiV1Envelope)
def snapshots_build(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> ScanApiV1Envelope:
    _guard()
    assert current_user.id is not None
    snaps = build_market_price_snapshots(session, owner_user_id=int(current_user.id))
    session.commit()
    body = [P68SnapshotRead.model_validate(s) for s in snaps]
    return wrap_object(P68SnapshotsBuildRead(built=len(body), items=body), owner_user_id=int(current_user.id))


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
