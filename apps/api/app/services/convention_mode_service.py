from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, col, func, select

from app.models.convention_mode import (
    ConventionActivity,
    ConventionBooth,
    ConventionModeEvent,
    ConventionInventoryStage,
    ConventionSession,
)
from app.schemas.convention_mode import (
    ConventionActivityListResponse,
    ConventionActivityResponse,
    ConventionBoothCreateRequest,
    ConventionBoothListResponse,
    ConventionBoothResponse,
    ConventionBoothUpdateRequest,
    ConventionEventResponse,
    ConventionInventoryStageListResponse,
    ConventionInventoryStageRequest,
    ConventionInventoryStageResponse,
    ConventionModeDashboardResponse,
    ConventionPermissionResponse,
    ConventionSessionCreateRequest,
    ConventionSessionListResponse,
    ConventionSessionResponse,
    ConventionSessionUpdateRequest,
)
from app.services.convention_mode_permissions import (
    validate_convention_manage_access,
    validate_convention_view_access,
)
from app.services.convention_registry import (
    ACTIVITY_BOOTH_CLOSED,
    ACTIVITY_BOOTH_OPENED,
    ACTIVITY_INVENTORY_REMOVED,
    ACTIVITY_INVENTORY_STAGED,
    ACTIVITY_SESSION_CREATED,
    BOOTH_STATUS_ACTIVE,
    BOOTH_STATUS_CLOSED,
    BOOTH_STATUS_SETUP,
    SESSION_STATUS_ACTIVE,
    SESSION_STATUS_ARCHIVED,
    SESSION_STATUS_COMPLETED,
    SESSION_STATUS_PLANNED,
    STAGE_STATUS_REMOVED,
    STAGE_STATUS_STAGED,
    can_transition_booth_status,
    can_transition_session_status,
    can_transition_stage_status,
    list_activity_types,
    list_booth_statuses,
    list_session_statuses,
    list_stage_statuses,
    validate_activity_type,
    validate_booth_status,
    validate_session_status,
    validate_stage_status,
)
from app.services.marketplace_permissions import MarketplacePermissionResolution


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


def _permission_response(resolution: MarketplacePermissionResolution) -> ConventionPermissionResponse:
    return ConventionPermissionResponse(can_view=resolution.can_view, can_manage=resolution.can_manage)


def create_convention_event(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int | None,
    event_type: str,
    event_payload_json: dict | None = None,
) -> ConventionModeEvent:
    row = ConventionModeEvent(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        event_payload_json=_json_safe(event_payload_json or {}),
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return row


def record_activity(
    session: Session,
    *,
    organization_id: int,
    convention_session_id: int,
    activity_type: str,
    activity_payload_json: dict | None = None,
) -> ConventionActivity:
    try:
        validate_activity_type(activity_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    row = ConventionActivity(
        organization_id=organization_id,
        convention_session_id=convention_session_id,
        activity_type=activity_type,
        activity_payload_json=_json_safe(activity_payload_json or {}),
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return row


def _session_response(row: ConventionSession) -> ConventionSessionResponse:
    return ConventionSessionResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        session_name=row.session_name,
        session_status=row.session_status,
        started_at=row.started_at,
        ended_at=row.ended_at,
        created_at=row.created_at,
    )


def _booth_response(row: ConventionBooth) -> ConventionBoothResponse:
    return ConventionBoothResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        convention_session_id=row.convention_session_id,
        booth_name=row.booth_name,
        booth_status=row.booth_status,
        created_at=row.created_at,
    )


def _stage_response(row: ConventionInventoryStage) -> ConventionInventoryStageResponse:
    return ConventionInventoryStageResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        convention_session_id=row.convention_session_id,
        inventory_item_id=row.inventory_item_id,
        stage_status=row.stage_status,
        staged_at=row.staged_at,
    )


def _activity_response(row: ConventionActivity) -> ConventionActivityResponse:
    return ConventionActivityResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        convention_session_id=row.convention_session_id,
        activity_type=row.activity_type,
        activity_payload_json=row.activity_payload_json,
        created_at=row.created_at,
    )


def _event_response(row: ConventionModeEvent) -> ConventionEventResponse:
    return ConventionEventResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        actor_user_id=row.actor_user_id,
        event_type=row.event_type,
        event_payload_json=row.event_payload_json,
        created_at=row.created_at,
    )


