from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, col, func, select

from app.models.mobile_foundation import (
    MobileDevice,
    MobileFoundationEvent,
    MobileSession,
    OfflineSyncContract,
)
from app.schemas.mobile_foundation import (
    MobileDeviceListResponse,
    MobileDeviceRegisterRequest,
    MobileDeviceResponse,
    MobileDeviceUpdateRequest,
    MobileFoundationDashboardResponse,
    MobileFoundationEventResponse,
    MobilePermissionResponse,
    MobileSessionCreateRequest,
    MobileSessionListResponse,
    MobileSessionResponse,
    OfflineSyncContractCreateRequest,
    OfflineSyncContractListResponse,
    OfflineSyncContractResponse,
)
from app.services.marketplace_permissions import MarketplacePermissionResolution
from app.services.mobile_device_security_service import validate_mobile_device_access
from app.services.mobile_permissions import validate_mobile_manage_access, validate_mobile_view_access
from app.services.offline_runtime_registry import (
    DEVICE_STATUS_ACTIVE,
    SESSION_STATUS_ACTIVE,
    SESSION_STATUS_EXPIRED,
    SESSION_STATUS_TERMINATED,
    can_transition_device_status,
    can_transition_session_status,
    list_device_statuses,
    list_session_statuses,
    list_sync_contract_types,
    validate_device_status,
    validate_session_status,
    validate_sync_contract_type,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _permission_response(resolution: MarketplacePermissionResolution) -> MobilePermissionResponse:
    return MobilePermissionResponse(can_view=resolution.can_view, can_manage=resolution.can_manage)


def create_mobile_event(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int | None,
    event_type: str,
    event_payload_json: dict | None = None,
) -> MobileFoundationEvent:
    row = MobileFoundationEvent(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        event_payload_json=_json_safe(event_payload_json or {}),
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return row


def _device_response(row: MobileDevice) -> MobileDeviceResponse:
    return MobileDeviceResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        device_identifier=row.device_identifier,
        device_name=row.device_name,
        device_type=row.device_type,
        device_status=row.device_status,
        last_seen_at=row.last_seen_at,
        created_at=row.created_at,
    )


def _session_response(row: MobileSession) -> MobileSessionResponse:
    return MobileSessionResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        device_id=row.device_id,
        user_id=row.user_id,
        session_status=row.session_status,
        started_at=row.started_at,
        ended_at=row.ended_at,
    )


def _contract_response(row: OfflineSyncContract) -> OfflineSyncContractResponse:
    return OfflineSyncContractResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        contract_type=row.contract_type,
        contract_payload_json=row.contract_payload_json,
        created_at=row.created_at,
    )


def _event_response(row: MobileFoundationEvent) -> MobileFoundationEventResponse:
    return MobileFoundationEventResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        actor_user_id=row.actor_user_id,
        event_type=row.event_type,
        event_payload_json=row.event_payload_json,
        created_at=row.created_at,
    )


def _get_org_device(session: Session, *, organization_id: int, device_id: int) -> MobileDevice:
    device = session.get(MobileDevice, device_id)
    if device is None or device.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Mobile device not found.")
    return device


def register_mobile_device(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    payload: MobileDeviceRegisterRequest,
) -> tuple[MobileDeviceResponse, bool]:
    validate_mobile_manage_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    existing = session.exec(
        select(MobileDevice)
        .where(MobileDevice.organization_id == organization_id)
        .where(MobileDevice.device_identifier == payload.device_identifier)
    ).first()
    now = utc_now()
    if existing is not None:
        existing.device_name = payload.device_name
        existing.device_type = payload.device_type
        existing.last_seen_at = now
        if existing.device_status != DEVICE_STATUS_ACTIVE:
            existing.device_status = DEVICE_STATUS_ACTIVE
        session.add(existing)
        create_mobile_event(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            event_type="mobile_device_seen",
            event_payload_json={"device_id": int(existing.id or 0), "device_identifier": existing.device_identifier},
        )
        session.commit()
        session.refresh(existing)
        return _device_response(existing), False

    device = MobileDevice(
        organization_id=organization_id,
        device_identifier=payload.device_identifier,
        device_name=payload.device_name,
        device_type=payload.device_type,
        device_status=DEVICE_STATUS_ACTIVE,
        last_seen_at=now,
        created_at=now,
    )
    session.add(device)
    session.flush()
    create_mobile_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type="mobile_device_registered",
        event_payload_json={
            "device_id": int(device.id or 0),
            "device_identifier": device.device_identifier,
            "device_type": device.device_type,
        },
    )
    session.commit()
    session.refresh(device)
    return _device_response(device), True


