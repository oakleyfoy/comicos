from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import MarketplaceAccount, MarketplaceConnectionEvent, MarketplaceCredential
from app.schemas.marketplace_accounts import (
    MarketplaceAccountConnectRequest,
    MarketplaceAccountDetailResponse,
    MarketplaceAccountDisconnectRequest,
    MarketplaceAccountListResponse,
    MarketplaceAccountResponse,
    MarketplaceAccountVerifyRequest,
    MarketplaceConnectionEventResponse,
    MarketplaceCredentialResponse,
    MarketplacePermissionResponse,
    MarketplaceRegistryEntryResponse,
)
from app.services.marketplace_permissions import (
    MarketplacePermissionResolution,
    validate_marketplace_management,
    validate_marketplace_visibility,
)
from app.services.marketplace_registry import MarketplaceDefinition, get_marketplace_definition, list_marketplace_definitions

ACCOUNT_STATUS_CONNECTED = "connected"
ACCOUNT_STATUS_DISCONNECTED = "disconnected"
ACCOUNT_STATUS_SUSPENDED = "suspended"
ACCOUNT_STATUSES = {ACCOUNT_STATUS_CONNECTED, ACCOUNT_STATUS_DISCONNECTED, ACCOUNT_STATUS_SUSPENDED}

VERIFICATION_STATUS_PENDING = "pending"
VERIFICATION_STATUS_VERIFIED = "verified"
VERIFICATION_STATUS_FAILED = "failed"
VERIFICATION_STATUSES = {VERIFICATION_STATUS_PENDING, VERIFICATION_STATUS_VERIFIED, VERIFICATION_STATUS_FAILED}

CREDENTIAL_STATUS_ACTIVE = "active"
CREDENTIAL_STATUS_ROTATED = "rotated"
CREDENTIAL_STATUS_REVOKED = "revoked"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def clamp_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 200), max(offset, 0)


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _normalize_marketplace_key(value: str) -> str:
    return value.strip().lower()


