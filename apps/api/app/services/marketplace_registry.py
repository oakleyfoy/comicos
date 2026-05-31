from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.marketplace import MarketplaceCapability as MarketplaceCapabilityRecord
from app.models.marketplace import MarketplaceDefinition as MarketplaceDefinitionRecord
from app.schemas.marketplace import (
    MarketplaceCapabilityRead,
    MarketplaceDefinitionListResponse,
    MarketplaceDefinitionRead,
)
from app.services.marketplace_seed import ensure_marketplace_definitions


@dataclass(frozen=True)
class MarketplaceDefinition:
    marketplace_key: str
    display_name: str
    status: str
    capability_flags: tuple[str, ...]


_MARKETPLACE_DEFINITIONS: tuple[MarketplaceDefinition, ...] = (
    MarketplaceDefinition(
        marketplace_key="ebay",
        display_name="eBay",
        status="supported",
        capability_flags=(
            "account_connect",
            "credential_reference",
            "inventory_sync_contract_reserved",
            "listing_sync_contract_reserved",
            "order_ingestion_contract_reserved",
        ),
    ),
    MarketplaceDefinition(
        marketplace_key="whatnot",
        display_name="Whatnot",
        status="supported",
        capability_flags=(
            "account_connect",
            "credential_reference",
            "inventory_sync_contract_reserved",
            "livestream_contract_reserved",
            "order_ingestion_contract_reserved",
        ),
    ),
    MarketplaceDefinition(
        marketplace_key="shopify",
        display_name="Shopify",
        status="supported",
        capability_flags=(
            "account_connect",
            "catalog_sync_contract_reserved",
            "credential_reference",
            "inventory_sync_contract_reserved",
            "order_ingestion_contract_reserved",
        ),
    ),
)

_MARKETPLACE_BY_KEY = {definition.marketplace_key: definition for definition in _MARKETPLACE_DEFINITIONS}


def list_marketplace_definitions() -> tuple[MarketplaceDefinition, ...]:
    return _MARKETPLACE_DEFINITIONS


def get_marketplace_definition(marketplace_key: str) -> MarketplaceDefinition | None:
    return _MARKETPLACE_BY_KEY.get(marketplace_key.strip().lower())


def _clamp(limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 200), max(offset, 0)


def _normalize_code(value: str) -> str:
    normalized = value.strip().upper()
    if not normalized:
        raise HTTPException(status_code=422, detail="Marketplace code is required.")
    return normalized


def _capability_reads(session: Session, *, marketplace_id: int) -> list[MarketplaceCapabilityRead]:
    rows = session.exec(
        select(MarketplaceCapabilityRecord)
        .where(MarketplaceCapabilityRecord.marketplace_id == marketplace_id)
        .order_by(MarketplaceCapabilityRecord.capability_code.asc(), MarketplaceCapabilityRecord.id.asc())
    ).all()
    return [
        MarketplaceCapabilityRead(
            id=int(row.id or 0),
            marketplace_id=row.marketplace_id,
            capability_code=row.capability_code,
            capability_name=row.capability_name,
        )
        for row in rows
    ]


def _definition_read(session: Session, row: MarketplaceDefinitionRecord) -> MarketplaceDefinitionRead:
    return MarketplaceDefinitionRead(
        id=int(row.id or 0),
        marketplace_code=row.marketplace_code,
        marketplace_name=row.marketplace_name,
        description=row.description,
        enabled=row.enabled,
        capabilities=_capability_reads(session, marketplace_id=int(row.id or 0)),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _definition_or_404(session: Session, *, marketplace_id: int) -> MarketplaceDefinitionRecord:
    row = session.get(MarketplaceDefinitionRecord, marketplace_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Marketplace definition not found.")
    return row


def register_marketplace(
    session: Session,
    *,
    marketplace_code: str,
    marketplace_name: str,
    description: str | None = None,
    enabled: bool = False,
    capabilities: list[tuple[str, str]] | None = None,
) -> MarketplaceDefinitionRead:
    code = _normalize_code(marketplace_code)
    existing = session.exec(
        select(MarketplaceDefinitionRecord).where(MarketplaceDefinitionRecord.marketplace_code == code)
    ).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Marketplace code already exists.")

    row = MarketplaceDefinitionRecord(
        marketplace_code=code,
        marketplace_name=marketplace_name.strip(),
        description=description.strip() if description else None,
        enabled=enabled,
    )
    session.add(row)
    session.flush()
    for capability_code, capability_name in sorted(capabilities or [], key=lambda item: item[0]):
        session.add(
            MarketplaceCapabilityRecord(
                marketplace_id=int(row.id or 0),
                capability_code=capability_code.strip(),
                capability_name=capability_name.strip(),
            )
        )
    session.commit()
    session.refresh(row)
    return _definition_read(session, row)


def update_marketplace(
    session: Session,
    *,
    marketplace_id: int,
    marketplace_name: str | None = None,
    description: str | None = None,
    enabled: bool | None = None,
    capabilities: list[tuple[str, str]] | None = None,
) -> MarketplaceDefinitionRead:
    row = _definition_or_404(session, marketplace_id=marketplace_id)
    if marketplace_name is not None:
        row.marketplace_name = marketplace_name.strip()
    if description is not None:
        row.description = description.strip() or None
    if enabled is not None:
        row.enabled = enabled
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    if capabilities is not None:
        existing_rows = session.exec(
            select(MarketplaceCapabilityRecord).where(MarketplaceCapabilityRecord.marketplace_id == marketplace_id)
        ).all()
        for capability_row in existing_rows:
            session.delete(capability_row)
        session.flush()
        for capability_code, capability_name in sorted(capabilities, key=lambda item: item[0]):
            session.add(
                MarketplaceCapabilityRecord(
                    marketplace_id=marketplace_id,
                    capability_code=capability_code.strip(),
                    capability_name=capability_name.strip(),
                )
            )
    session.commit()
    session.refresh(row)
    return _definition_read(session, row)


def list_marketplaces(
    session: Session,
    *,
    limit: int = 100,
    offset: int = 0,
) -> MarketplaceDefinitionListResponse:
    ensure_marketplace_definitions(session)
    limit, offset = _clamp(limit, offset)
    rows = session.exec(
        select(MarketplaceDefinitionRecord)
        .order_by(MarketplaceDefinitionRecord.marketplace_code.asc(), MarketplaceDefinitionRecord.id.asc())
    ).all()
    items = [_definition_read(session, row) for row in rows]
    return MarketplaceDefinitionListResponse(
        items=items[offset : offset + limit],
        total_items=len(items),
        limit=limit,
        offset=offset,
    )


def get_marketplace(session: Session, *, marketplace_id: int) -> MarketplaceDefinitionRead:
    ensure_marketplace_definitions(session)
    row = _definition_or_404(session, marketplace_id=marketplace_id)
    return _definition_read(session, row)


def enable_marketplace(session: Session, *, marketplace_id: int) -> MarketplaceDefinitionRead:
    return update_marketplace(session, marketplace_id=marketplace_id, enabled=True)


def disable_marketplace(session: Session, *, marketplace_id: int) -> MarketplaceDefinitionRead:
    return update_marketplace(session, marketplace_id=marketplace_id, enabled=False)
