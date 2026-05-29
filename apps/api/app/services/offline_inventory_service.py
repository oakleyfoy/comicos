from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, col, func, select

from app.models.mobile_foundation import MobileDevice
from app.models.offline_inventory import (
    OfflineInventoryChange,
    OfflineInventoryEvent,
    OfflineInventoryRecord,
    OfflineSyncConflict,
    OfflineSyncQueue,
)
from app.schemas.offline_inventory import (
    OfflineInventoryChangeListResponse,
    OfflineInventoryChangeRegisterRequest,
    OfflineInventoryChangeResponse,
    OfflineInventoryDashboardResponse,
    OfflineInventoryEventResponse,
    OfflineInventoryPermissionResponse,
    OfflineInventoryRecordCreateRequest,
    OfflineInventoryRecordListResponse,
    OfflineInventoryRecordResponse,
    OfflineInventoryRecordUpdateRequest,
    OfflineSyncConflictListResponse,
    OfflineSyncConflictRegisterRequest,
    OfflineSyncConflictResponse,
    OfflineSyncConflictUpdateRequest,
    OfflineSyncQueueCreateRequest,
    OfflineSyncQueueListResponse,
    OfflineSyncQueueResponse,
)
from app.services.marketplace_permissions import MarketplacePermissionResolution
from app.services.mobile_device_security_service import validate_mobile_device_access
from app.services.offline_inventory_permissions import (
    validate_offline_inventory_manage_access,
    validate_offline_inventory_view_access,
)
from app.services.offline_sync_registry import (
    CONFLICT_STATUS_OPEN,
    QUEUE_STATUS_PENDING,
    can_transition_conflict_status,
    list_change_types,
    list_conflict_statuses,
    list_queue_statuses,
    validate_change_type,
    validate_conflict_status,
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


def _permission_response(resolution: MarketplacePermissionResolution) -> OfflineInventoryPermissionResponse:
    return OfflineInventoryPermissionResponse(can_view=resolution.can_view, can_manage=resolution.can_manage)


def create_offline_inventory_event(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int | None,
    event_type: str,
    event_payload_json: dict | None = None,
) -> OfflineInventoryEvent:
    row = OfflineInventoryEvent(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        event_payload_json=_json_safe(event_payload_json or {}),
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return row


def _record_response(row: OfflineInventoryRecord) -> OfflineInventoryRecordResponse:
    return OfflineInventoryRecordResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        inventory_item_id=row.inventory_item_id,
        local_record_identifier=row.local_record_identifier,
        record_payload_json=row.record_payload_json,
        local_updated_at=row.local_updated_at,
        created_at=row.created_at,
    )


def _change_response(row: OfflineInventoryChange) -> OfflineInventoryChangeResponse:
    return OfflineInventoryChangeResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        device_id=row.device_id,
        inventory_item_id=row.inventory_item_id,
        change_type=row.change_type,
        change_payload_json=row.change_payload_json,
        created_at=row.created_at,
    )


def _queue_response(row: OfflineSyncQueue) -> OfflineSyncQueueResponse:
    return OfflineSyncQueueResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        device_id=row.device_id,
        queue_status=row.queue_status,
        queue_payload_json=row.queue_payload_json,
        queued_at=row.queued_at,
        processed_at=row.processed_at,
    )


def _conflict_response(row: OfflineSyncConflict) -> OfflineSyncConflictResponse:
    return OfflineSyncConflictResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        inventory_item_id=row.inventory_item_id,
        conflict_type=row.conflict_type,
        local_payload_json=row.local_payload_json,
        server_payload_json=row.server_payload_json,
        conflict_status=row.conflict_status,
        created_at=row.created_at,
    )


