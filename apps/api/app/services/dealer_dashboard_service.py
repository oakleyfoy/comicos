from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, func, select

from app.models import (
    OrganizationActivityEvent,
    OrganizationDealerDashboardEvent,
    OrganizationDealerDashboardSnapshot,
    OrganizationDealerOperationalMetric,
    OrganizationInventoryAssignment,
    OrganizationInventoryQueue,
    OrganizationMember,
    OrganizationNotification,
    OrganizationReview,
    UserAuthSession,
)
from app.schemas.organization_activity import LINEAGE_ACTIVITY_PREFIX
from app.schemas.organization_dealer_dashboard import (
    DASHBOARD_SECTIONS,
    DEFAULT_METRIC_PERIOD,
    LINEAGE_DASHBOARD_PREFIX,
    METRIC_KEYS,
    OrganizationDealerDashboardSectionSummary,
    OrganizationDealerDashboardSnapshotListResponse,
    OrganizationDealerDashboardSnapshotResponse,
    OrganizationDealerDashboardSummaryResponse,
    OrganizationDealerOperationalMetricListResponse,
    OrganizationDealerOperationalMetricResponse,
)
from app.security.tenant_context import get_membership_record, get_organization_or_404
from app.services.authorization_service import evaluate_permission
from app.services.dealer_profile_service import resolve_public_inventory_visibility
from app.services.review_workflow_service import REVIEW_STATUS_APPROVED, REVIEW_STATUS_COMPLETED, REVIEW_STATUS_REJECTED

ENGINE_VERSION = "P42-09-v1"
DASHBOARD_VIEW_PERMISSION = "operations:view"
ACTIVE_MEMBERSHIP_STATUS = "ACTIVE"
ACTIVE_ORGANIZATION_STATUS = "ACTIVE"
ACTIVE_ASSIGNMENT_STATUS = "ACTIVE"
ACTIVE_QUEUE_STATUS = "ACTIVE"
ACTIVE_SESSION_STATUS = "ACTIVE"
NOTIFICATION_UNREAD = "UNREAD"
SYSTEM_ACTIVITY_VISIBILITY = "SYSTEM"
SNAPSHOT_TYPE_OPERATIONAL = "operational"

METRIC_KEY_TO_GROUP: dict[str, str] = {
    "active_inventory_count": "inventory",
    "pending_reviews_count": "reviews",
    "assigned_inventory_count": "assignments",
    "unread_notifications_count": "notifications",
    "active_staff_count": "inventory",
    "storefront_public_inventory_count": "storefront",
    "recent_activity_count": "activity",
    "active_org_sessions_count": "security",
}

SECTION_METRIC_KEYS: dict[str, tuple[str, ...]] = {
    "inventory": ("active_inventory_count", "active_staff_count"),
    "reviews": ("pending_reviews_count",),
    "activity": ("recent_activity_count",),
    "storefront": ("storefront_public_inventory_count",),
    "notifications": ("unread_notifications_count",),
    "security": ("active_org_sessions_count",),
    "assignments": ("assigned_inventory_count",),
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def clamp_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 200), max(offset, 0)


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _stable_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(_json_safe(payload), sort_keys=True))


def _metric_group(metric_key: str) -> str:
    return METRIC_KEY_TO_GROUP.get(metric_key, "inventory")


def _to_snapshot_response(row: OrganizationDealerDashboardSnapshot) -> OrganizationDealerDashboardSnapshotResponse:
    assert row.id is not None
    return OrganizationDealerDashboardSnapshotResponse(
        id=int(row.id),
        organization_id=int(row.organization_id),
        snapshot_type=str(row.snapshot_type),
        snapshot_payload_json=dict(row.snapshot_payload_json or {}),
        generated_at=row.generated_at,
    )


def _to_metric_response(row: OrganizationDealerOperationalMetric) -> OrganizationDealerOperationalMetricResponse:
    assert row.id is not None
    payload = dict(row.metric_value_json or {})
    group = str(payload.get("metric_group") or _metric_group(str(row.metric_key)))
    return OrganizationDealerOperationalMetricResponse(
        id=int(row.id),
        organization_id=int(row.organization_id),
        metric_key=str(row.metric_key),
        metric_value_json=payload,
        metric_group=group,
        metric_period=str(row.metric_period),
        generated_at=row.generated_at,
    )