def _get_org_session(session: Session, *, organization_id: int, session_id: int) -> ConventionSession:
    row = session.get(ConventionSession, session_id)
    if row is None or row.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Convention session not found.")
    return row


def _get_org_booth(session: Session, *, organization_id: int, booth_id: int) -> ConventionBooth:
    row = session.get(ConventionBooth, booth_id)
    if row is None or row.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Convention booth not found.")
    return row


def create_convention_session(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    payload: ConventionSessionCreateRequest,
) -> ConventionSessionResponse:
    validate_convention_manage_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    now = utc_now()
    row = ConventionSession(
        organization_id=organization_id,
        session_name=payload.session_name,
        session_status=SESSION_STATUS_PLANNED,
        created_at=now,
    )
    session.add(row)
    session.flush()
    session_id = int(row.id or 0)
    create_convention_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type="convention_session_created",
        event_payload_json={"session_id": session_id, "session_name": payload.session_name},
    )
    record_activity(
        session,
        organization_id=organization_id,
        convention_session_id=session_id,
        activity_type=ACTIVITY_SESSION_CREATED,
        activity_payload_json={"session_name": payload.session_name},
    )
    session.commit()
    session.refresh(row)
    return _session_response(row)


def start_convention_session(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    session_id: int,
) -> ConventionSessionResponse:
    return _update_session_status(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        target_status=SESSION_STATUS_ACTIVE,
        event_type="convention_session_started",
        set_started=True,
    )


def end_convention_session(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    session_id: int,
) -> ConventionSessionResponse:
    return _update_session_status(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        session_id=session_id,
        target_status=SESSION_STATUS_COMPLETED,
        event_type="convention_session_completed",
        set_ended=True,
    )


def _update_session_status(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    session_id: int,
    target_status: str,
    event_type: str,
    set_started: bool = False,
    set_ended: bool = False,
) -> ConventionSessionResponse:
    validate_convention_manage_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    row = _get_org_session(session, organization_id=organization_id, session_id=session_id)
    try:
        validate_session_status(target_status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not can_transition_session_status(row.session_status, target_status):
        raise HTTPException(status_code=422, detail="Invalid session status transition.")
    if row.session_status == target_status:
        return _session_response(row)
    previous = row.session_status
    row.session_status = target_status
    now = utc_now()
    if set_started:
        row.started_at = now
    if set_ended:
        row.ended_at = now
    session.add(row)
    create_convention_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        event_payload_json={"session_id": session_id, "previous_status": previous, "session_status": target_status},
    )
    session.commit()
    session.refresh(row)
    return _session_response(row)


def update_convention_session(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    session_id: int,
    payload: ConventionSessionUpdateRequest,
) -> ConventionSessionResponse:
    if payload.session_status == SESSION_STATUS_ACTIVE:
        return start_convention_session(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            session_id=session_id,
        )
    if payload.session_status == SESSION_STATUS_COMPLETED:
        return end_convention_session(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            session_id=session_id,
        )
    if payload.session_status == SESSION_STATUS_ARCHIVED:
        return _update_session_status(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            session_id=session_id,
            target_status=SESSION_STATUS_ARCHIVED,
            event_type="convention_session_completed",
            set_ended=True,
        )
    raise HTTPException(status_code=422, detail="Unsupported session status update.")


def create_booth(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    payload: ConventionBoothCreateRequest,
) -> ConventionBoothResponse:
    validate_convention_manage_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    _get_org_session(session, organization_id=organization_id, session_id=payload.convention_session_id)
    row = ConventionBooth(
        organization_id=organization_id,
        convention_session_id=payload.convention_session_id,
        booth_name=payload.booth_name,
        booth_status=BOOTH_STATUS_SETUP,
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    booth_id = int(row.id or 0)
    create_convention_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type="booth_created",
        event_payload_json={"booth_id": booth_id, "booth_name": payload.booth_name},
    )
    session.commit()
    session.refresh(row)
    return _booth_response(row)


