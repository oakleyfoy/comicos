from __future__ import annotations

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.marketplace import MarketplaceAccount, MarketplaceDefinition
from app.schemas.marketplace import MarketplaceAccountCreate, MarketplaceAccountRead
from app.schemas.shopify import ShopifyConnectRequest, ShopifyAccountStatusRead
from app.services.marketplace_accounts import (
    ACCOUNT_STATUS_ACTIVE,
    create_account,
    disable_account,
    get_account,
    update_account,
)
from app.services.marketplace_registry import enable_marketplace
from app.services.marketplace_seed import ensure_marketplace_definitions
from app.services.shopify_connector import SHOPIFY_MARKETPLACE_CODE, ShopifyConnector, _has_valid_credentials

SHOPIFY_CREDENTIAL_TYPE = "admin_api_token"


def _shopify_marketplace_id(session: Session) -> int:
    ensure_marketplace_definitions(session)
    row = session.exec(
        select(MarketplaceDefinition).where(MarketplaceDefinition.marketplace_code == SHOPIFY_MARKETPLACE_CODE)
    ).first()
    if row is None or row.id is None:
        raise HTTPException(status_code=404, detail="Shopify marketplace definition not found.")
    return int(row.id)


def get_owner_shopify_account(session: Session, *, owner_id: int) -> MarketplaceAccount:
    marketplace_id = _shopify_marketplace_id(session)
    row = session.exec(
        select(MarketplaceAccount)
        .where(MarketplaceAccount.owner_id == owner_id)
        .where(MarketplaceAccount.marketplace_id == marketplace_id)
        .where(MarketplaceAccount.status == ACCOUNT_STATUS_ACTIVE)
        .order_by(MarketplaceAccount.updated_at.desc(), MarketplaceAccount.id.desc())
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Active Shopify account not found.")
    return row


def connect_account(session: Session, *, owner_id: int, payload: ShopifyConnectRequest) -> MarketplaceAccountRead:
    marketplace_id = _shopify_marketplace_id(session)
    account = create_account(
        session,
        owner_id=owner_id,
        payload=MarketplaceAccountCreate(
            marketplace_id=marketplace_id,
            account_name=payload.account_name.strip(),
            account_identifier=payload.shop_domain.strip(),
            status=ACCOUNT_STATUS_ACTIVE,
            credential_type=SHOPIFY_CREDENTIAL_TYPE,
            credential_payload=payload.admin_api_token.strip(),
        ),
    )
    connector = ShopifyConnector(marketplace_id=marketplace_id, account_id=account.id)
    if not connector.validate_credentials(session):
        disable_account(session, owner_id=owner_id, account_id=account.id)
        raise HTTPException(status_code=422, detail="Shopify credential validation failed.")
    connector.connect(session)
    enable_marketplace(session, marketplace_id=marketplace_id)
    return get_account(session, owner_id=owner_id, account_id=account.id)


def disconnect_account(session: Session, *, owner_id: int) -> MarketplaceAccountRead:
    account = get_owner_shopify_account(session, owner_id=owner_id)
    connector = ShopifyConnector(marketplace_id=account.marketplace_id, account_id=account.id)
    connector.disconnect(session)
    return disable_account(session, owner_id=owner_id, account_id=account.id)


def validate_account(session: Session, *, owner_id: int) -> ShopifyAccountStatusRead:
    account = get_owner_shopify_account(session, owner_id=owner_id)
    connector = ShopifyConnector(marketplace_id=account.marketplace_id, account_id=account.id)
    valid = connector.validate_credentials(session)
    return ShopifyAccountStatusRead(
        account_id=account.id,
        status=account.status,
        credentials_valid=valid,
        marketplace_id=account.marketplace_id,
    )


def refresh_credentials(session: Session, *, owner_id: int, admin_api_token: str) -> MarketplaceAccountRead:
    account = get_owner_shopify_account(session, owner_id=owner_id)
    updated = update_account(
        session,
        owner_id=owner_id,
        account_id=account.id,
        credential_type=SHOPIFY_CREDENTIAL_TYPE,
        credential_payload=admin_api_token.strip(),
    )
    connector = ShopifyConnector(marketplace_id=updated.marketplace_id, account_id=updated.id)
    if not connector.validate_credentials(session):
        raise HTTPException(status_code=422, detail="Shopify credential validation failed.")
    return updated


def get_account_status(session: Session, *, owner_id: int) -> ShopifyAccountStatusRead:
    account_row = session.exec(
        select(MarketplaceAccount)
        .where(MarketplaceAccount.owner_id == owner_id)
        .where(MarketplaceAccount.marketplace_id == _shopify_marketplace_id(session))
        .order_by(MarketplaceAccount.updated_at.desc(), MarketplaceAccount.id.desc())
    ).first()
    if account_row is None:
        raise HTTPException(status_code=404, detail="Shopify account not found.")
    account = get_account(session, owner_id=owner_id, account_id=int(account_row.id or 0))
    valid = account.status == ACCOUNT_STATUS_ACTIVE and _has_valid_credentials(session, account_id=account.id)
    return ShopifyAccountStatusRead(
        account_id=account.id,
        status=account.status,
        credentials_valid=valid,
        marketplace_id=account.marketplace_id,
    )
