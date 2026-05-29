from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import (
    MarketplaceAccount,
    MarketplaceListingDraft,
    MarketplacePriceRecommendation,
    MarketplacePricingEvent,
    MarketplacePricingRule,
)
from app.schemas.marketplace_pricing import (
    MarketplacePriceRecommendationGenerateRequest,
    MarketplacePriceRecommendationListResponse,
    MarketplacePriceRecommendationResponse,
    MarketplacePriceRecommendationReviewRequest,
    MarketplacePricingEventResponse,
    MarketplacePricingPermissionResponse,
    MarketplacePricingRuleCreateRequest,
    MarketplacePricingRuleListResponse,
    MarketplacePricingRuleResponse,
    MarketplacePricingRuleUpdateRequest,
)
from app.services.marketplace_permissions import (
    MarketplacePermissionResolution,
    resolve_marketplace_permissions,
)
from app.services.marketplace_pricing_rules import (
    PricingRuleValidationResult,
    evaluate_pricing_rules,
    list_active_pricing_rules,
    normalize_pricing_rule_payload,
    resolve_rule_priority,
    validate_pricing_rule,
)

RECOMMENDATION_STATUS_GENERATED = "generated"
RECOMMENDATION_STATUS_REVIEWED = "reviewed"
RECOMMENDATION_STATUS_APPLIED_INTERNAL = "applied_internal"
RECOMMENDATION_STATUS_DISMISSED = "dismissed"
RECOMMENDATION_STATUSES = {
    RECOMMENDATION_STATUS_GENERATED,
    RECOMMENDATION_STATUS_REVIEWED,
    RECOMMENDATION_STATUS_APPLIED_INTERNAL,
    RECOMMENDATION_STATUS_DISMISSED,
}

PRICING_RULE_STATUS_ACTIVE = "active"
PRICING_RULE_STATUS_INACTIVE = "inactive"
PRICING_RULE_STATUSES = {PRICING_RULE_STATUS_ACTIVE, PRICING_RULE_STATUS_INACTIVE}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_decimal(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


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


def _permission_response(resolution: MarketplacePermissionResolution) -> MarketplacePricingPermissionResponse:
    return MarketplacePricingPermissionResponse(can_view=resolution.can_view, can_manage=resolution.can_manage)


def _to_recommendation_response(row: MarketplacePriceRecommendation) -> MarketplacePriceRecommendationResponse:
    return MarketplacePriceRecommendationResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        marketplace_account_id=row.marketplace_account_id,
        marketplace_listing_draft_id=row.marketplace_listing_draft_id,
        inventory_item_id=row.inventory_item_id,
        recommendation_type=row.recommendation_type,
        recommended_price=row.recommended_price,
        current_listing_price=row.current_listing_price,
        floor_price=row.floor_price,
        ceiling_price=row.ceiling_price,
        recommendation_reason=row.recommendation_reason,
        recommendation_status=row.recommendation_status,
        generated_at=row.generated_at,
        reviewed_at=row.reviewed_at,
    )


def _to_offer_response(row) -> MarketplaceOfferResponse:
    from app.schemas.marketplace_pricing import MarketplaceOfferResponse

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


def _to_rule_response(row: MarketplacePricingRule) -> MarketplacePricingRuleResponse:
    return MarketplacePricingRuleResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        rule_key=row.rule_key,
        rule_name=row.rule_name,
        rule_status=row.rule_status,
        rule_payload_json=dict(row.rule_payload_json or {}),
        created_by_user_id=row.created_by_user_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_event_response(row: MarketplacePricingEvent) -> MarketplacePricingEventResponse:
    return MarketplacePricingEventResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        marketplace_account_id=row.marketplace_account_id,
        marketplace_listing_draft_id=row.marketplace_listing_draft_id,
        actor_user_id=row.actor_user_id,
        event_type=row.event_type,
        event_payload_json=dict(row.event_payload_json or {}),
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