def update_booth(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    booth_id: int,
    payload: ConventionBoothUpdateRequest,
) -> ConventionBoothResponse:
    validate_convention_manage_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    row = _get_org_booth(session, organization_id=organization_id, booth_id=booth_id)
    try:
        validate_booth_status(payload.booth_status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not can_transition_booth_status(row.booth_status, payload.booth_status):
        raise HTTPException(status_code=422, detail="Invalid booth status transition.")
    if row.booth_status == payload.booth_status:
        return _booth_response(row)
    previous = row.booth_status
    row.booth_status = payload.booth_status
    session.add(row)
    event_type = "booth_opened" if payload.booth_status == BOOTH_STATUS_ACTIVE else None
    activity_type = ACTIVITY_BOOTH_OPENED if payload.booth_status == BOOTH_STATUS_ACTIVE else None
    if payload.booth_status == BOOTH_STATUS_CLOSED:
        event_type = "booth_closed"
        activity_type = ACTIVITY_BOOTH_CLOSED
    if event_type:
        create_convention_event(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            event_payload_json={
                "booth_id": booth_id,
                "previous_status": previous,
                "booth_status": payload.booth_status,
            },
        )
    if activity_type:
        record_activity(
            session,
            organization_id=organization_id,
            convention_session_id=row.convention_session_id,
            activity_type=activity_type,
            activity_payload_json={"booth_id": booth_id, "booth_name": row.booth_name},
        )
    session.commit()
    session.refresh(row)
    return _booth_response(row)


def stage_inventory(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    payload: ConventionInventoryStageRequest,
) -> ConventionInventoryStageResponse:
    validate_convention_manage_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    _get_org_session(session, organization_id=organization_id, session_id=payload.convention_session_id)
    existing = session.exec(
        select(ConventionInventoryStage)
        .where(ConventionInventoryStage.organization_id == organization_id)
        .where(ConventionInventoryStage.convention_session_id == payload.convention_session_id)
        .where(ConventionInventoryStage.inventory_item_id == payload.inventory_item_id)
        .where(ConventionInventoryStage.stage_status != STAGE_STATUS_REMOVED)
        .order_by(ConventionInventoryStage.staged_at.asc(), ConventionInventoryStage.id.asc())
    ).first()
    if existing is not None:
        return _stage_response(existing)
    now = utc_now()
    row = ConventionInventoryStage(
        organization_id=organization_id,
        convention_session_id=payload.convention_session_id,
        inventory_item_id=payload.inventory_item_id,
        stage_status=STAGE_STATUS_STAGED,
        staged_at=now,
    )
    session.add(row)
    session.flush()
    stage_id = int(row.id or 0)
    create_convention_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type="inventory_staged",
        event_payload_json={
            "stage_id": stage_id,
            "inventory_item_id": payload.inventory_item_id,
            "convention_session_id": payload.convention_session_id,
        },
    )
    record_activity(
        session,
        organization_id=organization_id,
        convention_session_id=payload.convention_session_id,
        activity_type=ACTIVITY_INVENTORY_STAGED,
        activity_payload_json={"stage_id": stage_id, "inventory_item_id": payload.inventory_item_id},
    )
    session.commit()
    session.refresh(row)
    return _stage_response(row)


def remove_inventory(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    stage_id: int,
) -> ConventionInventoryStageResponse:
    validate_convention_manage_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    row = session.get(ConventionInventoryStage, stage_id)
    if row is None or row.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Staged inventory not found.")
    if not can_transition_stage_status(row.stage_status, STAGE_STATUS_REMOVED):
        raise HTTPException(status_code=422, detail="Invalid stage status transition.")
    if row.stage_status == STAGE_STATUS_REMOVED:
        return _stage_response(row)
    previous = row.stage_status
    row.stage_status = STAGE_STATUS_REMOVED
    session.add(row)
    create_convention_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type="inventory_removed",
        event_payload_json={
            "stage_id": stage_id,
            "previous_status": previous,
            "inventory_item_id": row.inventory_item_id,
        },
    )
    record_activity(
        session,
        organization_id=organization_id,
        convention_session_id=row.convention_session_id,
        activity_type=ACTIVITY_INVENTORY_REMOVED,
        activity_payload_json={"stage_id": stage_id, "inventory_item_id": row.inventory_item_id},
    )
    session.commit()
    session.refresh(row)
    return _stage_response(row)