def create_dashboard_event(
    session: Session,
    *,
    organization_id: int,
    event_type: str,
    event_payload_json: dict[str, Any] | None = None,
) -> OrganizationDealerDashboardEvent:
    row = OrganizationDealerDashboardEvent(
        organization_id=organization_id,
        event_type=event_type,
        event_payload_json=_stable_payload(event_payload_json or {}),
    )
    session.add(row)
    session.flush()
    return row


def _append_lineage_event(
    session: Session,
    *,
    organization_id: int,
    lineage_type: str,
    payload: dict[str, Any] | None = None,
) -> OrganizationDealerDashboardEvent:
    return create_dashboard_event(
        session,
        organization_id=organization_id,
        event_type=f"{LINEAGE_DASHBOARD_PREFIX}{lineage_type}",
        event_payload_json=payload,
    )


def _record_unauthorized_dashboard_attempt(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    reason: str,
) -> None:
    audit_session = Session(session.get_bind())
    try:
        _append_lineage_event(
            audit_session,
            organization_id=organization_id,
            lineage_type="unauthorized_dashboard_access_attempt",
            payload={"reason": reason, "actor_user_id": actor_user_id},
        )
        audit_session.commit()
    finally:
        audit_session.close()


def _require_dashboard_access(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    record_access: bool = True,
) -> None:
    organization = get_organization_or_404(session, organization_id=organization_id)
    if organization.status != ACTIVE_ORGANIZATION_STATUS:
        raise HTTPException(status_code=409, detail="Organization is not active.")
    member = get_membership_record(session, organization_id=organization_id, user_id=actor_user_id, active_only=True)
    if member is None:
        _record_unauthorized_dashboard_attempt(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            reason="membership_required",
        )
        raise HTTPException(status_code=403, detail="Organization dashboard access denied.")
    evaluation = evaluate_permission(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action_key=DASHBOARD_VIEW_PERMISSION,
    )
    if not evaluation.allowed:
        _record_unauthorized_dashboard_attempt(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            reason=evaluation.reason,
        )
        raise HTTPException(status_code=403, detail="Organization dashboard access denied.")
    if record_access:
        _append_lineage_event(
            session,
            organization_id=organization_id,
            lineage_type="dashboard_accessed",
            payload={"actor_user_id": actor_user_id},
        )
        session.commit()


def _compute_metric_values(session: Session, *, organization_id: int) -> dict[str, dict[str, Any]]:
    member_user_ids = session.exec(
        select(OrganizationMember.user_id)
        .where(OrganizationMember.organization_id == organization_id)
        .where(OrganizationMember.membership_status == ACTIVE_MEMBERSHIP_STATUS)
    ).all()
    staff_ids = tuple(int(uid) for uid in member_user_ids if uid is not None)

    assigned_count = session.exec(
        select(func.count())
        .select_from(OrganizationInventoryAssignment)
        .where(OrganizationInventoryAssignment.organization_id == organization_id)
        .where(OrganizationInventoryAssignment.assignment_status == ACTIVE_ASSIGNMENT_STATUS)
    ).one()

    queue_inventory_ids = session.exec(
        select(OrganizationInventoryQueue.inventory_item_id)
        .where(OrganizationInventoryQueue.organization_id == organization_id)
        .where(OrganizationInventoryQueue.queue_status == ACTIVE_QUEUE_STATUS)
    ).all()
    assignment_inventory_ids = session.exec(
        select(OrganizationInventoryAssignment.inventory_item_id)
        .where(OrganizationInventoryAssignment.organization_id == organization_id)
        .where(OrganizationInventoryAssignment.assignment_status == ACTIVE_ASSIGNMENT_STATUS)
    ).all()
    active_inventory_ids = set(int(v) for v in queue_inventory_ids if v is not None) | set(
        int(v) for v in assignment_inventory_ids if v is not None
    )

    pending_reviews = session.exec(
        select(func.count())
        .select_from(OrganizationReview)
        .where(OrganizationReview.organization_id == organization_id)
        .where(OrganizationReview.review_status.not_in([REVIEW_STATUS_APPROVED, REVIEW_STATUS_REJECTED, REVIEW_STATUS_COMPLETED]))
    ).one()

    unread_notifications = session.exec(
        select(func.count())
        .select_from(OrganizationNotification)
        .where(OrganizationNotification.organization_id == organization_id)
        .where(OrganizationNotification.notification_status == NOTIFICATION_UNREAD)
    ).one()

    try:
        public_inventory_count = len(resolve_public_inventory_visibility(session, organization_id=organization_id))
    except HTTPException:
        public_inventory_count = 0

    recent_activity = session.exec(
        select(func.count())
        .select_from(OrganizationActivityEvent)
        .where(OrganizationActivityEvent.organization_id == organization_id)
        .where(OrganizationActivityEvent.visibility_scope != SYSTEM_ACTIVITY_VISIBILITY)
        .where(~OrganizationActivityEvent.activity_type.like(f"{LINEAGE_ACTIVITY_PREFIX}%"))
    ).one()

    active_sessions = 0
    if staff_ids:
        active_sessions = session.exec(
            select(func.count())
            .select_from(UserAuthSession)
            .where(UserAuthSession.organization_id == organization_id)
            .where(UserAuthSession.user_id.in_(staff_ids))
            .where(UserAuthSession.session_status == ACTIVE_SESSION_STATUS)
        ).one()

    def pack(metric_key: str, value: int | float) -> dict[str, Any]:
        return _stable_payload(
            {
                "value": int(value),
                "metric_group": _metric_group(metric_key),
                "engine_version": ENGINE_VERSION,
            }
        )

    return {
        "active_inventory_count": pack("active_inventory_count", len(active_inventory_ids)),
        "pending_reviews_count": pack("pending_reviews_count", int(pending_reviews)),
        "assigned_inventory_count": pack("assigned_inventory_count", int(assigned_count)),
        "unread_notifications_count": pack("unread_notifications_count", int(unread_notifications)),
        "active_staff_count": pack("active_staff_count", len(staff_ids)),
        "storefront_public_inventory_count": pack("storefront_public_inventory_count", public_inventory_count),
        "recent_activity_count": pack("recent_activity_count", int(recent_activity)),
        "active_org_sessions_count": pack("active_org_sessions_count", int(active_sessions)),
    }


