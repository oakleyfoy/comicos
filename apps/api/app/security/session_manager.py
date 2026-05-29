from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.models import OrganizationSecurityContext, OrganizationMember, UserAuthSession, UserAuthSessionEvent

ACTIVE_SESSION_STATUS = "ACTIVE"
REVOKED_SESSION_STATUS = "REVOKED"
EXPIRED_SESSION_STATUS = "EXPIRED"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def hash_session_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def detect_device_type(user_agent: str | None) -> str:
    candidate = (user_agent or "").lower()
    if any(token in candidate for token in ("iphone", "android", "mobile", "ipad")):
        return "MOBILE"
    if candidate:
        return "DESKTOP"
    return "UNKNOWN"


def build_device_label(user_agent: str | None) -> str:
    candidate = (user_agent or "").strip()
    if not candidate:
        return "Web Session"
    label = candidate.split("(", 1)[0].strip()
    return label[:120] or "Web Session"


def append_session_event(
    session: Session,
    *,
    auth_session_id: int | None,
    user_id: int | None,
    organization_id: int | None,
    event_type: str,
    event_payload_json: dict[str, Any],
    created_at: datetime | None = None,
) -> UserAuthSessionEvent:
    row = UserAuthSessionEvent(
        auth_session_id=auth_session_id,
        user_id=user_id,
        organization_id=organization_id,
        event_type=event_type,
        event_payload_json=_json_safe(event_payload_json),
        created_at=created_at or utc_now(),
    )
    session.add(row)
    return row


def ensure_security_context(session: Session, *, user_id: int) -> OrganizationSecurityContext:
    row = session.exec(
        select(OrganizationSecurityContext)
        .where(OrganizationSecurityContext.user_id == user_id)
    ).first()
    if row is not None:
        return row
    row = OrganizationSecurityContext(user_id=user_id)
    session.add(row)
    session.flush()
    return row


def create_session(
    session: Session,
    *,
    user_id: int,
    raw_token: str,
    expires_at: datetime,
    device_label: str,
    device_type: str,
    ip_address: str | None,
    user_agent: str | None,
    organization_id: int | None = None,
    issued_at: datetime | None = None,
) -> UserAuthSession:
    now = issued_at or utc_now()
    row = UserAuthSession(
        user_id=user_id,
        session_token_hash=hash_session_token(raw_token),
        device_label=device_label,
        device_type=device_type,
        ip_address=ip_address,
        user_agent=user_agent,
        organization_id=organization_id,
        session_status=ACTIVE_SESSION_STATUS,
        issued_at=now,
        last_seen_at=now,
        expires_at=_coerce_utc(expires_at),
    )
    session.add(row)
    session.flush()
    ensure_security_context(session, user_id=user_id)
    append_session_event(
        session,
        auth_session_id=int(row.id or 0),
        user_id=user_id,
        organization_id=organization_id,
        event_type="session_created",
        event_payload_json={
            "device_label": row.device_label,
            "device_type": row.device_type,
            "expires_at": row.expires_at,
            "ip_address": row.ip_address,
            "session_status": row.session_status,
        },
        created_at=now,
    )
    session.commit()
    session.refresh(row)
    return row


def touch_session_last_seen(session: Session, *, auth_session: UserAuthSession, seen_at: datetime | None = None) -> UserAuthSession:
    auth_session.last_seen_at = seen_at or utc_now()
    session.add(auth_session)
    return auth_session


