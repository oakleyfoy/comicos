"""P90-02 FMV Intelligence V2 API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI
from sqlmodel import Session

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models import User
from app.schemas.p90_fmv_v2 import P90FmvDiagnosticsRead, P90FmvIntelligenceDashboardRead, P90FmvV2CopyRead
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.services.fmv_v2_dashboard_service import (
    build_fmv_diagnostics,
    build_fmv_intelligence_dashboard,
    fmv_v2_for_inventory_copy,
)
from app.services.ops_admin import ensure_ops_admin_access
from app.services.portfolio_fmv_v2_service import build_portfolio_fmv_v2

p90_fmv_v2_router = APIRouter(tags=["FMV Intelligence V2 (P90-02)"])


def attach_p90_fmv_v2_layer(app: FastAPI) -> None:
    app.include_router(p90_fmv_v2_router)


@p90_fmv_v2_router.get("/api/v1/fmv-intelligence", response_model=ScanApiV1Envelope)
def v1_fmv_intelligence_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P90FmvIntelligenceDashboardRead = build_fmv_intelligence_dashboard(
        session, owner_user_id=int(current_user.id)
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@p90_fmv_v2_router.get("/api/v1/fmv-intelligence/portfolio", response_model=ScanApiV1Envelope)
def v1_fmv_portfolio(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    return wrap_object(build_portfolio_fmv_v2(session, owner_user_id=int(current_user.id)), owner_user_id=int(current_user.id))


@p90_fmv_v2_router.get("/api/v1/fmv-intelligence/inventory/{inventory_copy_id}", response_model=ScanApiV1Envelope)
def v1_fmv_inventory_copy(
    inventory_copy_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P90FmvV2CopyRead = fmv_v2_for_inventory_copy(
        session, owner_user_id=int(current_user.id), inventory_copy_id=inventory_copy_id
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@p90_fmv_v2_router.get("/api/v1/ops/fmv-diagnostics", response_model=ScanApiV1Envelope, include_in_schema=False)
def v1_ops_fmv_diagnostics(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    assert current_user.id is not None
    body: P90FmvDiagnosticsRead = build_fmv_diagnostics(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))
