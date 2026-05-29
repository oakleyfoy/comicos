from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import MarketplaceAccount, MarketplaceListingDraft, MarketplaceOffer
from app.schemas.marketplace_pricing import (
    MarketplaceOfferIngestRequest,
    MarketplaceOfferListResponse,
    MarketplaceOfferResponse,
    MarketplaceOfferStatusUpdateRequest,
    MarketplacePricingOfferSummaryResponse,
    MarketplacePricingPermissionResponse,
)
from app.services.marketplace_permissions import (
    MarketplacePermissionResolution,
    resolve_marketplace_permissions,
)
from app.services.marketplace_pricing_service import create_pricing_event

OFFER_STATUS_RECEIVED = "received"
OFFER_STATUS_REVIEWED = "reviewed"
OFFER_STATUS_ACCEPTED_INTERNAL = "accepted_internal"
OFFER_STATUS_REJECTED_INTERNAL = "rejected_internal"
OFFER_STATUS_EXPIRED = "expired"
OFFER_STATUSES = {
    OFFER_STATUS_RECEIVED,
    OFFER_STATUS_REVIEWED,
    OFFER_STATUS_ACCEPTED_INTERNAL,
    OFFER_STATUS_REJECTED_INTERNAL,
    OFFER_STATUS_EXPIRED,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_decimal(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def _permission_response(resolution: MarketplacePermissionResolution) -> MarketplacePricingPermissionResponse:
    return MarketplacePricingPermissionResponse(can_view=resolution.can_view, can_manage=resolution.can_manage)


def clamp_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 200), max(offset, 0)


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _to_offer_response(row: MarketplaceOffer) -> MarketplaceOfferResponse:
    return MarketplaceOfferResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        marketplace_account_id=row.marketplace_account_id,
        marketplace_listing_draft_id=row.marketplace_listing_draft_id,
        marketplace_offer_identifier=row.marketplace_offer_identifier,
        offer_status=row.offer_status,
        offer_amount=row.offer_amount,
        offer_currency=row.offer_currency,
        buyer_identifier=row.buyer_identifier,
        received_at=row.received_at,
        expires_at=row.expires_at,
        created_at=row.created_at,
    )


def _account_or_404(session: Session, *, organization_id: int, marketplace_account_id: int) -> MarketplaceAccount:
    account = session.get(MarketplaceAccount, marketplace_account_id)
    if account is None or account.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Marketplace account not found.")
    return account


def _listing_or_404(session: Session, *, organization_id: int, marketplace_listing_draft_id: int) -> MarketplaceListingDraft:
    listing = session.get(MarketplaceListingDraft, marketplace_listing_draft_id)
    if listing is None or listing.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Marketplace listing draft not found.")
    return listing


def _validate_offer_visibility(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    action: str = "marketplace_offer:view",
) -> MarketplacePermissionResolution:
    resolution = resolve_marketplace_permissions(session, organization_id=organization_id, actor_user_id=actor_user_id)
    if not resolution.can_view:
        create_pricing_event(
            session,
            organization_id=organization_id,
            marketplace_account_id=None,
            marketplace_listing_draft_id=None,
            actor_user_id=actor_user_id,
            event_type="unauthorized_marketplace_pricing_access_attempt",
            event_payload_json={"action": action, "reason": resolution.reason},
        )
        session.commit()
        raise HTTPException(status_code=403, detail="Marketplace offer visibility is denied for this organization.")
    return resolution


def _validate_offer_management(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    marketplace_account_id: int | None = None,
    marketplace_listing_draft_id: int | None = None,
    action: str = "marketplace_offer:manage",
) -> MarketplacePermissionResolution:
    resolution = resolve_marketplace_permissions(session, organization_id=organization_id, actor_user_id=actor_user_id)
    if not resolution.can_manage:
        create_pricing_event(
            session,
            organization_id=organization_id,
            marketplace_account_id=marketplace_account_id,
            marketplace_listing_draft_id=marketplace_listing_draft_id,
            actor_user_id=actor_user_id,
            event_type="unauthorized_marketplace_pricing_access_attempt",
            event_payload_json={"action": action, "reason": resolution.reason},
        )
        session.commit()
        raise HTTPException(status_code=403, detail="Marketplace offer management is denied for this organization.")
    if marketplace_account_id is not None:
        _account_or_404(session, organization_id=organization_id, marketplace_account_id=marketplace_account_id)
    if marketplace_listing_draft_id is not None:
        _listing_or_404(session, organization_id=organization_id, marketplace_listing_draft_id=marketplace_listing_draft_id)
    return resolution


def detect_duplicate_offer(
    session: Session,
    *,
    marketplace_account_id: int,
    marketplace_offer_identifier: str,
) -> MarketplaceOffer | None:
    return session.exec(
        select(MarketplaceOffer)
        .where(MarketplaceOffer.marketplace_account_id == marketplace_account_id)
        .where(MarketplaceOffer.marketplace_offer_identifier == marketplace_offer_identifier.strip())
        .order_by(MarketplaceOffer.id.asc())
    ).first()