def _normalize_account_status(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in ACCOUNT_STATUSES:
        raise HTTPException(status_code=422, detail="Unsupported marketplace account status.")
    return normalized


def _normalize_verification_status(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in VERIFICATION_STATUSES:
        raise HTTPException(status_code=422, detail="Unsupported marketplace verification status.")
    return normalized


def _normalize_reference(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise HTTPException(status_code=422, detail="Credential reference is required.")
    return normalized


def _registry_response(definition: MarketplaceDefinition) -> MarketplaceRegistryEntryResponse:
    return MarketplaceRegistryEntryResponse(
        marketplace_key=definition.marketplace_key,
        display_name=definition.display_name,
        status=definition.status,
        capability_flags=list(definition.capability_flags),
    )


def _permission_response(resolution: MarketplacePermissionResolution) -> MarketplacePermissionResponse:
    return MarketplacePermissionResponse(
        can_view=resolution.can_view,
        can_manage=resolution.can_manage,
        role_keys=list(resolution.role_keys),
        permission_keys=list(resolution.permission_keys),
    )


def _to_account_response(row: MarketplaceAccount) -> MarketplaceAccountResponse:
    return MarketplaceAccountResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        marketplace_type=row.marketplace_type,
        marketplace_account_id=row.marketplace_account_id,
        display_name=row.display_name,
        account_status=row.account_status,
        verification_status=row.verification_status,
        connected_at=row.connected_at,
        disconnected_at=row.disconnected_at,
        created_at=row.created_at,
    )


def _to_credential_response(row: MarketplaceCredential) -> MarketplaceCredentialResponse:
    return MarketplaceCredentialResponse(
        id=int(row.id or 0),
        marketplace_account_id=row.marketplace_account_id,
        credential_type=row.credential_type,
        credential_reference=row.credential_reference,
        credential_status=row.credential_status,
        rotated_at=row.rotated_at,
        created_at=row.created_at,
    )


def _to_event_response(row: MarketplaceConnectionEvent) -> MarketplaceConnectionEventResponse:
    return MarketplaceConnectionEventResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        marketplace_account_id=row.marketplace_account_id,
        actor_user_id=row.actor_user_id,
        event_type=row.event_type,
        event_payload_json=dict(sorted((row.event_payload_json or {}).items())),
        created_at=row.created_at,
    )


def _account_or_404(session: Session, *, account_id: int) -> MarketplaceAccount:
    account = session.get(MarketplaceAccount, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Marketplace account not found.")
    return account


def _credential_rows(session: Session, *, marketplace_account_id: int) -> list[MarketplaceCredential]:
    return session.exec(
        select(MarketplaceCredential)
        .where(MarketplaceCredential.marketplace_account_id == marketplace_account_id)
        .order_by(MarketplaceCredential.created_at.asc(), MarketplaceCredential.id.asc())
    ).all()


def _event_rows(session: Session, *, organization_id: int, marketplace_account_id: int) -> list[MarketplaceConnectionEvent]:
    return session.exec(
        select(MarketplaceConnectionEvent)
        .where(MarketplaceConnectionEvent.organization_id == organization_id)
        .where(MarketplaceConnectionEvent.marketplace_account_id == marketplace_account_id)
        .order_by(MarketplaceConnectionEvent.created_at.asc(), MarketplaceConnectionEvent.id.asc())
    ).all()


def _detail_response(
    session: Session,
    *,
    account: MarketplaceAccount,
    resolution: MarketplacePermissionResolution,
) -> MarketplaceAccountDetailResponse:
    definition = get_marketplace_definition(account.marketplace_type)
    if definition is None:  # pragma: no cover - defensive
        raise RuntimeError("Marketplace registry entry is missing.")
    return MarketplaceAccountDetailResponse(
        account=_to_account_response(account),
        credentials=[_to_credential_response(row) for row in _credential_rows(session, marketplace_account_id=int(account.id or 0))],
        connection_events=[
            _to_event_response(row)
            for row in _event_rows(session, organization_id=account.organization_id, marketplace_account_id=int(account.id or 0))
        ],
        registry_entry=_registry_response(definition),
        permissions=_permission_response(resolution),
    )


def create_connection_event(
    session: Session,
    *,
    organization_id: int,
    marketplace_account_id: int | None,
    actor_user_id: int | None,
    event_type: str,
    event_payload_json: dict[str, Any],
) -> MarketplaceConnectionEvent:
    row = MarketplaceConnectionEvent(
        organization_id=organization_id,
        marketplace_account_id=marketplace_account_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        event_payload_json=_json_safe(event_payload_json),
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return row


def _activate_credential_reference(
    session: Session,
    *,
    account: MarketplaceAccount,
    credential_type: str,
    credential_reference: str,
    now: datetime,
) -> bool:
    existing_rows = _credential_rows(session, marketplace_account_id=int(account.id or 0))
    exact_match = next(
        (
            row
            for row in existing_rows
            if row.credential_type == credential_type and row.credential_reference == credential_reference
        ),
        None,
    )

    changed = False
    for row in existing_rows:
        if row.credential_type != credential_type:
            continue
        if row.credential_reference == credential_reference:
            if row.credential_status != CREDENTIAL_STATUS_ACTIVE:
                row.credential_status = CREDENTIAL_STATUS_ACTIVE
                row.rotated_at = None
                session.add(row)
                changed = True
            continue
        if row.credential_status == CREDENTIAL_STATUS_ACTIVE:
            row.credential_status = CREDENTIAL_STATUS_ROTATED
            row.rotated_at = now
            session.add(row)
            changed = True

    if exact_match is not None:
        return changed

    session.add(
        MarketplaceCredential(
            marketplace_account_id=int(account.id or 0),
            credential_type=credential_type,
            credential_reference=credential_reference,
            credential_status=CREDENTIAL_STATUS_ACTIVE,
            created_at=now,
        )
    )
    return True


def connect_marketplace_account(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    payload: MarketplaceAccountConnectRequest,
) -> tuple[MarketplaceAccountDetailResponse, bool]:
    resolution = validate_marketplace_management(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
    )
    marketplace_key = _normalize_marketplace_key(payload.marketplace_type)
    definition = get_marketplace_definition(marketplace_key)
    if definition is None:
        raise HTTPException(status_code=422, detail="Unsupported marketplace type.")

    marketplace_account_id = payload.marketplace_account_id.strip()
    display_name = payload.display_name.strip()
    credential_type = payload.credential_type.strip().lower()
    credential_reference = _normalize_reference(payload.credential_reference)
    now = utc_now()

    existing = session.exec(
        select(MarketplaceAccount)
        .where(MarketplaceAccount.marketplace_type == marketplace_key)
        .where(MarketplaceAccount.marketplace_account_id == marketplace_account_id)
        .order_by(MarketplaceAccount.id.asc())
    ).first()

    if existing is not None and existing.organization_id != organization_id:
        raise HTTPException(status_code=409, detail="Marketplace identity is already owned by another organization.")

    created = False
    should_emit_connected_event = False
    if existing is None:
        account = MarketplaceAccount(
            organization_id=organization_id,
            marketplace_type=marketplace_key,
            marketplace_account_id=marketplace_account_id,
            display_name=display_name,
            account_status=ACCOUNT_STATUS_CONNECTED,
            verification_status=VERIFICATION_STATUS_PENDING,
            connected_at=now,
            created_at=now,
        )
        session.add(account)
        session.flush()
        created = True
        should_emit_connected_event = True
    else:
        account = existing
        if account.account_status != ACCOUNT_STATUS_CONNECTED or account.disconnected_at is not None:
            account.account_status = ACCOUNT_STATUS_CONNECTED
            account.connected_at = now
            account.disconnected_at = None
            should_emit_connected_event = True
        if account.display_name != display_name:
            account.display_name = display_name
            should_emit_connected_event = True
        session.add(account)

    credentials_changed = _activate_credential_reference(
        session,
        account=account,
        credential_type=credential_type,
        credential_reference=credential_reference,
        now=now,
    )
    if credentials_changed:
        should_emit_connected_event = True
    if credentials_changed and account.verification_status == VERIFICATION_STATUS_VERIFIED:
        account.verification_status = VERIFICATION_STATUS_PENDING
        session.add(account)

    if should_emit_connected_event:
        create_connection_event(
            session,
            organization_id=organization_id,
            marketplace_account_id=int(account.id or 0),
            actor_user_id=actor_user_id,
            event_type="marketplace_connected",
            event_payload_json={
                "credential_reference": credential_reference,
                "credential_type": credential_type,
                "display_name": account.display_name,
                "marketplace_account_id": account.marketplace_account_id,
                "marketplace_type": account.marketplace_type,
                "verification_status": account.verification_status,
            },
        )

    session.commit()
    session.refresh(account)
    resolution = validate_marketplace_visibility(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        marketplace_account=account,
        requested_account_id=int(account.id or 0),
    )
    return _detail_response(session, account=account, resolution=resolution), created


def disconnect_marketplace_account(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    payload: MarketplaceAccountDisconnectRequest,
) -> MarketplaceAccountDetailResponse:
    account = _account_or_404(session, account_id=payload.account_id)
    resolution = validate_marketplace_management(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        marketplace_account=account,
        requested_account_id=payload.account_id,
    )
    if account.account_status == ACCOUNT_STATUS_DISCONNECTED and account.disconnected_at is not None:
        return _detail_response(session, account=account, resolution=resolution)

    now = utc_now()
    account.account_status = ACCOUNT_STATUS_DISCONNECTED
    account.disconnected_at = now
    session.add(account)
    for credential in _credential_rows(session, marketplace_account_id=int(account.id or 0)):
        if credential.credential_status == CREDENTIAL_STATUS_ACTIVE:
            credential.credential_status = CREDENTIAL_STATUS_REVOKED
            credential.rotated_at = now
            session.add(credential)
    create_connection_event(
        session,
        organization_id=organization_id,
        marketplace_account_id=int(account.id or 0),
        actor_user_id=actor_user_id,
        event_type="marketplace_disconnected",
        event_payload_json={
            "account_status": account.account_status,
            "disconnected_at": account.disconnected_at,
            "reason": payload.reason or "",
        },
    )
    session.commit()
    session.refresh(account)
    visibility = validate_marketplace_visibility(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        marketplace_account=account,
        requested_account_id=payload.account_id,
    )
    return _detail_response(session, account=account, resolution=visibility)


def verify_marketplace_account(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    payload: MarketplaceAccountVerifyRequest,
) -> MarketplaceAccountDetailResponse:
    account = _account_or_404(session, account_id=payload.account_id)
    resolution = validate_marketplace_management(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        marketplace_account=account,
        requested_account_id=payload.account_id,
    )
    verification_status = _normalize_verification_status(payload.verification_status)
    if verification_status == VERIFICATION_STATUS_PENDING:
        raise HTTPException(status_code=422, detail="Verification endpoint only supports verified or failed states.")
    if account.verification_status == verification_status:
        return _detail_response(session, account=account, resolution=resolution)

    account.verification_status = verification_status
    session.add(account)
    event_type = "marketplace_verified" if verification_status == VERIFICATION_STATUS_VERIFIED else "marketplace_verification_failed"
    create_connection_event(
        session,
        organization_id=organization_id,
        marketplace_account_id=int(account.id or 0),
        actor_user_id=actor_user_id,
        event_type=event_type,
        event_payload_json={
            "reason": payload.reason or "",
            "verification_status": verification_status,
        },
    )
    session.commit()
    session.refresh(account)
    visibility = validate_marketplace_visibility(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        marketplace_account=account,
        requested_account_id=payload.account_id,
    )
    return _detail_response(session, account=account, resolution=visibility)


def validate_marketplace_access(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    account_id: int,
) -> tuple[MarketplaceAccount, MarketplacePermissionResolution]:
    account = _account_or_404(session, account_id=account_id)
    resolution = validate_marketplace_visibility(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        marketplace_account=account,
        requested_account_id=account_id,
    )
    return account, resolution


def get_marketplace_account_detail(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    account_id: int,
) -> MarketplaceAccountDetailResponse:
    account, resolution = validate_marketplace_access(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        account_id=account_id,
    )
    return _detail_response(session, account=account, resolution=resolution)


def list_marketplace_accounts(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> MarketplaceAccountListResponse:
    resolution = validate_marketplace_visibility(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
    )
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    rows = session.exec(
        select(MarketplaceAccount)
        .where(MarketplaceAccount.organization_id == organization_id)
        .order_by(
            MarketplaceAccount.marketplace_type.asc(),
            MarketplaceAccount.display_name.asc(),
            MarketplaceAccount.marketplace_account_id.asc(),
            MarketplaceAccount.id.asc(),
        )
    ).all()
    items = [_to_account_response(row) for row in rows]
    return MarketplaceAccountListResponse(
        items=items[offset : offset + limit],
        registry=[_registry_response(definition) for definition in list_marketplace_definitions()],
        permissions=_permission_response(resolution),
        total_items=len(items),
        limit=limit,
        offset=offset,
    )
