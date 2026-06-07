"""P88 manual marketplace URL import and source listing."""

from __future__ import annotations

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import User
from app.models.p88_marketplace_foundation import MarketplaceOpportunitySource, utc_now
from app.schemas.p88_marketplace_foundation import (
    BuyOpportunityImportUrlPayload,
    MarketplaceImportAuditListResponse,
    MarketplaceImportAuditRow,
    MarketplaceImportUrlResponse,
    MarketplaceOpportunitySourceListResponse,
    MarketplaceOpportunitySourceRead,
)
from app.services.marketplace.marketplace_registry import (
    extract_external_listing_id,
    marketplace_display_name,
)
from app.services.marketplace.url_validation import validate_marketplace_url


def _to_read(row: MarketplaceOpportunitySource) -> MarketplaceOpportunitySourceRead:
    return MarketplaceOpportunitySourceRead(
        id=int(row.id or 0),
        owner_user_id=int(row.owner_user_id),
        opportunity_id=row.opportunity_id,
        marketplace=row.marketplace,
        marketplace_display_name=marketplace_display_name(row.marketplace),
        source_type=row.source_type,  # type: ignore[arg-type]
        source_url=row.source_url,
        external_listing_id=row.external_listing_id,
        source_status=row.source_status,  # type: ignore[arg-type]
        notes=row.notes,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def import_marketplace_url(
    session: Session,
    *,
    owner_user_id: int,
    payload: BuyOpportunityImportUrlPayload,
) -> MarketplaceImportUrlResponse:
    validation = validate_marketplace_url(payload.url)
    if not validation.is_valid or not validation.normalized_url or not validation.marketplace:
        raise HTTPException(status_code=422, detail=validation.error_message or "Invalid marketplace URL.")

    if payload.opportunity_id is not None:
        from app.models.p82_p84_collector_expansion import MarketplaceAcquisitionOpportunity

        opp = session.get(MarketplaceAcquisitionOpportunity, payload.opportunity_id)
        if opp is None or opp.owner_user_id != owner_user_id:
            raise HTTPException(status_code=404, detail="Opportunity not found.")

    now = utc_now()
    ext_id = extract_external_listing_id(validation.normalized_url, validation.marketplace)
    row = MarketplaceOpportunitySource(
        owner_user_id=owner_user_id,
        opportunity_id=payload.opportunity_id,
        marketplace=validation.marketplace,
        source_type="MANUAL_IMPORT",
        source_url=validation.normalized_url,
        external_listing_id=ext_id,
        source_status="ACTIVE",
        notes=(payload.notes or "").strip(),
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    return MarketplaceImportUrlResponse(
        message="Marketplace imported successfully.",
        source=_to_read(row),
    )


def list_opportunity_sources(
    session: Session,
    *,
    owner_user_id: int,
    opportunity_id: int | None = None,
    limit: int = 50,
) -> MarketplaceOpportunitySourceListResponse:
    stmt = select(MarketplaceOpportunitySource).where(MarketplaceOpportunitySource.owner_user_id == owner_user_id)
    if opportunity_id is not None:
        stmt = stmt.where(MarketplaceOpportunitySource.opportunity_id == opportunity_id)
    rows = list(
        session.exec(
            stmt.order_by(MarketplaceOpportunitySource.created_at.desc()).limit(max(1, min(limit, 200)))
        ).all()
    )
    items = [_to_read(r) for r in rows]
    return MarketplaceOpportunitySourceListResponse(
        items=items,
        total_items=len(items),
        limit=max(1, min(limit, 200)),
        offset=0,
    )


def list_marketplace_import_audit(
    session: Session,
    *,
    limit: int = 100,
    offset: int = 0,
) -> MarketplaceImportAuditListResponse:
    rows = list(
        session.exec(
            select(MarketplaceOpportunitySource).order_by(MarketplaceOpportunitySource.created_at.desc())
        ).all()
    )
    user_ids = {int(r.owner_user_id) for r in rows}
    users: dict[int, User] = {}
    for uid in user_ids:
        user = session.get(User, uid)
        if user is not None:
            users[uid] = user
    lim = max(1, min(limit, 500))
    off = max(0, offset)
    page = rows[off : off + lim]
    items = [
        MarketplaceImportAuditRow(
            id=int(r.id or 0),
            imported_url=r.source_url,
            marketplace=r.marketplace,
            marketplace_display_name=marketplace_display_name(r.marketplace),
            user_id=int(r.owner_user_id),
            user_email=(users.get(int(r.owner_user_id)).email if users.get(int(r.owner_user_id)) else ""),
            status=r.source_status,
            source_type=r.source_type,
            notes=r.notes,
            created_at=r.created_at,
        )
        for r in page
    ]
    return MarketplaceImportAuditListResponse(
        items=items,
        total_items=len(rows),
        limit=lim,
        offset=off,
    )
