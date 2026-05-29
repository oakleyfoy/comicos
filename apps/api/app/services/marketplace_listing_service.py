from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import (
    InventoryCopy,
    MarketplaceAccount,
    MarketplaceListingDraft,
    MarketplaceListingEvent,
    MarketplaceListingProjection,
)
from app.schemas.marketplace_listings import (
    MarketplaceListingDraftCreateRequest,
    MarketplaceListingDraftDetailResponse,
    MarketplaceListingDraftResponse,
    MarketplaceListingDraftUpdateRequest,
    MarketplaceListingEventResponse,
    MarketplaceListingListResponse,
    MarketplaceListingPermissionResponse,
    MarketplaceListingProjectionListResponse,
    MarketplaceListingProjectionResponse,
    MarketplaceListingValidationErrorResponse,
)
from app.services.marketplace_account_service import ACCOUNT_STATUS_CONNECTED
from app.services.marketplace_listing_projection import (
    generate_listing_projection,
    list_listing_projections,
)
from app.services.marketplace_listing_validation import (
    LISTING_STATUS_ARCHIVED,
    LISTING_STATUS_DRAFT,
    LISTING_STATUSES_MUTABLE,
    VALIDATION_STATUS_PENDING,
    VALIDATION_STATUS_VALID,
    validate_listing_draft,
    validate_marketplace_account_listing_access,
    validate_inventory_listing_eligibility,
)
from app.services.marketplace_permissions import (
    MarketplacePermissionResolution,
    resolve_marketplace_permissions,
    validate_marketplace_management,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


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


def _permission_response(resolution: MarketplacePermissionResolution) -> MarketplaceListingPermissionResponse:
    return MarketplaceListingPermissionResponse(
        can_view=resolution.can_view,
        can_manage=resolution.can_manage,
    )


def _validation_error_responses(draft: MarketplaceListingDraft, session: Session, *, organization_id: int):
    result = validate_listing_draft(session, organization_id=organization_id, draft=draft)
    return [
        MarketplaceListingValidationErrorResponse(code=row.code, message=row.message) for row in result.errors
    ]


def _to_draft_response(row: MarketplaceListingDraft) -> MarketplaceListingDraftResponse:
    return MarketplaceListingDraftResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        marketplace_account_id=row.marketplace_account_id,
        inventory_item_id=row.inventory_item_id,
        listing_title=row.listing_title,
        listing_description=row.listing_description,
        listing_price=row.listing_price,
        listing_currency=row.listing_currency,
        listing_quantity=row.listing_quantity,
        listing_status=row.listing_status,
        validation_status=row.validation_status,
        created_by_user_id=row.created_by_user_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        archived_at=row.archived_at,
    )


def _to_projection_response(row: MarketplaceListingProjection) -> MarketplaceListingProjectionResponse:
    return MarketplaceListingProjectionResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        marketplace_listing_draft_id=row.marketplace_listing_draft_id,
        marketplace_type=row.marketplace_type,
        projection_payload_json=dict(row.projection_payload_json or {}),
        projection_status=row.projection_status,
        generated_at=row.generated_at,
    )


def _to_event_response(row: MarketplaceListingEvent) -> MarketplaceListingEventResponse:
    return MarketplaceListingEventResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        marketplace_listing_draft_id=row.marketplace_listing_draft_id,
        actor_user_id=row.actor_user_id,
        event_type=row.event_type,
        event_payload_json=dict(row.event_payload_json or {}),
        created_at=row.created_at,
    )


def _draft_or_404(
    session: Session,
    *,
    organization_id: int,
    listing_id: int,
) -> MarketplaceListingDraft:
    row = session.get(MarketplaceListingDraft, listing_id)
    if row is None or row.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Marketplace listing draft not found.")
    return row


