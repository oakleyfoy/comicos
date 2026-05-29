from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, func, select

from app.models import (
    OrganizationInventoryAssignment,
    OrganizationInventoryQueue,
    OrganizationInventoryWorkflowEvent,
    OrganizationMember,
)
from app.schemas.organization_inventory import (
    ORG_INVENTORY_QUEUE_NAMES,
    OrganizationInventoryAssignmentListResponse,
    OrganizationInventoryAssignmentResponse,
    OrganizationInventoryQueueListResponse,
    OrganizationInventoryQueueResponse,
    OrganizationInventoryWorkflowEventListResponse,
    OrganizationInventoryWorkflowEventResponse,
)
from app.services.organization_inventory_access import (
    validate_inventory_assignment_access,
    validate_org_inventory_membership,
    validate_shared_inventory_access,
)

ENGINE_VERSION = "P42-04-v1"
ACTIVE_ASSIGNMENT_STATUS = "ACTIVE"
COMPLETED_ASSIGNMENT_STATUS = "COMPLETED"
UNASSIGNED_ASSIGNMENT_STATUS = "UNASSIGNED"
ACTIVE_QUEUE_STATUS = "ACTIVE"
REMOVED_QUEUE_STATUS = "REMOVED"
ACTIVE_MEMBERSHIP_STATUS = "ACTIVE"
DEFAULT_QUEUE_NAME = "intake"


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


def create_workflow_event(
    session: Session,
    *,
    organization_id: int,
    inventory_item_id: int | None,
    actor_user_id: int | None,
    workflow_event_type: str,
    workflow_payload_json: dict[str, Any] | None = None,
) -> OrganizationInventoryWorkflowEvent:
    row = OrganizationInventoryWorkflowEvent(
        organization_id=organization_id,
        inventory_item_id=inventory_item_id,
        actor_user_id=actor_user_id,
        workflow_event_type=workflow_event_type,
        workflow_payload_json=_stable_payload(workflow_payload_json or {}),
    )
    session.add(row)
    session.flush()
    return row


def _to_assignment_response(row: OrganizationInventoryAssignment) -> OrganizationInventoryAssignmentResponse:
    assert row.id is not None
    return OrganizationInventoryAssignmentResponse(
        id=int(row.id),
        organization_id=int(row.organization_id),
        inventory_item_id=int(row.inventory_item_id),
        assigned_user_id=int(row.assigned_user_id),
        assigned_by_user_id=int(row.assigned_by_user_id),
        assignment_status=str(row.assignment_status),
        assignment_notes=row.assignment_notes,
        assigned_at=row.assigned_at,
        completed_at=row.completed_at,
    )


def _to_queue_response(row: OrganizationInventoryQueue) -> OrganizationInventoryQueueResponse:
    assert row.id is not None
    return OrganizationInventoryQueueResponse(
        id=int(row.id),
        organization_id=int(row.organization_id),
        queue_name=str(row.queue_name),
        inventory_item_id=int(row.inventory_item_id),
        queue_position=int(row.queue_position),
        queue_status=str(row.queue_status),
        created_at=row.created_at,
    )


def _to_event_response(row: OrganizationInventoryWorkflowEvent) -> OrganizationInventoryWorkflowEventResponse:
    assert row.id is not None
    return OrganizationInventoryWorkflowEventResponse(
        id=int(row.id),
        organization_id=int(row.organization_id),
        inventory_item_id=row.inventory_item_id,
        actor_user_id=row.actor_user_id,
        workflow_event_type=str(row.workflow_event_type),
        workflow_payload_json=dict(row.workflow_payload_json or {}),
        created_at=row.created_at,
    )


def _active_assignment(
    session: Session,
    *,
    organization_id: int,
    inventory_item_id: int,
) -> OrganizationInventoryAssignment | None:
    return session.exec(
        select(OrganizationInventoryAssignment)
        .where(OrganizationInventoryAssignment.organization_id == organization_id)
        .where(OrganizationInventoryAssignment.inventory_item_id == inventory_item_id)
        .where(OrganizationInventoryAssignment.assignment_status == ACTIVE_ASSIGNMENT_STATUS)
        .order_by(OrganizationInventoryAssignment.assigned_at.asc(), OrganizationInventoryAssignment.id.asc())
    ).first()