def validate_session(
    session: Session,
    *,
    raw_token: str,
    expected_user_id: int,
) -> UserAuthSession:
    now = utc_now()
    row = session.exec(
        select(UserAuthSession)
        .where(UserAuthSession.session_token_hash == hash_session_token(raw_token))
    ).first()
    if row is None:
        append_session_event(
            session,
            auth_session_id=None,
            user_id=expected_user_id,
            organization_id=None,
            event_type="invalid_access_attempt",
            event_payload_json={"reason": "session_not_found"},
        )
        session.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication session is invalid.")
    if row.user_id != expected_user_id:
        append_session_event(
            session,
            auth_session_id=int(row.id or 0),
            user_id=expected_user_id,
            organization_id=row.organization_id,
            event_type="invalid_access_attempt",
            event_payload_json={"reason": "session_user_mismatch"},
        )
        session.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication session is invalid.")
    if row.session_status == REVOKED_SESSION_STATUS or row.revoked_at is not None:
        append_session_event(
            session,
            auth_session_id=int(row.id or 0),
            user_id=row.user_id,
            organization_id=row.organization_id,
            event_type="invalid_access_attempt",
            event_payload_json={"reason": "session_revoked"},
        )
        session.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication session has been revoked.")
    if _coerce_utc(row.expires_at) <= now:
        row.session_status = EXPIRED_SESSION_STATUS
        row.revoked_at = now
        session.add(row)
        append_session_event(
            session,
            auth_session_id=int(row.id or 0),
            user_id=row.user_id,
            organization_id=row.organization_id,
            event_type="session_expired",
            event_payload_json={"expires_at": row.expires_at},
        )
        session.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication session has expired.")

    touch_session_last_seen(session, auth_session=row, seen_at=now)
    append_session_event(
        session,
        auth_session_id=int(row.id or 0),
        user_id=row.user_id,
        organization_id=row.organization_id,
        event_type="session_validated",
        event_payload_json={"last_seen_at": row.last_seen_at},
        created_at=now,
    )
    session.commit()
    session.refresh(row)
    return row


def revoke_session(
    session: Session,
    *,
    auth_session: UserAuthSession,
    revoked_by_user_id: int,
    reason: str,
) -> UserAuthSession:
    if auth_session.session_status == REVOKED_SESSION_STATUS:
        return auth_session
    now = utc_now()
    auth_session.session_status = REVOKED_SESSION_STATUS
    auth_session.revoked_at = now
    session.add(auth_session)
    append_session_event(
        session,
        auth_session_id=int(auth_session.id or 0),
        user_id=auth_session.user_id,
        organization_id=auth_session.organization_id,
        event_type="session_revoked",
        event_payload_json={"reason": reason, "revoked_by_user_id": revoked_by_user_id},
        created_at=now,
    )
    if auth_session.organization_id is not None:
        from app.services.activity_feed_integration import record_security_activity

        record_security_activity(
            session,
            organization_id=int(auth_session.organization_id),
            actor_user_id=revoked_by_user_id,
            event_kind="session_revoked",
            payload={
                "title": "Session revoked",
                "body": "An organization session was revoked for security.",
                "reason": reason,
                "target_user_id": auth_session.user_id,
            },
            notify_user_id=int(auth_session.user_id) if auth_session.user_id != revoked_by_user_id else None,
        )
        from app.services.audit_ledger_integration import record_session_audit

        record_session_audit(
            session,
            organization_id=int(auth_session.organization_id),
            actor_user_id=revoked_by_user_id,
            audit_action="session_revoked",
            resource_type="user_auth_session",
            resource_id=int(auth_session.id or 0),
            payload={
                "reason": reason,
                "target_user_id": auth_session.user_id,
            },
            compliance_event_type="security.session_revoked",
            severity_level="elevated",
        )
    session.commit()
    session.refresh(auth_session)
    return auth_session


