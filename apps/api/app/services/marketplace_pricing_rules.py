from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_FLOOR
from typing import Any

from sqlmodel import Session, select

from app.models import MarketplacePricingRule

PRICING_RULE_STATUS_ACTIVE = "active"
PRICING_RULE_STATUS_INACTIVE = "inactive"
PRICING_RULE_STATUSES = {PRICING_RULE_STATUS_ACTIVE, PRICING_RULE_STATUS_INACTIVE}

RULE_TYPE_FIXED_MARGIN = "fixed_margin"
RULE_TYPE_MINIMUM_FLOOR = "minimum_floor"
RULE_TYPE_MAXIMUM_CEILING = "maximum_ceiling"
RULE_TYPE_ROUND_TO_ENDING = "round_to_ending"
RULE_TYPE_MARKETPLACE_FEE_BUFFER = "marketplace_fee_buffer"
SUPPORTED_RULE_TYPES = {
    RULE_TYPE_FIXED_MARGIN,
    RULE_TYPE_MINIMUM_FLOOR,
    RULE_TYPE_MAXIMUM_CEILING,
    RULE_TYPE_ROUND_TO_ENDING,
    RULE_TYPE_MARKETPLACE_FEE_BUFFER,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_decimal(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _normalize_decimal_string(value: Any) -> str:
    try:
        return str(_normalize_decimal(value))
    except Exception:
        return str(value)


@dataclass(frozen=True)
class PricingRuleValidationError:
    code: str
    message: str


@dataclass(frozen=True)
class PricingRuleValidationResult:
    is_valid: bool
    normalized_payload: dict[str, Any]
    errors: tuple[PricingRuleValidationError, ...]


@dataclass(frozen=True)
class PricingRuleEvaluationResult:
    recommended_price: Decimal
    floor_price: Decimal | None
    ceiling_price: Decimal | None
    recommendation_reason: str
    applied_rule_keys: tuple[str, ...]


def normalize_pricing_rule_payload(payload: dict[str, Any]) -> dict[str, Any]:
    rule_type = str(payload.get("rule_type", "")).strip().lower()
    normalized: dict[str, Any] = {"rule_type": rule_type}
    if "priority" in payload and payload["priority"] is not None:
        try:
            normalized["priority"] = int(payload["priority"])
        except Exception:
            normalized["priority"] = payload["priority"]
    if rule_type == RULE_TYPE_FIXED_MARGIN:
        if payload.get("margin_amount") is not None:
            normalized["margin_amount"] = _normalize_decimal_string(payload["margin_amount"])
        if payload.get("margin_percent") is not None:
            normalized["margin_percent"] = _normalize_decimal_string(payload["margin_percent"])
    elif rule_type == RULE_TYPE_MINIMUM_FLOOR:
        if payload.get("floor_price") is not None:
            normalized["floor_price"] = _normalize_decimal_string(payload["floor_price"])
    elif rule_type == RULE_TYPE_MAXIMUM_CEILING:
        if payload.get("ceiling_price") is not None:
            normalized["ceiling_price"] = _normalize_decimal_string(payload["ceiling_price"])
    elif rule_type == RULE_TYPE_ROUND_TO_ENDING:
        if payload.get("ending") is not None:
            normalized["ending"] = str(payload["ending"]).strip()
    elif rule_type == RULE_TYPE_MARKETPLACE_FEE_BUFFER:
        if payload.get("buffer_amount") is not None:
            normalized["buffer_amount"] = _normalize_decimal_string(payload["buffer_amount"])
        if payload.get("buffer_percent") is not None:
            normalized["buffer_percent"] = _normalize_decimal_string(payload["buffer_percent"])
    for key in sorted(payload):
        if key in normalized or key == "priority":
            continue
        normalized[key] = payload[key]
    return normalized


def validate_pricing_rule(
    *,
    organization_id: int,
    rule_key: str,
    rule_name: str,
    rule_status: str,
    rule_payload_json: dict[str, Any],
) -> PricingRuleValidationResult:
    errors: list[PricingRuleValidationError] = []
    normalized_payload = normalize_pricing_rule_payload(rule_payload_json)
    rule_type = normalized_payload.get("rule_type", "")

    if "priority" in normalized_payload:
        try:
            normalized_payload["priority"] = int(normalized_payload["priority"])
        except Exception:
            errors.append(PricingRuleValidationError(code="priority_invalid", message="Priority must be an integer."))

    if not rule_key.strip():
        errors.append(PricingRuleValidationError(code="rule_key_required", message="Rule key is required."))
    if not rule_name.strip():
        errors.append(PricingRuleValidationError(code="rule_name_required", message="Rule name is required."))
    if organization_id <= 0:
        errors.append(PricingRuleValidationError(code="organization_invalid", message="Organization scope is invalid."))
    if rule_status not in PRICING_RULE_STATUSES:
        errors.append(PricingRuleValidationError(code="rule_status_invalid", message="Rule status must be active or inactive."))
    if rule_type not in SUPPORTED_RULE_TYPES:
        errors.append(PricingRuleValidationError(code="rule_type_unsupported", message="Unsupported pricing rule type."))
    else:
        if rule_type == RULE_TYPE_FIXED_MARGIN:
            margin_amount = normalized_payload.get("margin_amount")
            margin_percent = normalized_payload.get("margin_percent")
            if margin_amount is None and margin_percent is None:
                errors.append(PricingRuleValidationError(code="fixed_margin_missing_value", message="Fixed margin requires a margin amount or percent."))
            if margin_amount is not None:
                try:
                    Decimal(str(margin_amount))
                except Exception:
                    errors.append(PricingRuleValidationError(code="fixed_margin_amount_invalid", message="Fixed margin amount is invalid."))
            if margin_percent is not None:
                try:
                    Decimal(str(margin_percent))
                except Exception:
                    errors.append(PricingRuleValidationError(code="fixed_margin_percent_invalid", message="Fixed margin percent is invalid."))
        elif rule_type == RULE_TYPE_MINIMUM_FLOOR:
            floor_price = normalized_payload.get("floor_price")
            if floor_price is None:
                errors.append(PricingRuleValidationError(code="minimum_floor_missing_value", message="Minimum floor requires a floor price."))
            else:
                try:
                    Decimal(str(floor_price))
                except Exception:
                    errors.append(PricingRuleValidationError(code="minimum_floor_invalid", message="Minimum floor price is invalid."))
        elif rule_type == RULE_TYPE_MAXIMUM_CEILING:
            ceiling_price = normalized_payload.get("ceiling_price")
            if ceiling_price is None:
                errors.append(PricingRuleValidationError(code="maximum_ceiling_missing_value", message="Maximum ceiling requires a ceiling price."))
            else:
                try:
                    Decimal(str(ceiling_price))
                except Exception:
                    errors.append(PricingRuleValidationError(code="maximum_ceiling_invalid", message="Maximum ceiling price is invalid."))
        elif rule_type == RULE_TYPE_ROUND_TO_ENDING:
            ending = normalized_payload.get("ending")
            if ending is None:
                errors.append(PricingRuleValidationError(code="round_to_ending_missing_value", message="Rounding rules require an ending."))
            else:
                try:
                    ending_value = Decimal(str(ending))
                except Exception:
                    errors.append(PricingRuleValidationError(code="round_to_ending_invalid", message="Rounding ending is invalid."))
                    ending_value = None
                if ending_value is not None and (ending_value < 0 or ending_value >= 1):
                    errors.append(PricingRuleValidationError(code="round_to_ending_invalid", message="Rounding ending must be between 0 and 1."))
        elif rule_type == RULE_TYPE_MARKETPLACE_FEE_BUFFER:
            buffer_amount = normalized_payload.get("buffer_amount")
            buffer_percent = normalized_payload.get("buffer_percent")
            if buffer_amount is None and buffer_percent is None:
                errors.append(PricingRuleValidationError(code="marketplace_fee_buffer_missing_value", message="Marketplace fee buffer requires an amount or percent."))
            if buffer_amount is not None:
                try:
                    Decimal(str(buffer_amount))
                except Exception:
                    errors.append(PricingRuleValidationError(code="marketplace_fee_buffer_amount_invalid", message="Marketplace fee buffer amount is invalid."))
            if buffer_percent is not None:
                try:
                    Decimal(str(buffer_percent))
                except Exception:
                    errors.append(PricingRuleValidationError(code="marketplace_fee_buffer_percent_invalid", message="Marketplace fee buffer percent is invalid."))

    return PricingRuleValidationResult(is_valid=not errors, normalized_payload=normalized_payload, errors=tuple(errors))


def resolve_rule_priority(rule: MarketplacePricingRule) -> tuple[int, datetime, int]:
    payload = dict(rule.rule_payload_json or {})
    priority = int(payload.get("priority", 100))
    return priority, rule.created_at, int(rule.id or 0)


def list_active_pricing_rules(
    session: Session,
    *,
    organization_id: int,
) -> list[MarketplacePricingRule]:
    rows = session.exec(
        select(MarketplacePricingRule)
        .where(MarketplacePricingRule.organization_id == organization_id)
        .where(MarketplacePricingRule.rule_status == PRICING_RULE_STATUS_ACTIVE)
        .order_by(MarketplacePricingRule.updated_at.asc(), MarketplacePricingRule.id.asc())
    ).all()
    return list(rows)


def _round_to_ending(value: Decimal, ending: Decimal) -> Decimal:
    whole = value.to_integral_value(rounding=ROUND_FLOOR)
    candidate = whole + ending
    if candidate < value:
        candidate = whole + Decimal("1.00") + ending
    return candidate.quantize(Decimal("0.01"))


def evaluate_pricing_rules(
    *,
    current_listing_price: Decimal | None,
    pricing_rules: list[MarketplacePricingRule],
) -> PricingRuleEvaluationResult:
    base_price = _normalize_decimal(current_listing_price or Decimal("0.00"))
    floor_price: Decimal | None = None
    ceiling_price: Decimal | None = None
    applied: list[str] = []
    price = base_price
    for rule in sorted(pricing_rules, key=resolve_rule_priority):
        payload = dict(rule.rule_payload_json or {})
        rule_type = str(payload.get("rule_type", "")).strip().lower()
        if rule_type == RULE_TYPE_FIXED_MARGIN:
            if payload.get("margin_amount") is not None:
                price += _normalize_decimal(payload["margin_amount"])
            elif payload.get("margin_percent") is not None:
                price *= Decimal("1.00") + (_normalize_decimal(payload["margin_percent"]) / Decimal("100.00"))
            applied.append(rule.rule_key)
        elif rule_type == RULE_TYPE_MARKETPLACE_FEE_BUFFER:
            if payload.get("buffer_amount") is not None:
                price += _normalize_decimal(payload["buffer_amount"])
            elif payload.get("buffer_percent") is not None:
                price *= Decimal("1.00") + (_normalize_decimal(payload["buffer_percent"]) / Decimal("100.00"))
            applied.append(rule.rule_key)
        elif rule_type == RULE_TYPE_MINIMUM_FLOOR and payload.get("floor_price") is not None:
            floor_value = _normalize_decimal(payload["floor_price"])
            floor_price = floor_value if floor_price is None else max(floor_price, floor_value)
            if price < floor_value:
                price = floor_value
            applied.append(rule.rule_key)
        elif rule_type == RULE_TYPE_MAXIMUM_CEILING and payload.get("ceiling_price") is not None:
            ceiling_value = _normalize_decimal(payload["ceiling_price"])
            ceiling_price = ceiling_value if ceiling_price is None else min(ceiling_price, ceiling_value)
            if price > ceiling_value:
                price = ceiling_value
            applied.append(rule.rule_key)
        elif rule_type == RULE_TYPE_ROUND_TO_ENDING and payload.get("ending") is not None:
            ending = _normalize_decimal(payload["ending"])
            price = _round_to_ending(price, ending)
            applied.append(rule.rule_key)

    if floor_price is not None and price < floor_price:
        price = floor_price
    if ceiling_price is not None and price > ceiling_price:
        price = ceiling_price

    return PricingRuleEvaluationResult(
        recommended_price=price.quantize(Decimal("0.01")),
        floor_price=floor_price,
        ceiling_price=ceiling_price,
        recommendation_reason=", ".join(applied) if applied else "No active pricing rules were applied.",
        applied_rule_keys=tuple(applied),
    )