def _ensure_assignee_is_member(
    session: Session,
    *,
    organization_id: int,
    assigned_user_id: int,
) -> None:
    member = session.exec(
        select(OrganizationMember)
        .where(OrganizationMember.organization_id == organization_id)
        .where(OrganizationMember.user_id == assigned_user_id)
        .where(OrganizationMember.membership_status == ACTIVE_MEMBERSHIP_STATUS)
    ).first()
    if member is None:
        raise HTTPException(status_code=400, detail="Assigned user must be an active organization member.")


def _active_queue_row(
    session: Session,
    *,
    organization_id: int,
    inventory_item_id: int,
) -> OrganizationInventoryQueue | None:
    return session.exec(
        select(OrganizationInventoryQueue)
        .where(OrganizationInventoryQueue.organization_id == organization_id)
        .where(OrganizationInventoryQueue.inventory_item_id == inventory_item_id)
    ).first()


def _ensure_queue_row(
    session: Session,
    *,
    organization_id: int,
    inventory_item_id: int,
    queue_name: str = DEFAULT_QUEUE_NAME,
    actor_user_id: int | None = None,
) -> OrganizationInventoryQueue:
    existing = _active_queue_row(
        session,
        organization_id=organization_id,
        inventory_item_id=inventory_item_id,
    )
    if existing is not None:
        if existing.queue_status == ACTIVE_QUEUE_STATUS and existing.queue_name == queue_name:
            return existing
        previous_name = existing.queue_name
        previous_position = int(existing.queue_position)
        existing.queue_name = queue_name
        existing.queue_position = _next_queue_position(
            session,
            organization_id=organization_id,
            queue_name=queue_name,
            exclude_inventory_item_id=inventory_item_id,
        )
        existing.queue_status = ACTIVE_QUEUE_STATUS
        session.add(existing)
        session.flush()
        create_workflow_event(
            session,
            organization_id=organization_id,
            inventory_item_id=inventory_item_id,
            actor_user_id=actor_user_id,
            workflow_event_type="queue_moved",
            workflow_payload_json={
                "queue_name": queue_name,
                "queue_position": int(existing.queue_position),
                "previous_queue_name": previous_name,
                "previous_queue_position": previous_position,
                "queue_id": int(existing.id or 0),
            },
        )
        return existing
    position = _next_queue_position(session, organization_id=organization_id, queue_name=queue_name)
    row = OrganizationInventoryQueue(
        organization_id=organization_id,
        queue_name=queue_name,
        inventory_item_id=inventory_item_id,
        queue_position=position,
        queue_status=ACTIVE_QUEUE_STATUS,
    )
    session.add(row)
    session.flush()
    create_workflow_event(
        session,
        organization_id=organization_id,
        inventory_item_id=inventory_item_id,
        actor_user_id=actor_user_id,
        workflow_event_type="queue_created",
        workflow_payload_json={"queue_name": queue_name, "queue_position": position, "queue_id": int(row.id or 0)},
    )
    return row


def _next_queue_position(
    session: Session,
    *,
    organization_id: int,
    queue_name: str,
    exclude_inventory_item_id: int | None = None,
) -> int:
    stmt = (
        select(func.max(OrganizationInventoryQueue.queue_position))
        .where(OrganizationInventoryQueue.organization_id == organization_id)
        .where(OrganizationInventoryQueue.queue_name == queue_name)
        .where(OrganizationInventoryQueue.queue_status == ACTIVE_QUEUE_STATUS)
    )
    if exclude_inventory_item_id is not None:
        stmt = stmt.where(OrganizationInventoryQueue.inventory_item_id != exclude_inventory_item_id)
    current_max = session.exec(stmt).one()
    if current_max is None:
        return 1
    return int(current_max) + 1