def _record_unauthorized_listing_attempt(
    session: Session,
    *,
    organization_id: int,
    marketplace_listing_draft_id: int | None,
    actor_user_id: int | None,
    action: str,
    reason: str,
    extra_payload: dict[str, Any] | None = None,
) -> None:
    create_listing_event(
        session,
        organization_id=organization_id,
        marketplace_listing_draft_id=marketplace_listing_draft_id,
        actor_user_id=actor_user_id,
        event_type="unauthorized_marketplace_listing_access_attempt",
        event_payload_json=_json_safe(
            {
                "action": action,
                "reason": reason,
                **(extra_payload or {}),
            }
        ),
    )
    session.commit()


def _apply_validation_state(session: Session, *, organization_id: int, draft: MarketplaceListingDraft) -> None:
    account = session.get(MarketplaceAccount, draft.marketplace_account_id)
    inv = session.get(InventoryCopy, draft.inventory_item_id)
    result = validate_listing_draft(
        session,
        organization_id=organization_id,
        draft=draft,
        marketplace_account=account,
        inventory=inv,
    )
    draft.validation_status = result.validation_status
    session.add(draft)


def create_listing_event(
    session: Session,
    *,
    organization_id: int,
    marketplace_listing_draft_id: int | None,
    actor_user_id: int | None,
    event_type: str,
    event_payload_json: dict[str, Any],
) -> MarketplaceListingEvent:
    row = MarketplaceListingEvent(
        organization_id=organization_id,
        marketplace_listing_draft_id=marketplace_listing_draft_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        event_payload_json=_json_safe(event_payload_json),
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return row


def _listing_events_for_draft(session: Session, *, draft_id: int) -> list[MarketplaceListingEventResponse]:
    rows = session.exec(
        select(MarketplaceListingEvent)
        .where(MarketplaceListingEvent.marketplace_listing_draft_id == draft_id)
        .order_by(MarketplaceListingEvent.created_at.asc(), MarketplaceListingEvent.id.asc())
    ).all()
    return [_to_event_response(row) for row in rows]


def _recent_projections(session: Session, *, draft_id: int, limit: int = 20) -> list[MarketplaceListingProjectionResponse]:
    rows = session.exec(
        select(MarketplaceListingProjection)
        .where(MarketplaceListingProjection.marketplace_listing_draft_id == draft_id)
        .order_by(MarketplaceListingProjection.generated_at.desc(), MarketplaceListingProjection.id.desc())
        .limit(limit)
    ).all()
    return [_to_projection_response(row) for row in rows]


def validate_listing_visibility(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    listing_id: int | None = None,
    action: str = "marketplace_listing:view",
) -> MarketplacePermissionResolution:
    resolution = resolve_marketplace_permissions(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
    )
    if not resolution.can_view:
        _record_unauthorized_listing_attempt(
            session,
            organization_id=organization_id,
            marketplace_listing_draft_id=listing_id,
            actor_user_id=actor_user_id,
            action=action,
            reason=resolution.reason,
        )
        raise HTTPException(status_code=403, detail="Marketplace listing visibility is denied for this organization.")
    return resolution


def list_listing_drafts(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> MarketplaceListingListResponse:
    resolution = validate_listing_visibility(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
    )
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    base = select(MarketplaceListingDraft).where(MarketplaceListingDraft.organization_id == organization_id)
    total = len(session.exec(base).all())
    rows = session.exec(
        base.order_by(MarketplaceListingDraft.created_at.asc(), MarketplaceListingDraft.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return MarketplaceListingListResponse(
        items=[_to_draft_response(row) for row in rows],
        permissions=_permission_response(resolution),
        total_items=total,
        limit=limit,
        offset=offset,
    )


def get_listing_draft(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    listing_id: int,
) -> MarketplaceListingDraftDetailResponse:
    resolution = validate_listing_visibility(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        listing_id=listing_id,
    )
    draft = _draft_or_404(session, organization_id=organization_id, listing_id=listing_id)
    return MarketplaceListingDraftDetailResponse(
        draft=_to_draft_response(draft),
        validation_errors=_validation_error_responses(draft, session, organization_id=organization_id),
        permissions=_permission_response(resolution),
        listing_events=_listing_events_for_draft(session, draft_id=int(draft.id or 0)),
        projections=_recent_projections(session, draft_id=int(draft.id or 0)),
    )


def create_listing_draft(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    payload: MarketplaceListingDraftCreateRequest,
) -> MarketplaceListingDraftDetailResponse:
    validate_marketplace_management(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
    )
    account = validate_marketplace_account_listing_access(
        session,
        organization_id=organization_id,
        marketplace_account_id=payload.marketplace_account_id,
    )
    if account.account_status != ACCOUNT_STATUS_CONNECTED:
        raise HTTPException(status_code=409, detail="Marketplace account must be connected to create listings.")
    validate_inventory_listing_eligibility(
        session,
        organization_id=organization_id,
        inventory_item_id=payload.inventory_item_id,
    )

    now = utc_now()
    draft = MarketplaceListingDraft(
        organization_id=organization_id,
        marketplace_account_id=payload.marketplace_account_id,
        inventory_item_id=payload.inventory_item_id,
        listing_title=payload.listing_title.strip(),
        listing_description=(payload.listing_description or "").strip() or None,
        listing_price=payload.listing_price,
        listing_currency=(payload.listing_currency or "USD").strip().upper(),
        listing_quantity=payload.listing_quantity,
        listing_status=LISTING_STATUS_DRAFT,
        validation_status=VALIDATION_STATUS_PENDING,
        created_by_user_id=actor_user_id,
        created_at=now,
        updated_at=now,
    )
    session.add(draft)
    session.flush()
    _apply_validation_state(session, organization_id=organization_id, draft=draft)
    create_listing_event(
        session,
        organization_id=organization_id,
        marketplace_listing_draft_id=int(draft.id or 0),
        actor_user_id=actor_user_id,
        event_type="marketplace_listing_draft_created",
        event_payload_json={
            "inventory_item_id": draft.inventory_item_id,
            "listing_status": draft.listing_status,
            "marketplace_account_id": draft.marketplace_account_id,
            "validation_status": draft.validation_status,
        },
    )
    session.commit()
    session.refresh(draft)
    return get_listing_draft(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        listing_id=int(draft.id or 0),
    )


def update_listing_draft(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    listing_id: int,
    payload: MarketplaceListingDraftUpdateRequest,
) -> MarketplaceListingDraftDetailResponse:
    validate_marketplace_management(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
    )
    draft = _draft_or_404(session, organization_id=organization_id, listing_id=listing_id)
    if draft.listing_status == LISTING_STATUS_ARCHIVED:
        raise HTTPException(status_code=409, detail="Archived listing drafts cannot be updated.")

    changed_fields: list[str] = []
    if payload.listing_title is not None:
        draft.listing_title = payload.listing_title.strip()
        changed_fields.append("listing_title")
    if payload.listing_description is not None:
        draft.listing_description = payload.listing_description.strip() or None
        changed_fields.append("listing_description")
    if payload.listing_price is not None:
        draft.listing_price = payload.listing_price
        changed_fields.append("listing_price")
    if payload.listing_currency is not None:
        draft.listing_currency = payload.listing_currency.strip().upper()
        changed_fields.append("listing_currency")
    if payload.listing_quantity is not None:
        draft.listing_quantity = payload.listing_quantity
        changed_fields.append("listing_quantity")
    if payload.listing_status is not None:
        normalized = payload.listing_status.strip().lower()
        if normalized not in LISTING_STATUSES_MUTABLE:
            raise HTTPException(status_code=422, detail="Unsupported listing status transition.")
        draft.listing_status = normalized
        changed_fields.append("listing_status")

    draft.updated_at = utc_now()
    session.add(draft)
    _apply_validation_state(session, organization_id=organization_id, draft=draft)
    create_listing_event(
        session,
        organization_id=organization_id,
        marketplace_listing_draft_id=int(draft.id or 0),
        actor_user_id=actor_user_id,
        event_type="marketplace_listing_draft_updated",
        event_payload_json={
            "changed_fields": sorted(changed_fields),
            "listing_status": draft.listing_status,
            "validation_status": draft.validation_status,
        },
    )
    session.commit()
    session.refresh(draft)
    return get_listing_draft(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        listing_id=int(draft.id or 0),
    )


def archive_listing_draft(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    listing_id: int,
) -> MarketplaceListingDraftDetailResponse:
    validate_marketplace_management(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
    )
    draft = _draft_or_404(session, organization_id=organization_id, listing_id=listing_id)
    if draft.listing_status == LISTING_STATUS_ARCHIVED and draft.archived_at is not None:
        return get_listing_draft(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            listing_id=listing_id,
        )

    now = utc_now()
    draft.listing_status = LISTING_STATUS_ARCHIVED
    draft.archived_at = now
    draft.updated_at = now
    session.add(draft)
    _apply_validation_state(session, organization_id=organization_id, draft=draft)
    create_listing_event(
        session,
        organization_id=organization_id,
        marketplace_listing_draft_id=int(draft.id or 0),
        actor_user_id=actor_user_id,
        event_type="marketplace_listing_draft_archived",
        event_payload_json={
            "archived_at": draft.archived_at,
            "listing_status": draft.listing_status,
            "validation_status": draft.validation_status,
        },
    )
    session.commit()
    session.refresh(draft)
    return get_listing_draft(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        listing_id=int(draft.id or 0),
    )


def generate_projection_for_draft(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    listing_id: int,
) -> MarketplaceListingDraftDetailResponse:
    validate_marketplace_management(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
    )
    draft = _draft_or_404(session, organization_id=organization_id, listing_id=listing_id)
    account = validate_marketplace_account_listing_access(
        session,
        organization_id=organization_id,
        marketplace_account_id=draft.marketplace_account_id,
    )
    validation = validate_listing_draft(
        session,
        organization_id=organization_id,
        draft=draft,
        marketplace_account=account,
    )
    draft.validation_status = validation.validation_status
    session.add(draft)

    if validation.validation_status != VALIDATION_STATUS_VALID:
        create_listing_event(
            session,
            organization_id=organization_id,
            marketplace_listing_draft_id=int(draft.id or 0),
            actor_user_id=actor_user_id,
            event_type="marketplace_listing_validation_failed",
            event_payload_json={
                "validation_errors": [{"code": row.code, "message": row.message} for row in validation.errors],
                "validation_status": validation.validation_status,
            },
        )
        session.commit()
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Listing draft failed validation.",
                "validation_errors": [{"code": row.code, "message": row.message} for row in validation.errors],
            },
        )

    projection = generate_listing_projection(
        session,
        organization_id=organization_id,
        draft=draft,
        marketplace_type=account.marketplace_type,
    )
    create_listing_event(
        session,
        organization_id=organization_id,
        marketplace_listing_draft_id=int(draft.id or 0),
        actor_user_id=actor_user_id,
        event_type="marketplace_listing_projection_generated",
        event_payload_json={
            "marketplace_type": projection.marketplace_type,
            "projection_id": int(projection.id or 0),
            "projection_status": projection.projection_status,
        },
    )
    session.commit()
    return get_listing_draft(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        listing_id=int(draft.id or 0),
    )


def list_projections_for_draft(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    listing_id: int,
    limit: int,
    offset: int,
) -> MarketplaceListingProjectionListResponse:
    validate_listing_visibility(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        listing_id=listing_id,
    )
    _draft_or_404(session, organization_id=organization_id, listing_id=listing_id)
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    rows, total = list_listing_projections(
        session,
        organization_id=organization_id,
        marketplace_listing_draft_id=listing_id,
        limit=limit,
        offset=offset,
    )
    return MarketplaceListingProjectionListResponse(
        items=[_to_projection_response(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )
