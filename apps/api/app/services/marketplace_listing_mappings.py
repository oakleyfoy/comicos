from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.marketplace import MarketplaceAccount as MarketplaceConnectorAccount
from app.models.marketplace import MarketplaceDefinition as MarketplaceConnectorDefinition
from app.models.marketplace_listing import MarketplaceListingMapping
from app.schemas.marketplace_listing import MarketplaceListingMappingCreate, MarketplaceListingMappingListResponse, MarketplaceListingMappingRead
from app.services.marketplace_listings import _clamp, _owner_listing_or_404


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_sync_status(value: str) -> str:
    normalized = value.strip().upper()
    if not normalized:
        raise HTTPException(status_code=422, detail="Mapping sync status is required.")
    return normalized


def _mapping_read(row: MarketplaceListingMapping) -> MarketplaceListingMappingRead:
    return MarketplaceListingMappingRead(
        id=int(row.id or 0),
        listing_id=row.listing_id,
        marketplace_id=row.marketplace_id,
        marketplace_account_id=row.marketplace_account_id,
        external_listing_id=row.external_listing_id,
        external_url=row.external_url,
        sync_status=row.sync_status,
        last_synced_at=row.last_synced_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _mapping_or_404(session: Session, *, listing_id: int, mapping_id: int) -> MarketplaceListingMapping:
    row = session.get(MarketplaceListingMapping, mapping_id)
    if row is None or row.listing_id != listing_id:
        raise HTTPException(status_code=404, detail="Marketplace listing mapping not found.")
    return row


def create_mapping(
    session: Session,
    *,
    owner_id: int,
    listing_id: int,
    payload: MarketplaceListingMappingCreate,
) -> MarketplaceListingMappingRead:
    _owner_listing_or_404(session, owner_id=owner_id, listing_id=listing_id)
    marketplace = session.get(MarketplaceConnectorDefinition, payload.marketplace_id)
    if marketplace is None:
        raise HTTPException(status_code=404, detail="Marketplace definition not found.")
    if payload.marketplace_account_id is not None:
        account = session.get(MarketplaceConnectorAccount, payload.marketplace_account_id)
        if account is None or account.owner_id != owner_id:
            raise HTTPException(status_code=404, detail="Marketplace account not found.")
    now = utc_now()
    row = MarketplaceListingMapping(
        listing_id=listing_id,
        marketplace_id=payload.marketplace_id,
        marketplace_account_id=payload.marketplace_account_id,
        external_listing_id=(payload.external_listing_id or "").strip() or None,
        external_url=(payload.external_url or "").strip() or None,
        sync_status=_normalize_sync_status(payload.sync_status),
        last_synced_at=None,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _mapping_read(row)


def update_mapping_status(
    session: Session,
    *,
    owner_id: int,
    listing_id: int,
    mapping_id: int,
    sync_status: str,
    external_listing_id: str | None = None,
    external_url: str | None = None,
    last_synced_at: datetime | None = None,
) -> MarketplaceListingMappingRead:
    _owner_listing_or_404(session, owner_id=owner_id, listing_id=listing_id)
    row = _mapping_or_404(session, listing_id=listing_id, mapping_id=mapping_id)
    row.sync_status = _normalize_sync_status(sync_status)
    if external_listing_id is not None:
        row.external_listing_id = external_listing_id.strip() or None
    if external_url is not None:
        row.external_url = external_url.strip() or None
    row.last_synced_at = last_synced_at or utc_now()
    row.updated_at = utc_now()
    session.add(row)
    session.commit()
    session.refresh(row)
    return _mapping_read(row)


def list_mappings_for_listing(session: Session, *, owner_id: int, listing_id: int, limit: int, offset: int) -> MarketplaceListingMappingListResponse:
    _owner_listing_or_404(session, owner_id=owner_id, listing_id=listing_id)
    limit, offset = _clamp(limit, offset)
    rows = session.exec(
        select(MarketplaceListingMapping)
        .where(MarketplaceListingMapping.listing_id == listing_id)
        .order_by(MarketplaceListingMapping.created_at.asc(), MarketplaceListingMapping.id.asc())
    ).all()
    items = [_mapping_read(row) for row in rows]
    return MarketplaceListingMappingListResponse(
        items=items[offset : offset + limit],
        total_items=len(items),
        limit=limit,
        offset=offset,
    )


def get_mapping(session: Session, *, owner_id: int, listing_id: int, mapping_id: int) -> MarketplaceListingMappingRead:
    _owner_listing_or_404(session, owner_id=owner_id, listing_id=listing_id)
    row = _mapping_or_404(session, listing_id=listing_id, mapping_id=mapping_id)
    return _mapping_read(row)