def _event_response(row: OfflineInventoryEvent) -> OfflineInventoryEventResponse:
    return OfflineInventoryEventResponse(
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


def _get_org_record(session: Session, *, organization_id: int, record_id: int) -> OfflineInventoryRecord:
    row = session.get(OfflineInventoryRecord, record_id)
    if row is None or row.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Offline inventory record not found.")
    return row


def create_offline_inventory_record(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    payload: OfflineInventoryRecordCreateRequest,
) -> tuple[OfflineInventoryRecordResponse, bool]:
    validate_offline_inventory_manage_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    existing = session.exec(
        select(OfflineInventoryRecord)
        .where(OfflineInventoryRecord.organization_id == organization_id)
        .where(OfflineInventoryRecord.local_record_identifier == payload.local_record_identifier)
    ).first()
    if existing is not None:
        update_payload = OfflineInventoryRecordUpdateRequest(
            inventory_item_id=payload.inventory_item_id,
            record_payload_json=payload.record_payload_json,
            local_updated_at=payload.local_updated_at,
        )
        updated = update_offline_inventory_record(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            record_id=int(existing.id or 0),
            payload=update_payload,
        )
        return updated, False

    now = utc_now()
    local_updated = payload.local_updated_at or now
    row = OfflineInventoryRecord(
        organization_id=organization_id,
        inventory_item_id=payload.inventory_item_id,
        local_record_identifier=payload.local_record_identifier,
        record_payload_json=_json_safe(payload.record_payload_json),
        local_updated_at=local_updated,
        created_at=now,
    )
    session.add(row)
    session.flush()
    create_offline_inventory_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type="offline_inventory_created",
        event_payload_json={
            "record_id": int(row.id or 0),
            "local_record_identifier": row.local_record_identifier,
        },
    )
    session.commit()
    session.refresh(row)
    return _record_response(row), True


def update_offline_inventory_record(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    record_id: int,
    payload: OfflineInventoryRecordUpdateRequest,
) -> OfflineInventoryRecordResponse:
    validate_offline_inventory_manage_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    row = _get_org_record(session, organization_id=organization_id, record_id=record_id)
    changes: dict[str, Any] = {}
    if payload.inventory_item_id is not None and payload.inventory_item_id != row.inventory_item_id:
        changes["inventory_item_id"] = {"before": row.inventory_item_id, "after": payload.inventory_item_id}
        row.inventory_item_id = payload.inventory_item_id
    if payload.record_payload_json is not None and payload.record_payload_json != row.record_payload_json:
        changes["record_payload_json"] = {"before": row.record_payload_json, "after": payload.record_payload_json}
        row.record_payload_json = _json_safe(payload.record_payload_json)
    now = payload.local_updated_at or utc_now()
    if now != row.local_updated_at:
        changes["local_updated_at"] = True
    row.local_updated_at = now
    session.add(row)
    create_offline_inventory_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type="offline_inventory_updated",
        event_payload_json={"record_id": record_id, "changes": changes or {"local_updated_at": True}},
    )
    session.commit()
    session.refresh(row)
    return _record_response(row)


def register_inventory_change(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    payload: OfflineInventoryChangeRegisterRequest,
) -> OfflineInventoryChangeResponse:
    validate_offline_inventory_manage_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    _get_org_device(session, organization_id=organization_id, device_id=payload.device_id)
    validate_mobile_device_access(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        mobile_device_id=payload.device_id,
        action="offline_inventory:change_register",
        require_active_session=True,
        offline_action=True,
    )
    try:
        validate_change_type(payload.change_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    row = OfflineInventoryChange(
        organization_id=organization_id,
        device_id=payload.device_id,
        inventory_item_id=payload.inventory_item_id,
        change_type=payload.change_type,
        change_payload_json=_json_safe(payload.change_payload_json),
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    create_offline_inventory_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type="offline_change_registered",
        event_payload_json={
            "change_id": int(row.id or 0),
            "device_id": payload.device_id,
            "change_type": payload.change_type,
        },
    )
    session.commit()
    session.refresh(row)
    return _change_response(row)


def queue_sync_operation(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    payload: OfflineSyncQueueCreateRequest,
) -> OfflineSyncQueueResponse:
    validate_offline_inventory_manage_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    _get_org_device(session, organization_id=organization_id, device_id=payload.device_id)
    validate_mobile_device_access(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        mobile_device_id=payload.device_id,
        action="offline_inventory:queue_sync",
        require_active_session=True,
        offline_action=True,
    )
    now = utc_now()
    row = OfflineSyncQueue(
        organization_id=organization_id,
        device_id=payload.device_id,
        queue_status=QUEUE_STATUS_PENDING,
        queue_payload_json=_json_safe(payload.queue_payload_json),
        queued_at=now,
    )
    session.add(row)
    session.flush()
    create_offline_inventory_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type="sync_queue_item_created",
        event_payload_json={"queue_id": int(row.id or 0), "device_id": payload.device_id},
    )
    session.commit()
    session.refresh(row)
    return _queue_response(row)