def ingest_marketplace_offer(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    payload: MarketplaceOfferIngestRequest,
) -> MarketplaceOfferResponse:
    _validate_offer_management(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        marketplace_account_id=payload.marketplace_account_id,
        marketplace_listing_draft_id=payload.marketplace_listing_draft_id,
        action="marketplace_offer:ingest",
    )
    existing = detect_duplicate_offer(
        session,
        marketplace_account_id=payload.marketplace_account_id,
        marketplace_offer_identifier=payload.marketplace_offer_identifier,
    )
    listing = _listing_or_404(session, organization_id=organization_id, marketplace_listing_draft_id=payload.marketplace_listing_draft_id)
    if existing is not None:
        create_pricing_event(
            session,
            organization_id=organization_id,
            marketplace_account_id=existing.marketplace_account_id,
            marketplace_listing_draft_id=existing.marketplace_listing_draft_id,
            actor_user_id=actor_user_id,
            event_type="marketplace_duplicate_offer_detected",
            event_payload_json={
                "marketplace_offer_identifier": existing.marketplace_offer_identifier,
                "offer_status": existing.offer_status,
            },
        )
        session.commit()
        return _to_offer_response(existing)

    offer_status = payload.offer_status.strip().lower()
    if offer_status not in OFFER_STATUSES:
        raise HTTPException(status_code=422, detail="Unsupported offer status.")
    now = utc_now()
    row = MarketplaceOffer(
        organization_id=organization_id,
        marketplace_account_id=payload.marketplace_account_id,
        marketplace_listing_draft_id=payload.marketplace_listing_draft_id,
        marketplace_offer_identifier=payload.marketplace_offer_identifier.strip(),
        offer_status=offer_status,
        offer_amount=_normalize_decimal(payload.offer_amount),
        offer_currency=payload.offer_currency.strip().upper(),
        buyer_identifier=payload.buyer_identifier or None,
        received_at=payload.received_at or now,
        expires_at=payload.expires_at,
        created_at=now,
    )
    session.add(row)
    session.flush()
    create_pricing_event(
        session,
        organization_id=organization_id,
        marketplace_account_id=payload.marketplace_account_id,
        marketplace_listing_draft_id=payload.marketplace_listing_draft_id,
        actor_user_id=actor_user_id,
        event_type="marketplace_offer_ingested",
        event_payload_json={
            "marketplace_offer_identifier": row.marketplace_offer_identifier,
            "offer_status": row.offer_status,
            "offer_amount": str(row.offer_amount),
            "offer_currency": row.offer_currency,
        },
    )
    session.commit()
    return _to_offer_response(row)


def update_offer_status(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    offer_id: int,
    payload: MarketplaceOfferStatusUpdateRequest,
) -> MarketplaceOfferResponse:
    _validate_offer_management(session, organization_id=organization_id, actor_user_id=actor_user_id)
    row = session.get(MarketplaceOffer, offer_id)
    if row is None or row.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Marketplace offer not found.")
    offer_status = payload.offer_status.strip().lower()
    if offer_status not in OFFER_STATUSES:
        raise HTTPException(status_code=422, detail="Unsupported offer status.")
    row.offer_status = offer_status
    session.add(row)
    session.flush()
    create_pricing_event(
        session,
        organization_id=organization_id,
        marketplace_account_id=row.marketplace_account_id,
        marketplace_listing_draft_id=row.marketplace_listing_draft_id,
        actor_user_id=actor_user_id,
        event_type="marketplace_offer_status_updated",
        event_payload_json={"marketplace_offer_identifier": row.marketplace_offer_identifier, "offer_status": row.offer_status},
    )
    session.commit()
    return _to_offer_response(row)


def list_marketplace_offers(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> MarketplaceOfferListResponse:
    resolution = _validate_offer_visibility(session, organization_id=organization_id, actor_user_id=actor_user_id)
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    base = select(MarketplaceOffer).where(MarketplaceOffer.organization_id == organization_id)
    total = len(session.exec(base).all())
    rows = session.exec(
        base.order_by(MarketplaceOffer.received_at.desc(), MarketplaceOffer.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    summary = generate_offer_summary(session, organization_id=organization_id)
    return MarketplaceOfferListResponse(
        items=[_to_offer_response(row) for row in rows],
        permissions=_permission_response(resolution),
        summary=summary,
        total_items=total,
        limit=limit,
        offset=offset,
    )


def get_marketplace_offer(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    offer_id: int,
) -> MarketplaceOfferResponse:
    _validate_offer_visibility(session, organization_id=organization_id, actor_user_id=actor_user_id)
    row = session.get(MarketplaceOffer, offer_id)
    if row is None or row.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Marketplace offer not found.")
    return _to_offer_response(row)


def generate_offer_summary(
    session: Session,
    *,
    organization_id: int,
) -> MarketplacePricingOfferSummaryResponse:
    rows = session.exec(
        select(MarketplaceOffer).where(MarketplaceOffer.organization_id == organization_id)
    ).all()
    received = sum(1 for row in rows if row.offer_status == OFFER_STATUS_RECEIVED)
    reviewed = sum(1 for row in rows if row.offer_status == OFFER_STATUS_REVIEWED)
    accepted = sum(1 for row in rows if row.offer_status == OFFER_STATUS_ACCEPTED_INTERNAL)
    rejected = sum(1 for row in rows if row.offer_status == OFFER_STATUS_REJECTED_INTERNAL)
    expired = sum(1 for row in rows if row.offer_status == OFFER_STATUS_EXPIRED)
    return MarketplacePricingOfferSummaryResponse(
        total_offers=len(rows),
        received_offers=received,
        reviewed_offers=reviewed,
        accepted_internal_offers=accepted,
        rejected_internal_offers=rejected,
        expired_offers=expired,
    )
