from __future__ import annotations

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.marketplace import MarketplaceAccount, MarketplaceDefinition
from app.schemas.marketplace import MarketplaceAccountCreate, MarketplaceAccountRead
from app.schemas.whatnot import WhatnotAccountStatusRead, WhatnotConnectRequest
from app.services.marketplace_accounts import (
    ACCOUNT_STATUS_ACTIVE,
    ACCOUNT_STATUS_DISABLED,
    create_account,
    disable_account,
    get_account,
    update_account,
)
from app.services.marketplace_registry import enable_marketplace
from app.services.marketplace_seed import ensure_marketplace_definitions
from app.services.whatnot_connector import WHATNOT_MARKETPLACE_CODE, WhatnotConnector, _has_valid_credentials

WHATNOT_CREDENTIAL_TYPE = "api_token"


def _whatnot_marketplace_id(session: Session) -> int:
    ensure_marketplace_definitions(session)
    row = session.exec(
        select(MarketplaceDefinition).where(MarketplaceDefinition.marketplace_code == WHATNOT_MARKETPLACE_CODE)
    ).first()
    if row is None or row.id is None:
        raise HTTPException(status_code=404, detail="Whatnot marketplace definition not found.")
    return int(row.id)


def get_owner_whatnot_account(session: Session, *, owner_id: int) -> MarketplaceAccount:
    marketplace_id = _whatnot_marketplace_id(session)
    row = session.exec(
        select(MarketplaceAccount)
        .where(MarketplaceAccount.owner_id == owner_id)
        .where(MarketplaceAccount.marketplace_id == marketplace_id)
        .where(MarketplaceAccount.status == ACCOUNT_STATUS_ACTIVE)
        .order_by(MarketplaceAccount.updated_at.desc(), MarketplaceAccount.id.desc())
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Active Whatnot account not found.")
    return row


def connect_account(session: Session, *, owner_id: int, payload: WhatnotConnectRequest) -> MarketplaceAccountRead:
    marketplace_id = _whatnot_marketplace_id(session)
    account = create_account(
        session,
        owner_id=owner_id,
        payload=MarketplaceAccountCreate(
            marketplace_id=marketplace_id,
            account_name=payload.account_name.strip(),
            account_identifier=payload.account_identifier.strip(),
            status=ACCOUNT_STATUS_ACTIVE,
            credential_type=WHATNOT_CREDENTIAL_TYPE,
            credential_payload=payload.api_token.strip(),
        ),
    )
    connector = WhatnotConnector(marketplace_id=marketplace_id, account_id=account.id)
    if not connector.validate_credentials(session):
        disable_account(session, owner_id=owner_id, account_id=account.id)
        raise HTTPException(status_code=422, detail="Whatnot credential validation failed.")
    connector.connect(session)
    enable_marketplace(session, marketplace_id=marketplace_id)
    return get_account(session, owner_id=owner_id, account_id=account.id)


def disconnect_account(session: Session, *, owner_id: int) -> MarketplaceAccountRead:
    account = get_owner_whatnot_account(session, owner_id=owner_id)
    connector = WhatnotConnector(marketplace_id=account.marketplace_id, account_id=account.id)
    connector.disconnect(session)
    return disable_account(session, owner_id=owner_id, account_id=account.id)


def validate_account(session: Session, *, owner_id: int) -> WhatnotAccountStatusRead:
    account = get_owner_whatnot_account(session, owner_id=owner_id)
    connector = WhatnotConnector(marketplace_id=account.marketplace_id, account_id=account.id)
    valid = connector.validate_credentials(session)
    return WhatnotAccountStatusRead(
        account_id=account.id,
        status=account.status,
        credentials_valid=valid,
        marketplace_id=account.marketplace_id,
    )


def refresh_credentials(session: Session, *, owner_id: int, api_token: str) -> MarketplaceAccountRead:
    account = get_owner_whatnot_account(session, owner_id=owner_id)
    updated = update_account(
        session,
        owner_id=owner_id,
        account_id=account.id,
        credential_type=WHATNOT_CREDENTIAL_TYPE,
        credential_payload=api_token.strip(),
    )
    connector = WhatnotConnector(marketplace_id=updated.marketplace_id, account_id=updated.id)
    if not connector.validate_credentials(session):
        raise HTTPException(status_code=422, detail="Whatnot credential validation failed.")
    return updated


def get_account_status(session: Session, *, owner_id: int) -> WhatnotAccountStatusRead:
    account_row = session.exec(
        select(MarketplaceAccount)
        .where(MarketplaceAccount.owner_id == owner_id)
        .where(MarketplaceAccount.marketplace_id == _whatnot_marketplace_id(session))
        .order_by(MarketplaceAccount.updated_at.desc(), MarketplaceAccount.id.desc())
    ).first()
    if account_row is None:
        raise HTTPException(status_code=404, detail="Whatnot account not found.")
    account = get_account(session, owner_id=owner_id, account_id=int(account_row.id or 0))
    valid = account.status == ACCOUNT_STATUS_ACTIVE and _has_valid_credentials(session, account_id=account.id)
    return WhatnotAccountStatusRead(
        account_id=account.id,
        status=account.status,
        credentials_valid=valid,
        marketplace_id=account.marketplace_id,
    )
