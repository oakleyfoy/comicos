from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.services.marketplace_analytics import get_marketplace_analytics
from app.services.marketplace_dashboard import get_marketplace_dashboard, list_account_health, list_connector_readiness
from app.services.marketplace_health import get_marketplace_health
from app.services.marketplace_validation import validate_marketplace_platform

marketplace_dashboard_v1_router = APIRouter(prefix="/api/v1", tags=["Marketplace Platform Dashboard API v1 (P46-08)"])


def attach_marketplace_dashboard_layer(app: FastAPI) -> None:
    app.include_router(marketplace_dashboard_v1_router)


@marketplace_dashboard_v1_router.get("/marketplace-dashboard", response_model=ScanApiV1Envelope)
def v1_marketplace_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_marketplace_dashboard(session, owner_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@marketplace_dashboard_v1_router.get("/marketplace-dashboard/health", response_model=ScanApiV1Envelope)
def v1_marketplace_dashboard_health(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_marketplace_health(session, owner_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@marketplace_dashboard_v1_router.get("/marketplace-dashboard/analytics", response_model=ScanApiV1Envelope)
def v1_marketplace_dashboard_analytics(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_marketplace_analytics(session, owner_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@marketplace_dashboard_v1_router.get("/marketplace-dashboard/validation", response_model=ScanApiV1Envelope)
def v1_marketplace_dashboard_validation(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = validate_marketplace_platform(session, owner_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@marketplace_dashboard_v1_router.get("/marketplace-dashboard/connectors", response_model=ScanApiV1Envelope)
def v1_marketplace_dashboard_connectors(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_connector_readiness(session, owner_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@marketplace_dashboard_v1_router.get("/marketplace-dashboard/accounts", response_model=ScanApiV1Envelope)
def v1_marketplace_dashboard_accounts(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_account_health(session, owner_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))
