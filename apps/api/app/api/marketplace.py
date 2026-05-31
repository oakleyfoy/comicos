from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.marketplace import MarketplaceAccountCreate
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.marketplace_accounts import create_account, disable_account, get_account, list_accounts
from app.services.marketplace_execution import get_execution, list_executions
from app.services.marketplace_registry import get_marketplace, list_marketplaces

marketplace_v1_router = APIRouter(prefix="/api/v1", tags=["Marketplace Connector Framework v1"])


def attach_marketplace_layer(app: FastAPI) -> None:
    app.include_router(marketplace_v1_router)


@marketplace_v1_router.get("/marketplaces", response_model=ScanApiV1Envelope)
def v1_list_marketplaces(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_marketplaces(session, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@marketplace_v1_router.get("/marketplaces/{marketplace_id}", response_model=ScanApiV1Envelope)
def v1_get_marketplace(
    marketplace_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_marketplace(session, marketplace_id=marketplace_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@marketplace_v1_router.post("/marketplace-accounts", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_create_marketplace_account(
    payload: MarketplaceAccountCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = create_account(session, owner_id=int(current_user.id), payload=payload)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@marketplace_v1_router.get("/marketplace-accounts", response_model=ScanApiV1Envelope)
def v1_list_marketplace_accounts(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_accounts(session, owner_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@marketplace_v1_router.get("/marketplace-accounts/{account_id}", response_model=ScanApiV1Envelope)
def v1_get_marketplace_account(
    account_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_account(session, owner_id=int(current_user.id), account_id=account_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@marketplace_v1_router.post("/marketplace-accounts/{account_id}/disable", response_model=ScanApiV1Envelope)
def v1_disable_marketplace_account(
    account_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = disable_account(session, owner_id=int(current_user.id), account_id=account_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id)


@marketplace_v1_router.get("/marketplace-executions", response_model=ScanApiV1Envelope)
def v1_list_marketplace_executions(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_executions(session, owner_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@marketplace_v1_router.get("/marketplace-executions/{execution_id}", response_model=ScanApiV1Envelope)
def v1_get_marketplace_execution(
    execution_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_execution(session, owner_id=int(current_user.id), execution_id=execution_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.execution.id)