def revoke_all_user_sessions(
    session: Session,
    *,
    user_id: int,
    revoked_by_user_id: int,
    reason: str,
) -> list[UserAuthSession]:
    rows = session.exec(
        select(UserAuthSession)
        .where(UserAuthSession.user_id == user_id)
        .where(UserAuthSession.session_status == ACTIVE_SESSION_STATUS)
        .order_by(UserAuthSession.issued_at.asc(), UserAuthSession.id.asc())
    ).all()
    revoked: list[UserAuthSession] = []
    for row in rows:
        row.session_status = REVOKED_SESSION_STATUS
        row.revoked_at = utc_now()
        session.add(row)
        append_session_event(
            session,
            auth_session_id=int(row.id or 0),
            user_id=row.user_id,
            organization_id=row.organization_id,
            event_type="session_revoked",
            event_payload_json={"reason": reason, "revoked_by_user_id": revoked_by_user_id},
            created_at=row.revoked_at,
        )
        if row.organization_id is not None:
            from app.services.audit_ledger_integration import record_session_audit

            record_session_audit(
                session,
                organization_id=int(row.organization_id),
                actor_user_id=revoked_by_user_id,
                audit_action="session_revoked",
                resource_type="user_auth_session",
                resource_id=int(row.id or 0),
                payload={
                    "reason": reason,
                    "target_user_id": row.user_id,
                },
                compliance_event_type="security.session_revoked",
                severity_level="elevated",
            )
        revoked.append(row)
    session.commit()
    for row in revoked:
        session.refresh(row)
    return revoked


def switch_active_organization(
    session: Session,
    *,
    user_id: int,
    auth_session: UserAuthSession,
    organization_id: int,
) -> OrganizationSecurityContext:
    member = session.exec(
        select(OrganizationMember)
        .where(OrganizationMember.organization_id == organization_id)
        .where(OrganizationMember.user_id == user_id)
        .where(OrganizationMember.membership_status == "ACTIVE")
    ).first()
    if member is None:
        append_session_event(
            session,
            auth_session_id=int(auth_session.id or 0),
            user_id=user_id,
            organization_id=organization_id,
            event_type="membership_validation_failed",
            event_payload_json={"reason": "active_membership_required"},
        )
        session.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Active organization membership is required.")
    context = ensure_security_context(session, user_id=user_id)
    now = utc_now()
    context.active_organization_id = organization_id
    context.last_org_switch_at = now
    context.updated_at = now
    session.add(context)
    auth_session.organization_id = organization_id
    auth_session.last_seen_at = now
    session.add(auth_session)
    append_session_event(
        session,
        auth_session_id=int(auth_session.id or 0),
        user_id=user_id,
        organization_id=organization_id,
        event_type="organization_switched",
        event_payload_json={"active_organization_id": organization_id},
        created_at=now,
    )
    from app.services.activity_feed_integration import record_security_activity

    record_security_activity(
        session,
        organization_id=organization_id,
        actor_user_id=user_id,
        event_kind="organization_switched",
        payload={
            "title": "Active organization switched",
            "body": f"Session active organization set to {organization_id}.",
            "active_organization_id": organization_id,
        },
    )
    from app.services.audit_ledger_integration import record_session_audit

    record_session_audit(
        session,
        organization_id=organization_id,
        actor_user_id=user_id,
        audit_action="organization_switched",
        resource_type="organization_security_context",
        resource_id=int(context.id or 0),
        payload={"active_organization_id": organization_id, "auth_session_id": int(auth_session.id or 0)},
    )
    session.commit()
    session.refresh(context)
    session.refresh(auth_session)
    return context


def expire_stale_sessions(session: Session, *, now: datetime | None = None) -> list[UserAuthSession]:
    current_time = now or utc_now()
    rows = session.exec(
        select(UserAuthSession)
        .where(UserAuthSession.session_status == ACTIVE_SESSION_STATUS)
        .where(UserAuthSession.expires_at <= current_time)
        .order_by(UserAuthSession.expires_at.asc(), UserAuthSession.id.asc())
    ).all()
    expired: list[UserAuthSession] = []
    for row in rows:
        row.session_status = EXPIRED_SESSION_STATUS
        row.revoked_at = current_time
        session.add(row)
        append_session_event(
            session,
            auth_session_id=int(row.id or 0),
            user_id=row.user_id,
            organization_id=row.organization_id,
            event_type="session_expired",
            event_payload_json={"expires_at": row.expires_at},
            created_at=current_time,
        )
        expired.append(row)
    session.commit()
    for row in expired:
        session.refresh(row)
    return expired