def register_sync_conflict(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    payload: OfflineSyncConflictRegisterRequest,
) -> OfflineSyncConflictResponse:
    validate_offline_inventory_manage_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    row = OfflineSyncConflict(
        organization_id=organization_id,
        inventory_item_id=payload.inventory_item_id,
        conflict_type=payload.conflict_type,
        local_payload_json=_json_safe(payload.local_payload_json),
        server_payload_json=_json_safe(payload.server_payload_json),
        conflict_status=CONFLICT_STATUS_OPEN,
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    create_offline_inventory_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type="sync_conflict_detected",
        event_payload_json={
            "conflict_id": int(row.id or 0),
            "conflict_type": payload.conflict_type,
        },
    )
    session.commit()
    session.refresh(row)
    return _conflict_response(row)


def acknowledge_sync_conflict(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    conflict_id: int,
    payload: OfflineSyncConflictUpdateRequest,
) -> OfflineSyncConflictResponse:
    validate_offline_inventory_manage_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    row = session.get(OfflineSyncConflict, conflict_id)
    if row is None or row.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Sync conflict not found.")
    try:
        validate_conflict_status(payload.conflict_status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not can_transition_conflict_status(row.conflict_status, payload.conflict_status):
        raise HTTPException(status_code=422, detail="Invalid conflict status transition.")
    if row.conflict_status == payload.conflict_status:
        return _conflict_response(row)
    previous = row.conflict_status
    row.conflict_status = payload.conflict_status
    session.add(row)
    create_offline_inventory_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type="sync_conflict_acknowledged",
        event_payload_json={
            "conflict_id": conflict_id,
            "previous_status": previous,
            "conflict_status": payload.conflict_status,
        },
    )
    session.commit()
    session.refresh(row)
    return _conflict_response(row)


