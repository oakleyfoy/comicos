from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import MarketplaceAccount, MarketplaceEvent
from app.services.marketplace_event_registry import get_marketplace_event_definition
from app.services.marketplace_permissions import resolve_marketplace_permissions


@dataclass(frozen=True)
class MarketplaceEventValidationError:
    code: str
    message: str


@dataclass(frozen=True)
class MarketplaceEventSignatureShellResult:
    is_verified: bool
    errors: tuple[MarketplaceEventValidationError, ...]


@dataclass(frozen=True)
class MarketplaceEventValidationResult:
    is_valid: bool
    normalized_payload: dict[str, Any]
    errors: tuple[MarketplaceEventValidationError, ...]
    event_type: str
    marketplace_type: str


def _normalize_payload(payload: Any) -> dict[str, Any]:
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Event payload must be a JSON object.")
    return {str(key): value for key, value in sorted(payload.items(), key=lambda pair: str(pair[0]))}


def detect_duplicate_event(
    session: Session,
    *,
    marketplace_account_id: int,
    external_event_identifier: str,
    exclude_event_id: int | None = None,
) -> MarketplaceEvent | None:
    query = (
        select(MarketplaceEvent)
        .where(MarketplaceEvent.marketplace_account_id == marketplace_account_id)
        .where(MarketplaceEvent.external_event_identifier == external_event_identifier.strip())
        .order_by(MarketplaceEvent.id.asc())
    )
    if exclude_event_id is not None:
        query = query.where(MarketplaceEvent.id != exclude_event_id)
    return session.exec(query).first()


def validate_event_signature_shell(*, event_payload_json: dict[str, Any]) -> MarketplaceEventSignatureShellResult:
    _normalize_payload(event_payload_json)
    return MarketplaceEventSignatureShellResult(is_verified=False, errors=())


def validate_event_payload(*, event_type: str, event_payload_json: dict[str, Any]) -> tuple[bool, tuple[MarketplaceEventValidationError, ...], dict[str, Any]]:
    errors: list[MarketplaceEventValidationError] = []
    normalized_payload = _normalize_payload(event_payload_json)
    if not event_type.strip():
        errors.append(MarketplaceEventValidationError(code="event_type_required", message="Event type is required."))
    return not errors, tuple(errors), normalized_payload


def resolve_event_validation_errors(errors: tuple[MarketplaceEventValidationError, ...]) -> list[dict[str, str]]:
    return [{"code": error.code, "message": error.message} for error in errors]


def validate_marketplace_event(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    marketplace_account_id: int,
    external_event_identifier: str,
    event_type: str,
    event_payload_json: dict[str, Any],
    exclude_event_id: int | None = None,
) -> MarketplaceEventValidationResult:
    errors: list[MarketplaceEventValidationError] = []
    resolved_event_type = event_type.strip().lower()
    normalized_payload = _normalize_payload(event_payload_json)

    account = session.get(MarketplaceAccount, marketplace_account_id)
    if account is None:
        errors.append(MarketplaceEventValidationError(code="marketplace_account_not_found", message="Marketplace account not found."))
    elif account.organization_id != organization_id:
        errors.append(
            MarketplaceEventValidationError(
                code="marketplace_account_cross_organization",
                message="Marketplace account does not belong to this organization.",
            )
        )

    resolution = resolve_marketplace_permissions(session, organization_id=organization_id, actor_user_id=actor_user_id)
    if not resolution.can_view:
        errors.append(MarketplaceEventValidationError(code="marketplace_access_denied", message="Marketplace access is denied."))

    if not external_event_identifier.strip():
        errors.append(MarketplaceEventValidationError(code="external_event_identifier_required", message="External event identifier is required."))

    definition = get_marketplace_event_definition(resolved_event_type)
    if definition is None:
        errors.append(MarketplaceEventValidationError(code="event_type_invalid", message="Unsupported marketplace event type."))

    if account is not None and account.organization_id == organization_id and external_event_identifier.strip():
        duplicate = detect_duplicate_event(
            session,
            marketplace_account_id=marketplace_account_id,
            external_event_identifier=external_event_identifier,
            exclude_event_id=exclude_event_id,
        )
        if duplicate is not None:
            errors.append(
                MarketplaceEventValidationError(
                    code="duplicate_event_detected",
                    message="Event has already been ingested for this marketplace account.",
                )
            )

    return MarketplaceEventValidationResult(
        is_valid=not errors,
        normalized_payload=normalized_payload,
        errors=tuple(errors),
        event_type=resolved_event_type,
        marketplace_type=account.marketplace_type if account is not None else "",
    )