def list_sessions(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> ConventionSessionListResponse:
    resolution = validate_convention_view_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    total_count = session.exec(
        select(func.count()).select_from(ConventionSession).where(ConventionSession.organization_id == organization_id)
    ).one()
    rows = session.exec(
        select(ConventionSession)
        .where(ConventionSession.organization_id == organization_id)
        .order_by(ConventionSession.created_at.asc(), ConventionSession.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return ConventionSessionListResponse(
        organization_id=organization_id,
        permissions=_permission_response(resolution),
        items=[_session_response(row) for row in rows],
        total_items=int(total_count),
        limit=limit,
        offset=offset,
    )


def list_booths(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> ConventionBoothListResponse:
    resolution = validate_convention_view_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    total_count = session.exec(
        select(func.count()).select_from(ConventionBooth).where(ConventionBooth.organization_id == organization_id)
    ).one()
    rows = session.exec(
        select(ConventionBooth)
        .where(ConventionBooth.organization_id == organization_id)
        .order_by(ConventionBooth.created_at.asc(), ConventionBooth.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return ConventionBoothListResponse(
        organization_id=organization_id,
        permissions=_permission_response(resolution),
        items=[_booth_response(row) for row in rows],
        total_items=int(total_count),
        limit=limit,
        offset=offset,
    )


def list_staged_inventory(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> ConventionInventoryStageListResponse:
    resolution = validate_convention_view_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    total_count = session.exec(
        select(func.count()).select_from(ConventionInventoryStage).where(ConventionInventoryStage.organization_id == organization_id)
    ).one()
    rows = session.exec(
        select(ConventionInventoryStage)
        .where(ConventionInventoryStage.organization_id == organization_id)
        .order_by(ConventionInventoryStage.staged_at.asc(), ConventionInventoryStage.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return ConventionInventoryStageListResponse(
        organization_id=organization_id,
        permissions=_permission_response(resolution),
        items=[_stage_response(row) for row in rows],
        total_items=int(total_count),
        limit=limit,
        offset=offset,
    )


def list_activities(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> ConventionActivityListResponse:
    resolution = validate_convention_view_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    total_count = session.exec(
        select(func.count()).select_from(ConventionActivity).where(ConventionActivity.organization_id == organization_id)
    ).one()
    rows = session.exec(
        select(ConventionActivity)
        .where(ConventionActivity.organization_id == organization_id)
        .order_by(ConventionActivity.created_at.asc(), ConventionActivity.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return ConventionActivityListResponse(
        organization_id=organization_id,
        permissions=_permission_response(resolution),
        items=[_activity_response(row) for row in rows],
        total_items=int(total_count),
        limit=limit,
        offset=offset,
    )


def build_convention_mode_dashboard(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
) -> ConventionModeDashboardResponse:
    resolution = validate_convention_view_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    session_count = session.exec(
        select(func.count()).select_from(ConventionSession).where(ConventionSession.organization_id == organization_id)
    ).one()
    active_sessions = session.exec(
        select(func.count())
        .select_from(ConventionSession)
        .where(ConventionSession.organization_id == organization_id)
        .where(ConventionSession.session_status == SESSION_STATUS_ACTIVE)
    ).one()
    booth_count = session.exec(
        select(func.count()).select_from(ConventionBooth).where(ConventionBooth.organization_id == organization_id)
    ).one()
    staged_count = session.exec(
        select(func.count())
        .select_from(ConventionInventoryStage)
        .where(ConventionInventoryStage.organization_id == organization_id)
        .where(ConventionInventoryStage.stage_status != STAGE_STATUS_REMOVED)
    ).one()
    activity_count = session.exec(
        select(func.count()).select_from(ConventionActivity).where(ConventionActivity.organization_id == organization_id)
    ).one()
    events = session.exec(
        select(ConventionModeEvent)
        .where(ConventionModeEvent.organization_id == organization_id)
        .order_by(col(ConventionModeEvent.created_at).desc(), col(ConventionModeEvent.id).desc())
        .limit(20)
    ).all()
    return ConventionModeDashboardResponse(
        organization_id=organization_id,
        permissions=_permission_response(resolution),
        summary={
            "sessions": {"total": int(session_count), "active": int(active_sessions)},
            "booths": {"total": int(booth_count)},
            "inventory_staged": {"total": int(staged_count)},
            "activities": {"total": int(activity_count)},
        },
        runtime_registry={
            "session_statuses": list(list_session_statuses()),
            "booth_statuses": list(list_booth_statuses()),
            "stage_statuses": list(list_stage_statuses()),
            "activity_types": list(list_activity_types()),
        },
        recent_events=[_event_response(row) for row in events],
    )