def list_offline_inventory_records(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> OfflineInventoryRecordListResponse:
    resolution = validate_offline_inventory_view_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    total_count = session.exec(
        select(func.count()).select_from(OfflineInventoryRecord).where(OfflineInventoryRecord.organization_id == organization_id)
    ).one()
    rows = session.exec(
        select(OfflineInventoryRecord)
        .where(OfflineInventoryRecord.organization_id == organization_id)
        .order_by(OfflineInventoryRecord.created_at.asc(), OfflineInventoryRecord.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return OfflineInventoryRecordListResponse(
        organization_id=organization_id,
        permissions=_permission_response(resolution),
        items=[_record_response(row) for row in rows],
        total_items=int(total_count),
        limit=limit,
        offset=offset,
    )


def list_inventory_changes(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> OfflineInventoryChangeListResponse:
    resolution = validate_offline_inventory_view_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    total_count = session.exec(
        select(func.count()).select_from(OfflineInventoryChange).where(OfflineInventoryChange.organization_id == organization_id)
    ).one()
    rows = session.exec(
        select(OfflineInventoryChange)
        .where(OfflineInventoryChange.organization_id == organization_id)
        .order_by(OfflineInventoryChange.created_at.asc(), OfflineInventoryChange.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return OfflineInventoryChangeListResponse(
        organization_id=organization_id,
        permissions=_permission_response(resolution),
        items=[_change_response(row) for row in rows],
        total_items=int(total_count),
        limit=limit,
        offset=offset,
    )


def list_sync_queue(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> OfflineSyncQueueListResponse:
    resolution = validate_offline_inventory_view_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    total_count = session.exec(
        select(func.count()).select_from(OfflineSyncQueue).where(OfflineSyncQueue.organization_id == organization_id)
    ).one()
    rows = session.exec(
        select(OfflineSyncQueue)
        .where(OfflineSyncQueue.organization_id == organization_id)
        .order_by(OfflineSyncQueue.queued_at.asc(), OfflineSyncQueue.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return OfflineSyncQueueListResponse(
        organization_id=organization_id,
        permissions=_permission_response(resolution),
        items=[_queue_response(row) for row in rows],
        total_items=int(total_count),
        limit=limit,
        offset=offset,
    )


def list_sync_conflicts(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> OfflineSyncConflictListResponse:
    resolution = validate_offline_inventory_view_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    total_count = session.exec(
        select(func.count()).select_from(OfflineSyncConflict).where(OfflineSyncConflict.organization_id == organization_id)
    ).one()
    rows = session.exec(
        select(OfflineSyncConflict)
        .where(OfflineSyncConflict.organization_id == organization_id)
        .order_by(OfflineSyncConflict.created_at.asc(), OfflineSyncConflict.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return OfflineSyncConflictListResponse(
        organization_id=organization_id,
        permissions=_permission_response(resolution),
        items=[_conflict_response(row) for row in rows],
        total_items=int(total_count),
        limit=limit,
        offset=offset,
    )


def build_offline_inventory_dashboard(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
) -> OfflineInventoryDashboardResponse:
    resolution = validate_offline_inventory_view_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    record_count = session.exec(
        select(func.count()).select_from(OfflineInventoryRecord).where(OfflineInventoryRecord.organization_id == organization_id)
    ).one()
    change_count = session.exec(
        select(func.count()).select_from(OfflineInventoryChange).where(OfflineInventoryChange.organization_id == organization_id)
    ).one()
    queue_count = session.exec(
        select(func.count()).select_from(OfflineSyncQueue).where(OfflineSyncQueue.organization_id == organization_id)
    ).one()
    pending_queue = session.exec(
        select(func.count())
        .select_from(OfflineSyncQueue)
        .where(OfflineSyncQueue.organization_id == organization_id)
        .where(OfflineSyncQueue.queue_status == QUEUE_STATUS_PENDING)
    ).one()
    conflict_count = session.exec(
        select(func.count()).select_from(OfflineSyncConflict).where(OfflineSyncConflict.organization_id == organization_id)
    ).one()
    open_conflicts = session.exec(
        select(func.count())
        .select_from(OfflineSyncConflict)
        .where(OfflineSyncConflict.organization_id == organization_id)
        .where(OfflineSyncConflict.conflict_status == CONFLICT_STATUS_OPEN)
    ).one()
    events = session.exec(
        select(OfflineInventoryEvent)
        .where(OfflineInventoryEvent.organization_id == organization_id)
        .order_by(col(OfflineInventoryEvent.created_at).desc(), col(OfflineInventoryEvent.id).desc())
        .limit(20)
    ).all()
    records = session.exec(
        select(OfflineInventoryRecord)
        .where(OfflineInventoryRecord.organization_id == organization_id)
        .order_by(OfflineInventoryRecord.created_at.asc(), OfflineInventoryRecord.id.asc())
        .limit(100)
    ).all()
    return OfflineInventoryDashboardResponse(
        organization_id=organization_id,
        permissions=_permission_response(resolution),
        summary={
            "records": {"total": int(record_count)},
            "changes": {"total": int(change_count)},
            "queue": {"total": int(queue_count), "pending": int(pending_queue)},
            "conflicts": {"total": int(conflict_count), "open": int(open_conflicts)},
        },
        runtime_registry={
            "queue_statuses": list(list_queue_statuses()),
            "conflict_statuses": list(list_conflict_statuses()),
            "change_types": list(list_change_types()),
        },
        recent_records=[_record_response(row) for row in records],
        recent_events=[_event_response(row) for row in events],
    )
