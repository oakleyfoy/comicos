from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, select

from app.core.security import encrypt_secret_value
from app.models.marketplace import MarketplaceAccount, MarketplaceCredential, MarketplaceDefinition
from app.schemas.marketplace import (
    MarketplaceAccountCreate,
    MarketplaceAccountListResponse,
    MarketplaceAccountRead,
    MarketplaceDefinitionRead,
)
from app.services.marketplace_registry import get_marketplace, list_marketplaces
from app.services.marketplace_seed import ensure_marketplace_definitions

ACCOUNT_STATUS_ACTIVE = "ACTIVE"
ACCOUNT_STATUS_DISABLED = "DISABLED"
ACCOUNT_STATUS_PENDING = "PENDING"
ACCOUNT_STATUSES = {ACCOUNT_STATUS_ACTIVE, ACCOUNT_STATUS_DISABLED, ACCOUNT_STATUS_PENDING}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _clamp(limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 200), max(offset, 0)


def _normalize_status(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in ACCOUNT_STATUSES:
        raise HTTPException(status_code=422, detail="Unsupported marketplace account status.")
    return normalized


def _definition_map(session: Session) -> dict[int, MarketplaceDefinitionRead]:
    listing = list_marketplaces(session, limit=200, offset=0)
    return {row.id: row for row in listing.items}


def _account_read(
    row: MarketplaceAccount,
    *,
    marketplace: MarketplaceDefinitionRead | None,
) -> MarketplaceAccountRead:
    return MarketplaceAccountRead(
        id=int(row.id or 0),
        marketplace_id=row.marketplace_id,
        owner_id=row.owner_id,
        account_name=row.account_name,
        account_identifier=row.account_identifier,
        status=row.status,
        marketplace=marketplace,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _account_or_404(session: Session, *, account_id: int) -> MarketplaceAccount:
    row = session.get(MarketplaceAccount, account_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Marketplace account not found.")
    return row


def _owner_account_or_404(session: Session, *, owner_id: int, account_id: int) -> MarketplaceAccount:
    row = _account_or_404(session, account_id=account_id)
    if row.owner_id != owner_id:
        raise HTTPException(status_code=404, detail="Marketplace account not found.")
    return row


def create_account(session: Session, *, owner_id: int, payload: MarketplaceAccountCreate) -> MarketplaceAccountRead:
    ensure_marketplace_definitions(session)
    marketplace_row = session.get(MarketplaceDefinition, payload.marketplace_id)
    if marketplace_row is None:
        raise HTTPException(status_code=404, detail="Marketplace definition not found.")

    existing = session.exec(
        select(MarketplaceAccount)
        .where(MarketplaceAccount.marketplace_id == payload.marketplace_id)
        .where(MarketplaceAccount.owner_id == owner_id)
        .where(MarketplaceAccount.account_identifier == payload.account_identifier.strip())
    ).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Marketplace account already exists.")

    now = utc_now()
    row = MarketplaceAccount(
        marketplace_id=payload.marketplace_id,
        owner_id=owner_id,
        account_name=payload.account_name.strip(),
        account_identifier=payload.account_identifier.strip(),
        status=_normalize_status(payload.status),
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    if payload.credential_type and payload.credential_payload:
        session.add(
            MarketplaceCredential(
                account_id=int(row.id or 0),
                credential_type=payload.credential_type.strip().lower(),
                encrypted_payload=encrypt_secret_value(payload.credential_payload),
                created_at=now,
                updated_at=now,
            )
        )
    session.commit()
    session.refresh(row)
    return _account_read(row, marketplace=get_marketplace(session, marketplace_id=row.marketplace_id))


def update_account(
    session: Session,
    *,
    owner_id: int,
    account_id: int,
    account_name: str | None = None,
    status: str | None = None,
    credential_type: str | None = None,
    credential_payload: str | None = None,
) -> MarketplaceAccountRead:
    row = _owner_account_or_404(session, owner_id=owner_id, account_id=account_id)
    if account_name is not None:
        row.account_name = account_name.strip()
    if status is not None:
        row.status = _normalize_status(status)
    row.updated_at = utc_now()
    session.add(row)
    if (credential_type is None) != (credential_payload is None):
        raise HTTPException(status_code=422, detail="credential_type and credential_payload must be provided together.")
    if credential_type and credential_payload:
        existing_credential = session.exec(
            select(MarketplaceCredential)
            .where(MarketplaceCredential.account_id == account_id)
            .where(MarketplaceCredential.credential_type == credential_type.strip().lower())
        ).first()
        now = utc_now()
        if existing_credential is None:
            session.add(
                MarketplaceCredential(
                    account_id=account_id,
                    credential_type=credential_type.strip().lower(),
                    encrypted_payload=encrypt_secret_value(credential_payload),
                    created_at=now,
                    updated_at=now,
                )
            )
        else:
            existing_credential.encrypted_payload = encrypt_secret_value(credential_payload)
            existing_credential.updated_at = now
            session.add(existing_credential)
    session.commit()
    session.refresh(row)
    return _account_read(row, marketplace=get_marketplace(session, marketplace_id=row.marketplace_id))


def disable_account(session: Session, *, owner_id: int, account_id: int) -> MarketplaceAccountRead:
    row = _owner_account_or_404(session, owner_id=owner_id, account_id=account_id)
    row.status = ACCOUNT_STATUS_DISABLED
    row.updated_at = utc_now()
    session.add(row)
    session.commit()
    session.refresh(row)
    return _account_read(row, marketplace=get_marketplace(session, marketplace_id=row.marketplace_id))


def list_accounts(session: Session, *, owner_id: int, limit: int, offset: int) -> MarketplaceAccountListResponse:
    ensure_marketplace_definitions(session)
    definition_map = _definition_map(session)
    limit, offset = _clamp(limit, offset)
    rows = session.exec(
        select(MarketplaceAccount)
        .where(MarketplaceAccount.owner_id == owner_id)
        .order_by(
            MarketplaceAccount.marketplace_id.asc(),
            MarketplaceAccount.account_name.asc(),
            MarketplaceAccount.account_identifier.asc(),
            MarketplaceAccount.id.asc(),
        )
    ).all()
    items = [
        _account_read(row, marketplace=definition_map.get(row.marketplace_id))
        for row in rows
    ]
    return MarketplaceAccountListResponse(
        items=items[offset : offset + limit],
        total_items=len(items),
        limit=limit,
        offset=offset,
    )


def get_account(session: Session, *, owner_id: int, account_id: int) -> MarketplaceAccountRead:
    row = _owner_account_or_404(session, owner_id=owner_id, account_id=account_id)
    return _account_read(row, marketplace=get_marketplace(session, marketplace_id=row.marketplace_id))