def update_mobile_device(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    device_id: int,
    payload: MobileDeviceUpdateRequest,
) -> MobileDeviceResponse:
    validate_mobile_manage_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    device = _get_org_device(session, organization_id=organization_id, device_id=device_id)
    changes: dict[str, Any] = {}
    if payload.device_name is not None and payload.device_name != device.device_name:
        changes["device_name"] = {"before": device.device_name, "after": payload.device_name}
        device.device_name = payload.device_name
    if payload.device_type is not None and payload.device_type != device.device_type:
        changes["device_type"] = {"before": device.device_type, "after": payload.device_type}
        device.device_type = payload.device_type
    if payload.device_status is not None:
        try:
            validate_device_status(payload.device_status)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if not can_transition_device_status(device.device_status, payload.device_status):
            raise HTTPException(status_code=422, detail="Invalid device status transition.")
        if payload.device_status != device.device_status:
            changes["device_status"] = {"before": device.device_status, "after": payload.device_status}
            device.device_status = payload.device_status
    if payload.record_seen or changes:
        device.last_seen_at = utc_now()
        if payload.record_seen and not changes:
            create_mobile_event(
                session,
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                event_type="mobile_device_seen",
                event_payload_json={"device_id": device_id, "device_identifier": device.device_identifier},
            )
    if changes:
        create_mobile_event(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            event_type="mobile_device_updated",
            event_payload_json={"device_id": device_id, "changes": changes},
        )
    session.add(device)
    session.commit()
    session.refresh(device)
    return _device_response(device)


def _terminate_mobile_session_row(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    row: MobileSession,
    session_status: str,
) -> None:
    if row.session_status != SESSION_STATUS_ACTIVE:
        return
    try:
        validate_session_status(session_status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if session_status not in {SESSION_STATUS_TERMINATED, SESSION_STATUS_EXPIRED}:
        raise HTTPException(status_code=422, detail="Unsupported session end status.")
    if not can_transition_session_status(row.session_status, session_status):
        raise HTTPException(status_code=422, detail="Invalid session status transition.")
    now = utc_now()
    row.session_status = session_status
    row.ended_at = now
    session.add(row)
    create_mobile_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type="mobile_session_ended",
        event_payload_json={
            "session_id": int(row.id or 0),
            "device_id": row.device_id,
            "session_status": session_status,
        },
    )


def end_mobile_session(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    session_id: int,
    session_status: str = SESSION_STATUS_TERMINATED,
) -> MobileSessionResponse:
    row = session.get(MobileSession, session_id)
    if row is None or row.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Mobile session not found.")
    _terminate_mobile_session_row(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        row=row,
        session_status=session_status,
    )
    session.commit()
    session.refresh(row)
    return _session_response(row)


def create_mobile_session(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    payload: MobileSessionCreateRequest,
) -> MobileSessionResponse:
    validate_mobile_manage_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    device = _get_org_device(session, organization_id=organization_id, device_id=payload.device_id)
    validate_mobile_device_access(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        mobile_device_id=int(device.id or 0),
        action="mobile:session_create",
        require_active_session=False,
    )
    active_sessions = session.exec(
        select(MobileSession)
        .where(MobileSession.organization_id == organization_id)
        .where(MobileSession.device_id == device.id)
        .where(MobileSession.session_status == SESSION_STATUS_ACTIVE)
        .order_by(MobileSession.started_at.asc(), MobileSession.id.asc())
    ).all()
    for active in active_sessions:
        _terminate_mobile_session_row(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            row=active,
            session_status=SESSION_STATUS_TERMINATED,
        )
    now = utc_now()
    mobile_session = MobileSession(
        organization_id=organization_id,
        device_id=int(device.id or 0),
        user_id=actor_user_id,
        session_status=SESSION_STATUS_ACTIVE,
        started_at=now,
    )
    session.add(mobile_session)
    session.flush()
    device.last_seen_at = now
    session.add(device)
    create_mobile_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type="mobile_session_started",
        event_payload_json={
            "session_id": int(mobile_session.id or 0),
            "device_id": int(device.id or 0),
            "user_id": actor_user_id,
        },
    )
    session.commit()
    session.refresh(mobile_session)
    return _session_response(mobile_session)


