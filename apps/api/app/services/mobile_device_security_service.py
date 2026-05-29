from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, col, func, select

from app.models import MobileDevice, MobileSession, MobileDeviceAccessLog, MobileDeviceSecurityEvent, MobileDeviceSecurityPolicy, MobileDeviceTrustState
from app.schemas.mobile_device_security import (
    MobileDeviceAccessLogListResponse,
    MobileDeviceAccessLogResponse,
    MobileDeviceSecurityDashboardResponse,
    MobileDeviceSecurityDiagnosticResponse,
    MobileDeviceSecurityEventListResponse,
    MobileDeviceSecurityEventResponse,
    MobileDeviceSecurityPermissionResponse,
    MobileDeviceSecurityPolicyCreateRequest,
    MobileDeviceSecurityPolicyListResponse,
    MobileDeviceSecurityPolicyResponse,
    MobileDeviceSecurityPolicyUpdateRequest,
    MobileDeviceTrustStateCreateRequest,
    MobileDeviceTrustStateListResponse,
    MobileDeviceTrustStateResponse,
    MobileDeviceTrustStateUpdateRequest,
)
from app.services.mobile_device_security_registry import (
    ACCESS_RESULT_ALLOWED,
    ACCESS_RESULT_DENIED,
    POLICY_KEY_ALLOW_OFFLINE_ACTIONS,
    POLICY_KEY_BLOCK_SUSPENDED_DEVICE,
    POLICY_KEY_REQUIRE_ACTIVE_SESSION,
    POLICY_KEY_REQUIRE_TRUSTED_DEVICE,
    POLICY_STATUS_ACTIVE,
    POLICY_STATUS_INACTIVE,
    TRUST_STATUS_SUSPENDED,
    TRUST_STATUS_TRUSTED,
    TRUST_STATUS_UNTRUSTED,
    can_transition_policy_status,
    can_transition_trust_status,
    list_policy_keys,
    validate_access_result,
    validate_policy_key,
    validate_policy_status,
    validate_trust_status,
)
from app.services.mobile_permissions import resolve_mobile_permissions
from app.services.offline_runtime_registry import DEVICE_STATUS_ACTIVE, DEVICE_STATUS_SUSPENDED, SESSION_STATUS_ACTIVE, SESSION_STATUS_TERMINATED


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


def _permission_response(*, can_view: bool, can_manage: bool) -> MobileDeviceSecurityPermissionResponse:
    return MobileDeviceSecurityPermissionResponse(can_view=can_view, can_manage=can_manage)


def _trust_state_response(row: MobileDeviceTrustState) -> MobileDeviceTrustStateResponse:
    return MobileDeviceTrustStateResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        mobile_device_id=row.mobile_device_id,
        trust_status=row.trust_status,
        trust_reason=row.trust_reason,
        trusted_at=row.trusted_at,
        suspended_at=row.suspended_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _policy_response(row: MobileDeviceSecurityPolicy) -> MobileDeviceSecurityPolicyResponse:
    return MobileDeviceSecurityPolicyResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        policy_key=row.policy_key,
        policy_status=row.policy_status,
        policy_payload_json=dict(row.policy_payload_json or {}),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _access_log_response(row: MobileDeviceAccessLog) -> MobileDeviceAccessLogResponse:
    return MobileDeviceAccessLogResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        mobile_device_id=row.mobile_device_id,
        user_id=row.user_id,
        access_result=row.access_result,
        access_reason=row.access_reason,
        accessed_at=row.accessed_at,
    )


def _event_response(row: MobileDeviceSecurityEvent) -> MobileDeviceSecurityEventResponse:
    return MobileDeviceSecurityEventResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        mobile_device_id=row.mobile_device_id,
        actor_user_id=row.actor_user_id,
        event_type=row.event_type,
        event_payload_json=dict(row.event_payload_json or {}),
        created_at=row.created_at,
    )