def create_pricing_event(
    session: Session,
    *,
    organization_id: int,
    marketplace_account_id: int | None,
    marketplace_listing_draft_id: int | None,
    actor_user_id: int | None,
    event_type: str,
    event_payload_json: dict[str, Any],
) -> MarketplacePricingEvent:
    row = MarketplacePricingEvent(
        organization_id=organization_id,
        marketplace_account_id=marketplace_account_id,
        marketplace_listing_draft_id=marketplace_listing_draft_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        event_payload_json=_json_safe(event_payload_json),
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return row


def _validate_pricing_visibility(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    action: str = "marketplace_pricing:view",
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
        raise HTTPException(status_code=403, detail="Marketplace pricing visibility is denied for this organization.")
    return resolution


def _validate_pricing_management(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    marketplace_account_id: int | None = None,
    marketplace_listing_draft_id: int | None = None,
    action: str = "marketplace_pricing:manage",
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
        raise HTTPException(status_code=403, detail="Marketplace pricing management is denied for this organization.")
    if marketplace_account_id is not None:
        _account_or_404(session, organization_id=organization_id, marketplace_account_id=marketplace_account_id)
    if marketplace_listing_draft_id is not None:
        _listing_or_404(session, organization_id=organization_id, marketplace_listing_draft_id=marketplace_listing_draft_id)
    return resolution


def list_pricing_rules(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> MarketplacePricingRuleListResponse:
    resolution = _validate_pricing_visibility(session, organization_id=organization_id, actor_user_id=actor_user_id)
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    base = select(MarketplacePricingRule).where(MarketplacePricingRule.organization_id == organization_id)
    total = len(session.exec(base).all())
    rows = session.exec(
        base.order_by(MarketplacePricingRule.updated_at.desc(), MarketplacePricingRule.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return MarketplacePricingRuleListResponse(
        items=[_to_rule_response(row) for row in rows],
        permissions=_permission_response(resolution),
        total_items=total,
        limit=limit,
        offset=offset,
    )


def create_pricing_rule(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    payload: MarketplacePricingRuleCreateRequest,
) -> MarketplacePricingRuleResponse:
    _validate_pricing_management(session, organization_id=organization_id, actor_user_id=actor_user_id)
    validation = validate_pricing_rule(
        organization_id=organization_id,
        rule_key=payload.rule_key,
        rule_name=payload.rule_name,
        rule_status=payload.rule_status,
        rule_payload_json=payload.rule_payload_json,
    )
    if not validation.is_valid:
        raise HTTPException(
            status_code=422,
            detail=[{"code": err.code, "message": err.message} for err in validation.errors],
        )
    existing = session.exec(
        select(MarketplacePricingRule)
        .where(MarketplacePricingRule.organization_id == organization_id)
        .where(MarketplacePricingRule.rule_key == payload.rule_key.strip())
        .order_by(MarketplacePricingRule.id.asc())
    ).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Pricing rule key already exists for this organization.")
    now = utc_now()
    row = MarketplacePricingRule(
        organization_id=organization_id,
        rule_key=payload.rule_key.strip(),
        rule_name=payload.rule_name.strip(),
        rule_status=payload.rule_status.strip().lower(),
        rule_payload_json=validation.normalized_payload,
        created_by_user_id=actor_user_id,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    create_pricing_event(
        session,
        organization_id=organization_id,
        marketplace_account_id=None,
        marketplace_listing_draft_id=None,
        actor_user_id=actor_user_id,
        event_type="marketplace_pricing_rule_created",
        event_payload_json={"rule_key": row.rule_key, "rule_status": row.rule_status},
    )
    session.commit()
    return _to_rule_response(row)


def update_pricing_rule(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    rule_id: int,
    payload: MarketplacePricingRuleUpdateRequest,
) -> MarketplacePricingRuleResponse:
    _validate_pricing_management(session, organization_id=organization_id, actor_user_id=actor_user_id)
    row = session.get(MarketplacePricingRule, rule_id)
    if row is None or row.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Pricing rule not found.")
    rule_name = payload.rule_name if payload.rule_name is not None else row.rule_name
    rule_status = payload.rule_status if payload.rule_status is not None else row.rule_status
    rule_payload_json = payload.rule_payload_json if payload.rule_payload_json is not None else dict(row.rule_payload_json or {})
    validation = validate_pricing_rule(
        organization_id=organization_id,
        rule_key=row.rule_key,
        rule_name=rule_name,
        rule_status=rule_status,
        rule_payload_json=rule_payload_json,
    )
    if not validation.is_valid:
        raise HTTPException(
            status_code=422,
            detail=[{"code": err.code, "message": err.message} for err in validation.errors],
        )
    row.rule_name = rule_name.strip()
    row.rule_status = rule_status.strip().lower()
    row.rule_payload_json = validation.normalized_payload
    row.updated_at = utc_now()
    session.add(row)
    session.flush()
    create_pricing_event(
        session,
        organization_id=organization_id,
        marketplace_account_id=None,
        marketplace_listing_draft_id=None,
        actor_user_id=actor_user_id,
        event_type="marketplace_pricing_rule_updated",
        event_payload_json={"rule_key": row.rule_key, "rule_status": row.rule_status},
    )
    session.commit()
    return _to_rule_response(row)


def generate_price_recommendation(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    payload: MarketplacePriceRecommendationGenerateRequest,
) -> MarketplacePriceRecommendationResponse:
    _validate_pricing_management(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        marketplace_account_id=payload.marketplace_account_id,
        marketplace_listing_draft_id=payload.marketplace_listing_draft_id,
        action="marketplace_pricing:generate",
    )
    listing = _listing_or_404(
        session,
        organization_id=organization_id,
        marketplace_listing_draft_id=payload.marketplace_listing_draft_id,
    )
    rules = list_active_pricing_rules(session, organization_id=organization_id)
    evaluation = evaluate_pricing_rules(
        current_listing_price=payload.current_listing_price if payload.current_listing_price is not None else listing.listing_price,
        pricing_rules=rules,
    )
    floor_price = payload.floor_price if payload.floor_price is not None else evaluation.floor_price
    ceiling_price = payload.ceiling_price if payload.ceiling_price is not None else evaluation.ceiling_price
    recommended_price = evaluation.recommended_price
    if floor_price is not None and recommended_price < floor_price:
        recommended_price = _normalize_decimal(floor_price)
    if ceiling_price is not None and recommended_price > ceiling_price:
        recommended_price = _normalize_decimal(ceiling_price)
    now = utc_now()
    row = MarketplacePriceRecommendation(
        organization_id=organization_id,
        marketplace_account_id=payload.marketplace_account_id,
        marketplace_listing_draft_id=payload.marketplace_listing_draft_id,
        inventory_item_id=listing.inventory_item_id,
        recommendation_type=payload.recommendation_type.strip().lower(),
        recommended_price=recommended_price,
        current_listing_price=payload.current_listing_price if payload.current_listing_price is not None else listing.listing_price,
        floor_price=floor_price,
        ceiling_price=ceiling_price,
        recommendation_reason=evaluation.recommendation_reason,
        recommendation_status=RECOMMENDATION_STATUS_GENERATED,
        generated_at=now,
    )
    session.add(row)
    session.flush()
    create_pricing_event(
        session,
        organization_id=organization_id,
        marketplace_account_id=payload.marketplace_account_id,
        marketplace_listing_draft_id=payload.marketplace_listing_draft_id,
        actor_user_id=actor_user_id,
        event_type="marketplace_price_recommendation_generated",
        event_payload_json={
            "recommendation_type": row.recommendation_type,
            "recommended_price": str(row.recommended_price),
            "applied_rules": list(evaluation.applied_rule_keys),
        },
    )
    session.commit()
    return _to_recommendation_response(row)


def list_price_recommendations(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> MarketplacePriceRecommendationListResponse:
    resolution = _validate_pricing_visibility(session, organization_id=organization_id, actor_user_id=actor_user_id)
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    base = select(MarketplacePriceRecommendation).where(MarketplacePriceRecommendation.organization_id == organization_id)
    total = len(session.exec(base).all())
    rows = session.exec(
        base.order_by(MarketplacePriceRecommendation.generated_at.desc(), MarketplacePriceRecommendation.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return MarketplacePriceRecommendationListResponse(
        items=[_to_recommendation_response(row) for row in rows],
        permissions=_permission_response(resolution),
        total_items=total,
        limit=limit,
        offset=offset,
    )


def review_price_recommendation(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    recommendation_id: int,
    payload: MarketplacePriceRecommendationReviewRequest,
) -> MarketplacePriceRecommendationResponse:
    _validate_pricing_management(session, organization_id=organization_id, actor_user_id=actor_user_id)
    row = session.get(MarketplacePriceRecommendation, recommendation_id)
    if row is None or row.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Pricing recommendation not found.")
    recommendation_status = payload.recommendation_status.strip().lower()
    if recommendation_status not in RECOMMENDATION_STATUSES:
        raise HTTPException(status_code=422, detail="Unsupported recommendation status.")
    row.recommendation_status = recommendation_status
    row.reviewed_at = utc_now()
    session.add(row)
    session.flush()
    create_pricing_event(
        session,
        organization_id=organization_id,
        marketplace_account_id=row.marketplace_account_id,
        marketplace_listing_draft_id=row.marketplace_listing_draft_id,
        actor_user_id=actor_user_id,
        event_type="marketplace_price_recommendation_reviewed",
        event_payload_json={
            "recommendation_id": int(row.id or 0),
            "recommendation_status": row.recommendation_status,
            "review_reason": payload.review_reason,
        },
    )
    session.commit()
    return _to_recommendation_response(row)


def list_pricing_rule_events(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> list[MarketplacePricingEventResponse]:
    _validate_pricing_visibility(session, organization_id=organization_id, actor_user_id=actor_user_id)
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    rows = session.exec(
        select(MarketplacePricingEvent)
        .where(MarketplacePricingEvent.organization_id == organization_id)
        .order_by(MarketplacePricingEvent.created_at.asc(), MarketplacePricingEvent.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return [_to_event_response(row) for row in rows]
