"""P43-01 `/api/v1/organizations/*/marketplaces` layered routes with deterministic envelopes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, Response, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.marketplace_accounts import (
    MarketplaceAccountConnectRequest,
    MarketplaceAccountDisconnectRequest,
    MarketplaceAccountVerifyRequest,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.marketplace_account_service import (
    connect_marketplace_account,
    disconnect_marketplace_account,
    get_marketplace_account_detail,
    list_marketplace_accounts,
    verify_marketplace_account,
)

marketplace_accounts_v1_router = APIRouter(prefix="/api/v1", tags=["Marketplace Accounts API v1 (P43-01)"])


def attach_marketplace_accounts_layer(app: FastAPI) -> None:
    app.include_router(marketplace_accounts_v1_router)


@marketplace_accounts_v1_router.get("/organizations/{organization_id}/marketplaces", response_model=ScanApiV1Envelope)
def v1_list_marketplace_accounts(
    organization_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_marketplace_accounts(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@marketplace_accounts_v1_router.get("/organizations/{organization_id}/marketplaces/{account_id}", response_model=ScanApiV1Envelope)
def v1_get_marketplace_account(
    organization_id: int,
    account_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_marketplace_account_detail(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        account_id=account_id,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.account.id)


@marketplace_accounts_v1_router.post(
    "/organizations/{organization_id}/marketplaces/connect",
    response_model=ScanApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_connect_marketplace_account(
    organization_id: int,
    payload: MarketplaceAccountConnectRequest,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body, created = connect_marketplace_account(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        payload=payload,
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.account.id)


@marketplace_accounts_v1_router.post("/organizations/{organization_id}/marketplaces/disconnect", response_model=ScanApiV1Envelope)
def v1_disconnect_marketplace_account(
    organization_id: int,
    payload: MarketplaceAccountDisconnectRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = disconnect_marketplace_account(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.account.id)


@marketplace_accounts_v1_router.post("/organizations/{organization_id}/marketplaces/verify", response_model=ScanApiV1Envelope)
def v1_verify_marketplace_account(
    organization_id: int,
    payload: MarketplaceAccountVerifyRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = verify_marketplace_account(
        session,
        organization_id=organization_id,
        actor_user_id=int(current_user.id),
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.account.id)