def create_device_security_event(
    session: Session,
    *,
    organization_id: int,
    mobile_device_id: int | None,
    actor_user_id: int | None,
    event_type: str,
    event_payload_json: dict | None = None,
) -> MobileDeviceSecurityEvent:
    row = MobileDeviceSecurityEvent(
        organization_id=organization_id,
        mobile_device_id=mobile_device_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        event_payload_json=_json_safe(event_payload_json or {}),
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return row


def create_device_access_log(
    session: Session,
    *,
    organization_id: int,
    mobile_device_id: int,
    user_id: int,
    access_result: str,
    access_reason: str,
) -> MobileDeviceAccessLog:
    try:
        validate_access_result(access_result)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    row = MobileDeviceAccessLog(
        organization_id=organization_id,
        mobile_device_id=mobile_device_id,
        user_id=user_id,
        access_result=access_result,
        access_reason=access_reason,
        accessed_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return row


def _get_org_device(session: Session, *, organization_id: int, mobile_device_id: int) -> MobileDevice:
    row = session.get(MobileDevice, mobile_device_id)
    if row is None or row.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Mobile device not found.")
    return row


def _get_org_trust_state(session: Session, *, organization_id: int, trust_state_id: int) -> MobileDeviceTrustState:
    row = session.get(MobileDeviceTrustState, trust_state_id)
    if row is None or row.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Device trust state not found.")
    return row


def _get_org_policy(session: Session, *, organization_id: int, policy_id: int) -> MobileDeviceSecurityPolicy:
    row = session.get(MobileDeviceSecurityPolicy, policy_id)
    if row is None or row.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Device security policy not found.")
    return row


def _trust_state_for_device(session: Session, *, organization_id: int, mobile_device_id: int) -> MobileDeviceTrustState | None:
    return session.exec(
        select(MobileDeviceTrustState)
        .where(MobileDeviceTrustState.organization_id == organization_id)
        .where(MobileDeviceTrustState.mobile_device_id == mobile_device_id)
    ).first()


def _policy_by_key(session: Session, *, organization_id: int, policy_key: str) -> MobileDeviceSecurityPolicy | None:
    return session.exec(
        select(MobileDeviceSecurityPolicy)
        .where(MobileDeviceSecurityPolicy.organization_id == organization_id)
        .where(MobileDeviceSecurityPolicy.policy_key == policy_key)
    ).first()


def _validate_security_view(session: Session, *, organization_id: int, actor_user_id: int, action: str):
    resolution = resolve_mobile_permissions(session, organization_id=organization_id, actor_user_id=actor_user_id)
    if not resolution.can_view:
        create_device_security_event(
            session,
            organization_id=organization_id,
            mobile_device_id=None,
            actor_user_id=actor_user_id,
            event_type="unauthorized_mobile_security_access_attempt",
            event_payload_json={"action": action, "reason": resolution.reason},
        )
        session.commit()
        raise HTTPException(status_code=403, detail="Mobile device security visibility is denied for this organization.")
    return resolution


def _validate_security_manage(session: Session, *, organization_id: int, actor_user_id: int, action: str):
    resolution = resolve_mobile_permissions(session, organization_id=organization_id, actor_user_id=actor_user_id)
    if not resolution.can_manage:
        create_device_security_event(
            session,
            organization_id=organization_id,
            mobile_device_id=None,
            actor_user_id=actor_user_id,
            event_type="unauthorized_mobile_security_access_attempt",
            event_payload_json={"action": action, "reason": resolution.reason},
        )
        session.commit()
        raise HTTPException(status_code=403, detail="Mobile device security management is denied for this organization.")
    return resolution


def _effective_policy_statuses(session: Session, *, organization_id: int) -> dict[str, str]:
    defaults = {
        POLICY_KEY_REQUIRE_TRUSTED_DEVICE: POLICY_STATUS_INACTIVE,
        POLICY_KEY_BLOCK_SUSPENDED_DEVICE: POLICY_STATUS_ACTIVE,
        POLICY_KEY_REQUIRE_ACTIVE_SESSION: POLICY_STATUS_ACTIVE,
        POLICY_KEY_ALLOW_OFFLINE_ACTIONS: POLICY_STATUS_ACTIVE,
    }
    for policy_key in list_policy_keys():
        row = _policy_by_key(session, organization_id=organization_id, policy_key=policy_key)
        if row is not None:
            defaults[policy_key] = row.policy_status
    return defaults


def _active_session_for_device(
    session: Session,
    *,
    organization_id: int,
    mobile_device_id: int,
    user_id: int | None,
) -> MobileSession | None:
    statement = (
        select(MobileSession)
        .where(MobileSession.organization_id == organization_id)
        .where(MobileSession.device_id == mobile_device_id)
        .where(MobileSession.session_status == SESSION_STATUS_ACTIVE)
        .order_by(MobileSession.started_at.asc(), MobileSession.id.asc())
    )
    if user_id is not None:
        statement = statement.where(MobileSession.user_id == user_id)
    return session.exec(statement).first()


def _terminate_active_sessions_for_device(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    mobile_device_id: int,
) -> None:
    rows = session.exec(
        select(MobileSession)
        .where(MobileSession.organization_id == organization_id)
        .where(MobileSession.device_id == mobile_device_id)
        .where(MobileSession.session_status == SESSION_STATUS_ACTIVE)
        .order_by(MobileSession.started_at.asc(), MobileSession.id.asc())
    ).all()
    now = utc_now()
    for row in rows:
        row.session_status = SESSION_STATUS_TERMINATED
        row.ended_at = now
        session.add(row)
        create_device_security_event(
            session,
            organization_id=organization_id,
            mobile_device_id=mobile_device_id,
            actor_user_id=actor_user_id,
            event_type="device_access_denied",
            event_payload_json={"reason": "device_suspended_active_session_terminated", "session_id": int(row.id or 0)},
        )


def set_device_trust_state(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    payload: MobileDeviceTrustStateCreateRequest,
) -> tuple[MobileDeviceTrustStateResponse, bool]:
    _validate_security_manage(session, organization_id=organization_id, actor_user_id=actor_user_id, action="mobile_security:trust_state_set")
    device = _get_org_device(session, organization_id=organization_id, mobile_device_id=payload.mobile_device_id)
    try:
        validate_trust_status(payload.trust_status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    existing = _trust_state_for_device(session, organization_id=organization_id, mobile_device_id=payload.mobile_device_id)
    now = utc_now()
    created = existing is None
    row = existing or MobileDeviceTrustState(
        organization_id=organization_id,
        mobile_device_id=payload.mobile_device_id,
        trust_status=payload.trust_status,
        created_at=now,
        updated_at=now,
    )
    if existing is not None and not can_transition_trust_status(existing.trust_status, payload.trust_status):
        raise HTTPException(status_code=422, detail="Invalid device trust state transition.")
    row.trust_status = payload.trust_status
    row.trust_reason = payload.trust_reason
    row.updated_at = now
    if payload.trust_status == TRUST_STATUS_TRUSTED:
        row.trusted_at = now
        row.suspended_at = None
        device.device_status = DEVICE_STATUS_ACTIVE
    elif payload.trust_status == TRUST_STATUS_SUSPENDED:
        row.suspended_at = now
        device.device_status = DEVICE_STATUS_SUSPENDED
        _terminate_active_sessions_for_device(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            mobile_device_id=payload.mobile_device_id,
        )
    elif payload.trust_status == TRUST_STATUS_UNTRUSTED:
        row.suspended_at = None
        device.device_status = DEVICE_STATUS_ACTIVE
    session.add(row)
    session.add(device)
    session.flush()
    create_device_security_event(
        session,
        organization_id=organization_id,
        mobile_device_id=payload.mobile_device_id,
        actor_user_id=actor_user_id,
        event_type="device_trust_state_set",
        event_payload_json={"trust_state_id": int(row.id or 0), "trust_status": payload.trust_status, "trust_reason": payload.trust_reason},
    )
    session.commit()
    session.refresh(row)
    return _trust_state_response(row), created


def suspend_mobile_device(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    trust_state_id: int,
    payload: MobileDeviceTrustStateUpdateRequest,
) -> MobileDeviceTrustStateResponse:
    _validate_security_manage(session, organization_id=organization_id, actor_user_id=actor_user_id, action="mobile_security:device_suspend")
    row = _get_org_trust_state(session, organization_id=organization_id, trust_state_id=trust_state_id)
    if not can_transition_trust_status(row.trust_status, TRUST_STATUS_SUSPENDED):
        raise HTTPException(status_code=422, detail="Invalid device trust state transition.")
    device = _get_org_device(session, organization_id=organization_id, mobile_device_id=row.mobile_device_id)
    now = utc_now()
    row.trust_status = TRUST_STATUS_SUSPENDED
    row.trust_reason = payload.trust_reason
    row.suspended_at = now
    row.updated_at = now
    device.device_status = DEVICE_STATUS_SUSPENDED
    session.add(row)
    session.add(device)
    _terminate_active_sessions_for_device(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        mobile_device_id=row.mobile_device_id,
    )
    create_device_security_event(
        session,
        organization_id=organization_id,
        mobile_device_id=row.mobile_device_id,
        actor_user_id=actor_user_id,
        event_type="device_suspended",
        event_payload_json={"trust_state_id": trust_state_id, "trust_reason": payload.trust_reason},
    )
    session.commit()
    session.refresh(row)
    return _trust_state_response(row)


def unsuspend_mobile_device(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    trust_state_id: int,
    payload: MobileDeviceTrustStateUpdateRequest,
) -> MobileDeviceTrustStateResponse:
    _validate_security_manage(session, organization_id=organization_id, actor_user_id=actor_user_id, action="mobile_security:device_unsuspend")
    row = _get_org_trust_state(session, organization_id=organization_id, trust_state_id=trust_state_id)
    if row.trust_status != TRUST_STATUS_SUSPENDED:
        raise HTTPException(status_code=422, detail="Only suspended devices can be unsuspended.")
    target_status = payload.trust_status or TRUST_STATUS_TRUSTED
    if target_status == TRUST_STATUS_SUSPENDED:
        raise HTTPException(status_code=422, detail="Unsuspend target must not remain suspended.")
    if not can_transition_trust_status(row.trust_status, target_status):
        raise HTTPException(status_code=422, detail="Invalid device trust state transition.")
    device = _get_org_device(session, organization_id=organization_id, mobile_device_id=row.mobile_device_id)
    now = utc_now()
    row.trust_status = target_status
    row.trust_reason = payload.trust_reason
    row.updated_at = now
    row.suspended_at = None
    if target_status == TRUST_STATUS_TRUSTED:
        row.trusted_at = now
    device.device_status = DEVICE_STATUS_ACTIVE
    session.add(row)
    session.add(device)
    create_device_security_event(
        session,
        organization_id=organization_id,
        mobile_device_id=row.mobile_device_id,
        actor_user_id=actor_user_id,
        event_type="device_unsuspended",
        event_payload_json={"trust_state_id": trust_state_id, "trust_status": target_status, "trust_reason": payload.trust_reason},
    )
    session.commit()
    session.refresh(row)
    return _trust_state_response(row)


def create_security_policy(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    payload: MobileDeviceSecurityPolicyCreateRequest,
) -> tuple[MobileDeviceSecurityPolicyResponse, bool]:
    _validate_security_manage(session, organization_id=organization_id, actor_user_id=actor_user_id, action="mobile_security:policy_create")
    try:
        validate_policy_key(payload.policy_key)
        validate_policy_status(payload.policy_status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    existing = _policy_by_key(session, organization_id=organization_id, policy_key=payload.policy_key)
    now = utc_now()
    created = existing is None
    row = existing or MobileDeviceSecurityPolicy(
        organization_id=organization_id,
        policy_key=payload.policy_key,
        policy_status=payload.policy_status,
        created_at=now,
        updated_at=now,
    )
    if existing is not None and not can_transition_policy_status(existing.policy_status, payload.policy_status):
        raise HTTPException(status_code=422, detail="Invalid device security policy transition.")
    row.policy_status = payload.policy_status
    row.policy_payload_json = _json_safe(payload.policy_payload_json)
    row.updated_at = now
    session.add(row)
    session.flush()
    create_device_security_event(
        session,
        organization_id=organization_id,
        mobile_device_id=None,
        actor_user_id=actor_user_id,
        event_type="device_security_policy_created" if created else "device_security_policy_updated",
        event_payload_json={"policy_id": int(row.id or 0), "policy_key": row.policy_key, "policy_status": row.policy_status},
    )
    session.commit()
    session.refresh(row)
    return _policy_response(row), created


def update_security_policy(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    policy_id: int,
    payload: MobileDeviceSecurityPolicyUpdateRequest,
) -> MobileDeviceSecurityPolicyResponse:
    _validate_security_manage(session, organization_id=organization_id, actor_user_id=actor_user_id, action="mobile_security:policy_update")
    try:
        validate_policy_status(payload.policy_status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    row = _get_org_policy(session, organization_id=organization_id, policy_id=policy_id)
    if not can_transition_policy_status(row.policy_status, payload.policy_status):
        raise HTTPException(status_code=422, detail="Invalid device security policy transition.")
    row.policy_status = payload.policy_status
    row.policy_payload_json = _json_safe(payload.policy_payload_json)
    row.updated_at = utc_now()
    session.add(row)
    create_device_security_event(
        session,
        organization_id=organization_id,
        mobile_device_id=None,
        actor_user_id=actor_user_id,
        event_type="device_security_policy_updated",
        event_payload_json={"policy_id": policy_id, "policy_key": row.policy_key, "policy_status": row.policy_status},
    )
    session.commit()
    session.refresh(row)
    return _policy_response(row)


def validate_mobile_device_access(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    mobile_device_id: int,
    action: str,
    require_active_session: bool = True,
    offline_action: bool = False,
) -> None:
    _validate_security_view(session, organization_id=organization_id, actor_user_id=actor_user_id, action=action)
    device = _get_org_device(session, organization_id=organization_id, mobile_device_id=mobile_device_id)
    trust_state = _trust_state_for_device(session, organization_id=organization_id, mobile_device_id=mobile_device_id)
    policies = _effective_policy_statuses(session, organization_id=organization_id)
    active_session = _active_session_for_device(
        session,
        organization_id=organization_id,
        mobile_device_id=mobile_device_id,
        user_id=actor_user_id,
    )

    denial_reason: str | None = None
    if policies[POLICY_KEY_BLOCK_SUSPENDED_DEVICE] == POLICY_STATUS_ACTIVE and (
        device.device_status == DEVICE_STATUS_SUSPENDED or (trust_state is not None and trust_state.trust_status == TRUST_STATUS_SUSPENDED)
    ):
        denial_reason = "device_suspended"
    elif policies[POLICY_KEY_REQUIRE_TRUSTED_DEVICE] == POLICY_STATUS_ACTIVE:
        current_trust = trust_state.trust_status if trust_state is not None else TRUST_STATUS_UNTRUSTED
        if current_trust != TRUST_STATUS_TRUSTED:
            denial_reason = "device_not_trusted"
    elif require_active_session and policies[POLICY_KEY_REQUIRE_ACTIVE_SESSION] == POLICY_STATUS_ACTIVE and active_session is None:
        denial_reason = "active_session_required"
    elif offline_action and policies[POLICY_KEY_ALLOW_OFFLINE_ACTIONS] == POLICY_STATUS_INACTIVE:
        denial_reason = "offline_actions_blocked"

    if denial_reason is not None:
        create_device_access_log(
            session,
            organization_id=organization_id,
            mobile_device_id=mobile_device_id,
            user_id=actor_user_id,
            access_result=ACCESS_RESULT_DENIED,
            access_reason=denial_reason,
        )
        create_device_security_event(
            session,
            organization_id=organization_id,
            mobile_device_id=mobile_device_id,
            actor_user_id=actor_user_id,
            event_type="device_access_denied",
            event_payload_json={"action": action, "reason": denial_reason},
        )
        session.commit()
        raise HTTPException(status_code=403, detail="Mobile device access denied by device security policy.")

    create_device_access_log(
        session,
        organization_id=organization_id,
        mobile_device_id=mobile_device_id,
        user_id=actor_user_id,
        access_result=ACCESS_RESULT_ALLOWED,
        access_reason="access_allowed",
    )
    create_device_security_event(
        session,
        organization_id=organization_id,
        mobile_device_id=mobile_device_id,
        actor_user_id=actor_user_id,
        event_type="device_access_allowed",
        event_payload_json={"action": action, "active_session_id": int(active_session.id or 0) if active_session is not None else None},
    )
    session.commit()


def list_device_trust_states(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> MobileDeviceTrustStateListResponse:
    resolution = _validate_security_view(session, organization_id=organization_id, actor_user_id=actor_user_id, action="mobile_security:trust_state:view")
    total_count = session.exec(
        select(func.count()).select_from(MobileDeviceTrustState).where(MobileDeviceTrustState.organization_id == organization_id)
    ).one()
    rows = session.exec(
        select(MobileDeviceTrustState)
        .where(MobileDeviceTrustState.organization_id == organization_id)
        .order_by(MobileDeviceTrustState.created_at.asc(), MobileDeviceTrustState.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return MobileDeviceTrustStateListResponse(
        organization_id=organization_id,
        permissions=_permission_response(can_view=resolution.can_view, can_manage=resolution.can_manage),
        items=[_trust_state_response(row) for row in rows],
        total_items=int(total_count),
        limit=limit,
        offset=offset,
    )


def list_security_policies(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> MobileDeviceSecurityPolicyListResponse:
    resolution = _validate_security_view(session, organization_id=organization_id, actor_user_id=actor_user_id, action="mobile_security:policy:view")
    total_count = session.exec(
        select(func.count()).select_from(MobileDeviceSecurityPolicy).where(MobileDeviceSecurityPolicy.organization_id == organization_id)
    ).one()
    rows = session.exec(
        select(MobileDeviceSecurityPolicy)
        .where(MobileDeviceSecurityPolicy.organization_id == organization_id)
        .order_by(MobileDeviceSecurityPolicy.created_at.asc(), MobileDeviceSecurityPolicy.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return MobileDeviceSecurityPolicyListResponse(
        organization_id=organization_id,
        permissions=_permission_response(can_view=resolution.can_view, can_manage=resolution.can_manage),
        items=[_policy_response(row) for row in rows],
        total_items=int(total_count),
        limit=limit,
        offset=offset,
    )


def list_device_access_logs(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> MobileDeviceAccessLogListResponse:
    resolution = _validate_security_view(session, organization_id=organization_id, actor_user_id=actor_user_id, action="mobile_security:access_log:view")
    total_count = session.exec(
        select(func.count()).select_from(MobileDeviceAccessLog).where(MobileDeviceAccessLog.organization_id == organization_id)
    ).one()
    rows = session.exec(
        select(MobileDeviceAccessLog)
        .where(MobileDeviceAccessLog.organization_id == organization_id)
        .order_by(MobileDeviceAccessLog.accessed_at.asc(), MobileDeviceAccessLog.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return MobileDeviceAccessLogListResponse(
        organization_id=organization_id,
        permissions=_permission_response(can_view=resolution.can_view, can_manage=resolution.can_manage),
        items=[_access_log_response(row) for row in rows],
        total_items=int(total_count),
        limit=limit,
        offset=offset,
    )


def list_device_security_events(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> MobileDeviceSecurityEventListResponse:
    resolution = _validate_security_view(session, organization_id=organization_id, actor_user_id=actor_user_id, action="mobile_security:event:view")
    total_count = session.exec(
        select(func.count()).select_from(MobileDeviceSecurityEvent).where(MobileDeviceSecurityEvent.organization_id == organization_id)
    ).one()
    rows = session.exec(
        select(MobileDeviceSecurityEvent)
        .where(MobileDeviceSecurityEvent.organization_id == organization_id)
        .order_by(MobileDeviceSecurityEvent.created_at.asc(), MobileDeviceSecurityEvent.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return MobileDeviceSecurityEventListResponse(
        organization_id=organization_id,
        permissions=_permission_response(can_view=resolution.can_view, can_manage=resolution.can_manage),
        items=[_event_response(row) for row in rows],
        total_items=int(total_count),
        limit=limit,
        offset=offset,
    )


def _build_security_diagnostics(
    *,
    trust_states: list[MobileDeviceTrustState],
    access_logs: list[MobileDeviceAccessLog],
    effective_policies: dict[str, str],
) -> list[MobileDeviceSecurityDiagnosticResponse]:
    diagnostics: list[MobileDeviceSecurityDiagnosticResponse] = []
    trusted_count = sum(1 for row in trust_states if row.trust_status == TRUST_STATUS_TRUSTED)
    suspended_count = sum(1 for row in trust_states if row.trust_status == TRUST_STATUS_SUSPENDED)
    denied_count = sum(1 for row in access_logs if row.access_result == ACCESS_RESULT_DENIED)
    if trusted_count == 0:
        diagnostics.append(
            MobileDeviceSecurityDiagnosticResponse(
                diagnostic_code="no_trusted_devices",
                diagnostic_status="warning",
                diagnostic_message="No trusted devices are configured.",
                diagnostic_payload_json={"trusted_devices": 0},
            )
        )
    if suspended_count > 0:
        diagnostics.append(
            MobileDeviceSecurityDiagnosticResponse(
                diagnostic_code="suspended_devices_present",
                diagnostic_status="warning",
                diagnostic_message="Suspended devices are present.",
                diagnostic_payload_json={"suspended_devices": suspended_count},
            )
        )
    if denied_count > 0:
        diagnostics.append(
            MobileDeviceSecurityDiagnosticResponse(
                diagnostic_code="denied_device_access_attempts_present",
                diagnostic_status="error",
                diagnostic_message="Denied device access attempts are present.",
                diagnostic_payload_json={"denied_access_attempts": denied_count},
            )
        )
    if effective_policies[POLICY_KEY_REQUIRE_TRUSTED_DEVICE] == POLICY_STATUS_INACTIVE:
        diagnostics.append(
            MobileDeviceSecurityDiagnosticResponse(
                diagnostic_code="trusted_device_requirement_inactive",
                diagnostic_status="warning",
                diagnostic_message="Trusted device enforcement is inactive.",
                diagnostic_payload_json={"policy_key": POLICY_KEY_REQUIRE_TRUSTED_DEVICE},
            )
        )
    return diagnostics


def build_mobile_device_security_dashboard(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
) -> MobileDeviceSecurityDashboardResponse:
    resolution = _validate_security_view(session, organization_id=organization_id, actor_user_id=actor_user_id, action="mobile_security:view")
    trust_rows = session.exec(
        select(MobileDeviceTrustState)
        .where(MobileDeviceTrustState.organization_id == organization_id)
        .order_by(MobileDeviceTrustState.created_at.asc(), MobileDeviceTrustState.id.asc())
    ).all()
    policy_rows = session.exec(
        select(MobileDeviceSecurityPolicy)
        .where(MobileDeviceSecurityPolicy.organization_id == organization_id)
        .order_by(MobileDeviceSecurityPolicy.created_at.asc(), MobileDeviceSecurityPolicy.id.asc())
    ).all()
    access_rows = session.exec(
        select(MobileDeviceAccessLog)
        .where(MobileDeviceAccessLog.organization_id == organization_id)
        .order_by(col(MobileDeviceAccessLog.accessed_at).desc(), col(MobileDeviceAccessLog.id).desc())
        .limit(25)
    ).all()
    event_rows = session.exec(
        select(MobileDeviceSecurityEvent)
        .where(MobileDeviceSecurityEvent.organization_id == organization_id)
        .order_by(col(MobileDeviceSecurityEvent.created_at).desc(), col(MobileDeviceSecurityEvent.id).desc())
        .limit(25)
    ).all()
    effective_policies = _effective_policy_statuses(session, organization_id=organization_id)
    diagnostics = _build_security_diagnostics(
        trust_states=trust_rows,
        access_logs=access_rows,
        effective_policies=effective_policies,
    )
    summary = {
        "trust_states": {
            "trusted": sum(1 for row in trust_rows if row.trust_status == TRUST_STATUS_TRUSTED),
            "untrusted": sum(1 for row in trust_rows if row.trust_status == TRUST_STATUS_UNTRUSTED),
            "suspended": sum(1 for row in trust_rows if row.trust_status == TRUST_STATUS_SUSPENDED),
        },
        "policies": {
            "active": sum(1 for key in effective_policies if effective_policies[key] == POLICY_STATUS_ACTIVE),
            "inactive": sum(1 for key in effective_policies if effective_policies[key] == POLICY_STATUS_INACTIVE),
        },
        "access_logs": {
            "allowed": sum(1 for row in access_rows if row.access_result == ACCESS_RESULT_ALLOWED),
            "denied": sum(1 for row in access_rows if row.access_result == ACCESS_RESULT_DENIED),
        },
        "diagnostics": {
            "warning": sum(1 for row in diagnostics if row.diagnostic_status == "warning"),
            "error": sum(1 for row in diagnostics if row.diagnostic_status == "error"),
        },
    }
    return MobileDeviceSecurityDashboardResponse(
        organization_id=organization_id,
        permissions=_permission_response(can_view=resolution.can_view, can_manage=resolution.can_manage),
        summary=summary,
        diagnostics=diagnostics,
        trust_states=[_trust_state_response(row) for row in trust_rows],
        policies=[_policy_response(row) for row in policy_rows],
        access_logs=[_access_log_response(row) for row in access_rows],
        events=[_event_response(row) for row in event_rows],
    )