def assign_inventory_item(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    inventory_item_id: int,
    assigned_user_id: int,
    assignment_notes: str | None = None,
) -> OrganizationInventoryAssignmentResponse:
    validate_inventory_assignment_access(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        inventory_item_id=inventory_item_id,
    )
    validate_org_inventory_membership(session, organization_id=organization_id, inventory_item_id=inventory_item_id)
    _ensure_assignee_is_member(session, organization_id=organization_id, assigned_user_id=assigned_user_id)
    existing = _active_assignment(session, organization_id=organization_id, inventory_item_id=inventory_item_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Inventory item already has an active assignment.")
    row = OrganizationInventoryAssignment(
        organization_id=organization_id,
        inventory_item_id=inventory_item_id,
        assigned_user_id=assigned_user_id,
        assigned_by_user_id=actor_user_id,
        assignment_status=ACTIVE_ASSIGNMENT_STATUS,
        assignment_notes=assignment_notes,
    )
    session.add(row)
    session.flush()
    _ensure_queue_row(
        session,
        organization_id=organization_id,
        inventory_item_id=inventory_item_id,
        actor_user_id=actor_user_id,
    )
    create_workflow_event(
        session,
        organization_id=organization_id,
        inventory_item_id=inventory_item_id,
        actor_user_id=actor_user_id,
        workflow_event_type="inventory_assigned",
        workflow_payload_json={
            "assignment_id": int(row.id or 0),
            "assigned_user_id": assigned_user_id,
            "assigned_by_user_id": actor_user_id,
            "engine_version": ENGINE_VERSION,
        },
    )
    from app.services.activity_feed_integration import record_inventory_activity

    record_inventory_activity(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_kind="assigned",
        payload={
            "title": "Inventory assigned",
            "body": f"Inventory copy {inventory_item_id} was assigned to user {assigned_user_id}.",
            "inventory_item_id": inventory_item_id,
            "assignment_id": int(row.id or 0),
            "assigned_user_id": assigned_user_id,
        },
        notify_user_id=assigned_user_id,
    )
    from app.services.audit_ledger_integration import record_inventory_audit

    record_inventory_audit(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        audit_action="inventory_assigned",
        resource_type="inventory_copy",
        resource_id=inventory_item_id,
        payload={
            "assignment_id": int(row.id or 0),
            "assigned_user_id": assigned_user_id,
            "assigned_by_user_id": actor_user_id,
        },
    )
    session.commit()
    session.refresh(row)
    return _to_assignment_response(row)


def unassign_inventory_item(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    inventory_item_id: int,
    assignment_notes: str | None = None,
) -> OrganizationInventoryAssignmentResponse:
    validate_inventory_assignment_access(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        inventory_item_id=inventory_item_id,
    )
    row = _active_assignment(session, organization_id=organization_id, inventory_item_id=inventory_item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Active assignment not found.")
    row.assignment_status = UNASSIGNED_ASSIGNMENT_STATUS
    if assignment_notes:
        row.assignment_notes = assignment_notes
    session.add(row)
    session.flush()
    create_workflow_event(
        session,
        organization_id=organization_id,
        inventory_item_id=inventory_item_id,
        actor_user_id=actor_user_id,
        workflow_event_type="inventory_unassigned",
        workflow_payload_json={"assignment_id": int(row.id or 0), "engine_version": ENGINE_VERSION},
    )
    from app.services.audit_ledger_integration import record_inventory_audit

    record_inventory_audit(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        audit_action="inventory_unassigned",
        resource_type="inventory_copy",
        resource_id=inventory_item_id,
        payload={"assignment_id": int(row.id or 0)},
    )
    session.commit()
    session.refresh(row)
    return _to_assignment_response(row)


def complete_assignment(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    inventory_item_id: int,
    assignment_notes: str | None = None,
) -> OrganizationInventoryAssignmentResponse:
    validate_inventory_assignment_access(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        inventory_item_id=inventory_item_id,
    )
    row = _active_assignment(session, organization_id=organization_id, inventory_item_id=inventory_item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Active assignment not found.")
    row.assignment_status = COMPLETED_ASSIGNMENT_STATUS
    row.completed_at = utc_now()
    if assignment_notes:
        row.assignment_notes = assignment_notes
    session.add(row)
    session.flush()
    create_workflow_event(
        session,
        organization_id=organization_id,
        inventory_item_id=inventory_item_id,
        actor_user_id=actor_user_id,
        workflow_event_type="assignment_completed",
        workflow_payload_json={"assignment_id": int(row.id or 0), "engine_version": ENGINE_VERSION},
    )
    from app.services.audit_ledger_integration import record_inventory_audit

    record_inventory_audit(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        audit_action="assignment_completed",
        resource_type="inventory_copy",
        resource_id=inventory_item_id,
        payload={"assignment_id": int(row.id or 0), "completed_at": row.completed_at},
    )
    session.commit()
    session.refresh(row)
    return _to_assignment_response(row)


def move_inventory_queue(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    inventory_item_id: int,
    queue_name: str,
    queue_position: int | None = None,
) -> OrganizationInventoryQueueResponse:
    if queue_name not in ORG_INVENTORY_QUEUE_NAMES:
        raise HTTPException(status_code=400, detail="Unsupported organization inventory queue.")
    validate_inventory_assignment_access(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        inventory_item_id=inventory_item_id,
    )
    validate_org_inventory_membership(session, organization_id=organization_id, inventory_item_id=inventory_item_id)
    existing = _active_queue_row(
        session,
        organization_id=organization_id,
        inventory_item_id=inventory_item_id,
    )
    previous_name = existing.queue_name if existing is not None else None
    previous_position = int(existing.queue_position) if existing is not None else None
    if existing is None:
        position = queue_position or _next_queue_position(session, organization_id=organization_id, queue_name=queue_name)
        row = OrganizationInventoryQueue(
            organization_id=organization_id,
            queue_name=queue_name,
            inventory_item_id=inventory_item_id,
            queue_position=position,
            queue_status=ACTIVE_QUEUE_STATUS,
        )
        session.add(row)
        session.flush()
        create_workflow_event(
            session,
            organization_id=organization_id,
            inventory_item_id=inventory_item_id,
            actor_user_id=actor_user_id,
            workflow_event_type="queue_created",
            workflow_payload_json={
                "queue_name": queue_name,
                "queue_position": position,
                "queue_id": int(row.id or 0),
                "engine_version": ENGINE_VERSION,
            },
        )
        session.commit()
        session.refresh(row)
        return _to_queue_response(row)
    if existing.queue_status == REMOVED_QUEUE_STATUS:
        existing.queue_status = ACTIVE_QUEUE_STATUS
    position = queue_position or _next_queue_position(
        session,
        organization_id=organization_id,
        queue_name=queue_name,
        exclude_inventory_item_id=inventory_item_id,
    )
    existing.queue_name = queue_name
    existing.queue_position = position
    session.add(existing)
    session.flush()
    create_workflow_event(
        session,
        organization_id=organization_id,
        inventory_item_id=inventory_item_id,
        actor_user_id=actor_user_id,
        workflow_event_type="queue_moved" if previous_name is not None else "queue_created",
        workflow_payload_json={
            "queue_name": queue_name,
            "queue_position": position,
            "previous_queue_name": previous_name,
            "previous_queue_position": previous_position,
            "queue_id": int(existing.id or 0),
            "engine_version": ENGINE_VERSION,
        },
    )
    session.commit()
    session.refresh(existing)
    return _to_queue_response(existing)


def list_org_inventory_assignments(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int = 50,
    offset: int = 0,
    assignment_status: str | None = None,
) -> OrganizationInventoryAssignmentListResponse:
    validate_shared_inventory_access(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action_key="inventory:view",
    )
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = (
        select(OrganizationInventoryAssignment)
        .where(OrganizationInventoryAssignment.organization_id == organization_id)
        .order_by(
            OrganizationInventoryAssignment.assigned_at.desc(),
            OrganizationInventoryAssignment.id.desc(),
        )
    )
    if assignment_status:
        stmt = stmt.where(OrganizationInventoryAssignment.assignment_status == assignment_status)
    rows = session.exec(stmt.offset(offset).limit(limit)).all()
    count_stmt = (
        select(func.count())
        .select_from(OrganizationInventoryAssignment)
        .where(OrganizationInventoryAssignment.organization_id == organization_id)
    )
    if assignment_status:
        count_stmt = count_stmt.where(OrganizationInventoryAssignment.assignment_status == assignment_status)
    total = session.exec(count_stmt).one()
    return OrganizationInventoryAssignmentListResponse(
        items=[_to_assignment_response(row) for row in rows],
        total_items=int(total),
        limit=limit,
        offset=offset,
    )


def list_org_inventory_queues(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int = 100,
    offset: int = 0,
    queue_name: str | None = None,
) -> OrganizationInventoryQueueListResponse:
    validate_shared_inventory_access(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action_key="inventory:view",
    )
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = (
        select(OrganizationInventoryQueue)
        .where(OrganizationInventoryQueue.organization_id == organization_id)
        .where(OrganizationInventoryQueue.queue_status == ACTIVE_QUEUE_STATUS)
        .order_by(
            OrganizationInventoryQueue.queue_name.asc(),
            OrganizationInventoryQueue.queue_position.asc(),
            OrganizationInventoryQueue.id.asc(),
        )
    )
    if queue_name:
        stmt = stmt.where(OrganizationInventoryQueue.queue_name == queue_name)
    rows = session.exec(stmt.offset(offset).limit(limit)).all()
    count_stmt = (
        select(func.count())
        .select_from(OrganizationInventoryQueue)
        .where(OrganizationInventoryQueue.organization_id == organization_id)
        .where(OrganizationInventoryQueue.queue_status == ACTIVE_QUEUE_STATUS)
    )
    if queue_name:
        count_stmt = count_stmt.where(OrganizationInventoryQueue.queue_name == queue_name)
    total = session.exec(count_stmt).one()
    return OrganizationInventoryQueueListResponse(
        items=[_to_queue_response(row) for row in rows],
        total_items=int(total),
        limit=limit,
        offset=offset,
    )


def list_org_inventory_workflow_events(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int = 100,
    offset: int = 0,
) -> OrganizationInventoryWorkflowEventListResponse:
    validate_shared_inventory_access(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action_key="audit:view",
    )
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    rows = session.exec(
        select(OrganizationInventoryWorkflowEvent)
        .where(OrganizationInventoryWorkflowEvent.organization_id == organization_id)
        .order_by(
            OrganizationInventoryWorkflowEvent.created_at.desc(),
            OrganizationInventoryWorkflowEvent.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()
    total = session.exec(
        select(func.count())
        .select_from(OrganizationInventoryWorkflowEvent)
        .where(OrganizationInventoryWorkflowEvent.organization_id == organization_id)
    ).one()
    return OrganizationInventoryWorkflowEventListResponse(
        items=[_to_event_response(row) for row in rows],
        total_items=int(total),
        limit=limit,
        offset=offset,
    )


def assignment_metadata_for_inventory_ids(
    session: Session,
    *,
    organization_id: int,
    inventory_item_ids: tuple[int, ...],
) -> dict[int, dict[str, object]]:
    if not inventory_item_ids:
        return {}
    assignments = session.exec(
        select(OrganizationInventoryAssignment)
        .where(OrganizationInventoryAssignment.organization_id == organization_id)
        .where(OrganizationInventoryAssignment.inventory_item_id.in_(inventory_item_ids))
        .where(OrganizationInventoryAssignment.assignment_status == ACTIVE_ASSIGNMENT_STATUS)
        .order_by(OrganizationInventoryAssignment.assigned_at.asc(), OrganizationInventoryAssignment.id.asc())
    ).all()
    queues = session.exec(
        select(OrganizationInventoryQueue)
        .where(OrganizationInventoryQueue.organization_id == organization_id)
        .where(OrganizationInventoryQueue.inventory_item_id.in_(inventory_item_ids))
        .where(OrganizationInventoryQueue.queue_status == ACTIVE_QUEUE_STATUS)
        .order_by(OrganizationInventoryQueue.id.asc())
    ).all()
    assignment_by_item = {int(row.inventory_item_id): row for row in assignments}
    queue_by_item = {int(row.inventory_item_id): row for row in queues}
    metadata: dict[int, dict[str, object]] = {}
    for inv_id in inventory_item_ids:
        assignment = assignment_by_item.get(inv_id)
        queue = queue_by_item.get(inv_id)
        metadata[inv_id] = {
            "organization_assignment_id": int(assignment.id) if assignment and assignment.id is not None else None,
            "organization_assigned_user_id": int(assignment.assigned_user_id) if assignment else None,
            "organization_assignment_status": assignment.assignment_status if assignment else None,
            "organization_queue_name": queue.queue_name if queue else None,
            "organization_queue_position": int(queue.queue_position) if queue else None,
        }
    return metadata