def generate_operational_metrics(
    session: Session,
    *,
    organization_id: int,
    metric_period: str = DEFAULT_METRIC_PERIOD,
) -> list[OrganizationDealerOperationalMetric]:
    values = _compute_metric_values(session, organization_id=organization_id)
    rows: list[OrganizationDealerOperationalMetric] = []
    for metric_key in METRIC_KEYS:
        row = OrganizationDealerOperationalMetric(
            organization_id=organization_id,
            metric_key=metric_key,
            metric_value_json=values[metric_key],
            metric_period=metric_period,
        )
        session.add(row)
        session.flush()
        assert row.id is not None
        _append_lineage_event(
            session,
            organization_id=organization_id,
            lineage_type="dashboard_metric_generated",
            payload={"metric_id": int(row.id), "metric_key": metric_key},
        )
        rows.append(row)
        if metric_key == "pending_reviews_count" and int(values[metric_key]["value"]) >= 10:
            _append_lineage_event(
                session,
                organization_id=organization_id,
                lineage_type="elevated_operational_alert",
                payload={"metric_key": metric_key, "value": int(values[metric_key]["value"])},
            )
    return rows


def generate_dashboard_snapshot(
    session: Session,
    *,
    organization_id: int,
    snapshot_type: str = SNAPSHOT_TYPE_OPERATIONAL,
) -> OrganizationDealerDashboardSnapshot:
    values = _compute_metric_values(session, organization_id=organization_id)
    sections: list[dict[str, Any]] = []
    for section_key in DASHBOARD_SECTIONS:
        metric_keys = SECTION_METRIC_KEYS.get(section_key, ())
        metrics = {key: values[key]["value"] for key in metric_keys if key in values}
        sections.append({"section_key": section_key, "metrics": metrics})
    payload = _stable_payload(
        {
            "sections": sections,
            "metric_keys": list(METRIC_KEYS),
            "engine_version": ENGINE_VERSION,
        }
    )
    now = utc_now()
    row = OrganizationDealerDashboardSnapshot(
        organization_id=organization_id,
        snapshot_type=snapshot_type,
        snapshot_payload_json=payload,
        generated_at=now,
    )
    session.add(row)
    session.flush()
    assert row.id is not None
    _append_lineage_event(
        session,
        organization_id=organization_id,
        lineage_type="dashboard_snapshot_generated",
        payload={"snapshot_id": int(row.id), "snapshot_type": snapshot_type},
    )
    return row