def create_offline_sync_contract(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    payload: OfflineSyncContractCreateRequest,
) -> OfflineSyncContractResponse:
    validate_mobile_manage_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    try:
        validate_sync_contract_type(payload.contract_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    contract = OfflineSyncContract(
        organization_id=organization_id,
        contract_type=payload.contract_type,
        contract_payload_json=_json_safe(payload.contract_payload_json),
        created_at=utc_now(),
    )
    session.add(contract)
    session.flush()
    create_mobile_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type="offline_contract_created",
        event_payload_json={
            "contract_id": int(contract.id or 0),
            "contract_type": contract.contract_type,
        },
    )
    session.commit()
    session.refresh(contract)
    return _contract_response(contract)


def list_mobile_devices(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> MobileDeviceListResponse:
    resolution = validate_mobile_view_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    total_count = session.exec(
        select(func.count()).select_from(MobileDevice).where(MobileDevice.organization_id == organization_id)
    ).one()
    rows = session.exec(
        select(MobileDevice)
        .where(MobileDevice.organization_id == organization_id)
        .order_by(MobileDevice.created_at.asc(), MobileDevice.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return MobileDeviceListResponse(
        organization_id=organization_id,
        permissions=_permission_response(resolution),
        items=[_device_response(row) for row in rows],
        total_items=int(total_count),
        limit=limit,
        offset=offset,
    )


def list_mobile_sessions(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> MobileSessionListResponse:
    resolution = validate_mobile_view_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    total_count = session.exec(
        select(func.count()).select_from(MobileSession).where(MobileSession.organization_id == organization_id)
    ).one()
    rows = session.exec(
        select(MobileSession)
        .where(MobileSession.organization_id == organization_id)
        .order_by(MobileSession.started_at.asc(), MobileSession.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return MobileSessionListResponse(
        organization_id=organization_id,
        permissions=_permission_response(resolution),
        items=[_session_response(row) for row in rows],
        total_items=int(total_count),
        limit=limit,
        offset=offset,
    )


def list_offline_sync_contracts(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> OfflineSyncContractListResponse:
    resolution = validate_mobile_view_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    total_count = session.exec(
        select(func.count()).select_from(OfflineSyncContract).where(OfflineSyncContract.organization_id == organization_id)
    ).one()
    rows = session.exec(
        select(OfflineSyncContract)
        .where(OfflineSyncContract.organization_id == organization_id)
        .order_by(OfflineSyncContract.created_at.asc(), OfflineSyncContract.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return OfflineSyncContractListResponse(
        organization_id=organization_id,
        permissions=_permission_response(resolution),
        items=[_contract_response(row) for row in rows],
        total_items=int(total_count),
        limit=limit,
        offset=offset,
    )


def build_mobile_foundation_dashboard(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
) -> MobileFoundationDashboardResponse:
    resolution = validate_mobile_view_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    device_count = session.exec(
        select(func.count()).select_from(MobileDevice).where(MobileDevice.organization_id == organization_id)
    ).one()
    active_device_count = session.exec(
        select(func.count())
        .select_from(MobileDevice)
        .where(MobileDevice.organization_id == organization_id)
        .where(MobileDevice.device_status == DEVICE_STATUS_ACTIVE)
    ).one()
    session_count = session.exec(
        select(func.count()).select_from(MobileSession).where(MobileSession.organization_id == organization_id)
    ).one()
    active_session_count = session.exec(
        select(func.count())
        .select_from(MobileSession)
        .where(MobileSession.organization_id == organization_id)
        .where(MobileSession.session_status == SESSION_STATUS_ACTIVE)
    ).one()
    contract_count = session.exec(
        select(func.count()).select_from(OfflineSyncContract).where(OfflineSyncContract.organization_id == organization_id)
    ).one()
    events = session.exec(
        select(MobileFoundationEvent)
        .where(MobileFoundationEvent.organization_id == organization_id)
        .order_by(col(MobileFoundationEvent.created_at).desc(), col(MobileFoundationEvent.id).desc())
        .limit(20)
    ).all()
    return MobileFoundationDashboardResponse(
        organization_id=organization_id,
        permissions=_permission_response(resolution),
        summary={
            "devices": {"total": int(device_count), "active": int(active_device_count)},
            "sessions": {"total": int(session_count), "active": int(active_session_count)},
            "contracts": {"total": int(contract_count)},
        },
        runtime_registry={
            "device_statuses": list(list_device_statuses()),
            "session_statuses": list(list_session_statuses()),
            "sync_contract_types": list(list_sync_contract_types()),
        },
        recent_events=[_event_response(row) for row in events],
    )