def _latest_metrics_by_key(
    session: Session,
    *,
    organization_id: int,
) -> dict[str, OrganizationDealerOperationalMetric]:
    rows = session.exec(
        select(OrganizationDealerOperationalMetric)
        .where(OrganizationDealerOperationalMetric.organization_id == organization_id)
        .order_by(OrganizationDealerOperationalMetric.generated_at.desc(), OrganizationDealerOperationalMetric.id.desc())
    ).all()
    latest: dict[str, OrganizationDealerOperationalMetric] = {}
    for row in rows:
        key = str(row.metric_key)
        if key not in latest:
            latest[key] = row
    return latest


def resolve_dashboard_summary(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    refresh: bool = True,
) -> OrganizationDealerDashboardSummaryResponse:
    _require_dashboard_access(session, organization_id=organization_id, actor_user_id=actor_user_id, record_access=True)
    snapshot: OrganizationDealerDashboardSnapshot | None = None
    if refresh:
        generate_operational_metrics(session, organization_id=organization_id)
        snapshot = generate_dashboard_snapshot(session, organization_id=organization_id)
        session.commit()
    else:
        snapshot = session.exec(
            select(OrganizationDealerDashboardSnapshot)
            .where(OrganizationDealerDashboardSnapshot.organization_id == organization_id)
            .order_by(OrganizationDealerDashboardSnapshot.generated_at.desc(), OrganizationDealerDashboardSnapshot.id.desc())
        ).first()

    latest_metrics = _latest_metrics_by_key(session, organization_id=organization_id)
    sections: list[OrganizationDealerDashboardSectionSummary] = []
    for section_key in DASHBOARD_SECTIONS:
        metric_keys = SECTION_METRIC_KEYS.get(section_key, ())
        metrics: dict[str, object] = {}
        for key in metric_keys:
            row = latest_metrics.get(key)
            if row is not None:
                metrics[key] = dict(row.metric_value_json or {}).get("value", 0)
        sections.append(OrganizationDealerDashboardSectionSummary(section_key=section_key, metrics=metrics))

    generated_at = snapshot.generated_at if snapshot is not None else utc_now()
    return OrganizationDealerDashboardSummaryResponse(
        organization_id=organization_id,
        snapshot=_to_snapshot_response(snapshot) if snapshot is not None else None,
        sections=sections,
        generated_at=generated_at,
    )


def list_dashboard_snapshots(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> OrganizationDealerDashboardSnapshotListResponse:
    _require_dashboard_access(session, organization_id=organization_id, actor_user_id=actor_user_id, record_access=False)
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(OrganizationDealerDashboardSnapshot).where(
        OrganizationDealerDashboardSnapshot.organization_id == organization_id
    )
    rows = session.exec(
        stmt.order_by(OrganizationDealerDashboardSnapshot.generated_at.desc(), OrganizationDealerDashboardSnapshot.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    total = session.exec(
        select(func.count())
        .select_from(OrganizationDealerDashboardSnapshot)
        .where(OrganizationDealerDashboardSnapshot.organization_id == organization_id)
    ).one()
    return OrganizationDealerDashboardSnapshotListResponse(
        items=[_to_snapshot_response(row) for row in rows],
        total_items=int(total),
        limit=limit,
        offset=offset,
    )


def list_dashboard_metrics(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int = 50,
    offset: int = 0,
    metric_period: str | None = None,
) -> OrganizationDealerOperationalMetricListResponse:
    _require_dashboard_access(session, organization_id=organization_id, actor_user_id=actor_user_id, record_access=False)
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(OrganizationDealerOperationalMetric).where(
        OrganizationDealerOperationalMetric.organization_id == organization_id
    )
    count_stmt = select(func.count()).select_from(OrganizationDealerOperationalMetric).where(
        OrganizationDealerOperationalMetric.organization_id == organization_id
    )
    if metric_period:
        stmt = stmt.where(OrganizationDealerOperationalMetric.metric_period == metric_period)
        count_stmt = count_stmt.where(OrganizationDealerOperationalMetric.metric_period == metric_period)
    rows = session.exec(
        stmt.order_by(OrganizationDealerOperationalMetric.generated_at.desc(), OrganizationDealerOperationalMetric.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    total = session.exec(count_stmt).one()
    return OrganizationDealerOperationalMetricListResponse(
        items=[_to_metric_response(row) for row in rows],
        total_items=int(total),
        limit=limit,
        offset=offset,
    )
