from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, func, select

from app.models import (
    OrganizationApprovalQueue,
    OrganizationReview,
    OrganizationReviewDecision,
    OrganizationReviewEvent,
)
from app.schemas.organization_reviews import (
    ORG_REVIEW_QUEUE_NAMES,
    OrganizationApprovalQueueListResponse,
    OrganizationApprovalQueueResponse,
    OrganizationReviewDecisionListResponse,
    OrganizationReviewDecisionResponse,
    OrganizationReviewListResponse,
    OrganizationReviewResponse,
)
from app.services.review_permissions import (
    MANAGE_PERMISSION,
    VIEW_PERMISSION,
    validate_review_access,
    validate_review_assignment,
    validate_review_queue_access,
    validate_review_visibility,
)

ENGINE_VERSION = "P42-05-v1"
REVIEW_STATUS_PENDING = "PENDING"
REVIEW_STATUS_ASSIGNED = "ASSIGNED"
REVIEW_STATUS_APPROVED = "APPROVED"
REVIEW_STATUS_REJECTED = "REJECTED"
REVIEW_STATUS_COMPLETED = "COMPLETED"
ACTIVE_QUEUE_STATUS = "ACTIVE"
DEFAULT_QUEUE_NAME = "intake_review"
DECISION_APPROVED = "APPROVED"
DECISION_REJECTED = "REJECTED"
TERMINAL_STATUSES = frozenset({REVIEW_STATUS_APPROVED, REVIEW_STATUS_REJECTED, REVIEW_STATUS_COMPLETED})


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


def append_review_event(
    session: Session,
    *,
    organization_id: int,
    organization_review_id: int | None,
    inventory_item_id: int | None,
    actor_user_id: int | None,
    event_type: str,
    event_payload_json: dict[str, Any] | None = None,
) -> OrganizationReviewEvent:
    row = OrganizationReviewEvent(
        organization_id=organization_id,
        organization_review_id=organization_review_id,
        inventory_item_id=inventory_item_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        event_payload_json=_stable_payload(event_payload_json or {}),
    )
    session.add(row)
    session.flush()
    return row


def _queue_for_review(
    session: Session,
    *,
    organization_id: int,
    review_id: int,
) -> OrganizationApprovalQueue | None:
    return session.exec(
        select(OrganizationApprovalQueue)
        .where(OrganizationApprovalQueue.organization_id == organization_id)
        .where(OrganizationApprovalQueue.review_id == review_id)
        .where(OrganizationApprovalQueue.queue_status == ACTIVE_QUEUE_STATUS)
    ).first()


def _to_review_response(session: Session, review: OrganizationReview) -> OrganizationReviewResponse:
    assert review.id is not None
    queue = _queue_for_review(session, organization_id=int(review.organization_id), review_id=int(review.id))
    return OrganizationReviewResponse(
        id=int(review.id),
        organization_id=int(review.organization_id),
        inventory_item_id=int(review.inventory_item_id),
        review_type=str(review.review_type),
        review_status=str(review.review_status),
        assigned_user_id=review.assigned_user_id,
        created_by_user_id=int(review.created_by_user_id),
        requested_at=review.requested_at,
        completed_at=review.completed_at,
        approval_queue_name=queue.queue_name if queue else None,
        approval_queue_position=int(queue.queue_position) if queue else None,
    )


def _to_decision_response(row: OrganizationReviewDecision) -> OrganizationReviewDecisionResponse:
    assert row.id is not None
    return OrganizationReviewDecisionResponse(
        id=int(row.id),
        organization_review_id=int(row.organization_review_id),
        actor_user_id=int(row.actor_user_id),
        decision_type=str(row.decision_type),
        decision_notes=row.decision_notes,
        created_at=row.created_at,
    )


def _to_queue_response(row: OrganizationApprovalQueue) -> OrganizationApprovalQueueResponse:
    assert row.id is not None
    return OrganizationApprovalQueueResponse(
        id=int(row.id),
        organization_id=int(row.organization_id),
        queue_name=str(row.queue_name),
        review_id=int(row.review_id),
        queue_position=int(row.queue_position),
        queue_status=str(row.queue_status),
        created_at=row.created_at,
    )


def _next_queue_position(
    session: Session,
    *,
    organization_id: int,
    queue_name: str,
    exclude_review_id: int | None = None,
) -> int:
    stmt = (
        select(func.max(OrganizationApprovalQueue.queue_position))
        .where(OrganizationApprovalQueue.organization_id == organization_id)
        .where(OrganizationApprovalQueue.queue_name == queue_name)
        .where(OrganizationApprovalQueue.queue_status == ACTIVE_QUEUE_STATUS)
    )
    if exclude_review_id is not None:
        stmt = stmt.where(OrganizationApprovalQueue.review_id != exclude_review_id)
    current_max = session.exec(stmt).one()
    if current_max is None:
        return 1
    return int(current_max) + 1


def _ensure_review_queue(
    session: Session,
    *,
    organization_id: int,
    review_id: int,
    inventory_item_id: int,
    queue_name: str,
    actor_user_id: int | None,
) -> OrganizationApprovalQueue:
    if queue_name not in ORG_REVIEW_QUEUE_NAMES:
        raise HTTPException(status_code=400, detail="Unsupported approval queue.")
    existing = session.exec(
        select(OrganizationApprovalQueue)
        .where(OrganizationApprovalQueue.organization_id == organization_id)
        .where(OrganizationApprovalQueue.review_id == review_id)
    ).first()
    if existing is not None:
        if existing.queue_name == queue_name and existing.queue_status == ACTIVE_QUEUE_STATUS:
            return existing
        previous_name = existing.queue_name
        previous_position = int(existing.queue_position)
        existing.queue_name = queue_name
        existing.queue_position = _next_queue_position(
            session,
            organization_id=organization_id,
            queue_name=queue_name,
            exclude_review_id=review_id,
        )
        existing.queue_status = ACTIVE_QUEUE_STATUS
        session.add(existing)
        session.flush()
        append_review_event(
            session,
            organization_id=organization_id,
            organization_review_id=review_id,
            inventory_item_id=inventory_item_id,
            actor_user_id=actor_user_id,
            event_type="queue_moved",
            event_payload_json={
                "queue_name": queue_name,
                "queue_position": int(existing.queue_position),
                "previous_queue_name": previous_name,
                "previous_queue_position": previous_position,
                "engine_version": ENGINE_VERSION,
            },
        )
        return existing
    position = _next_queue_position(session, organization_id=organization_id, queue_name=queue_name)
    row = OrganizationApprovalQueue(
        organization_id=organization_id,
        queue_name=queue_name,
        review_id=review_id,
        queue_position=position,
        queue_status=ACTIVE_QUEUE_STATUS,
    )
    session.add(row)
    session.flush()
    return row


def _require_mutable_review(review: OrganizationReview) -> None:
    if review.review_status in TERMINAL_STATUSES:
        raise HTTPException(status_code=409, detail="Review is already terminal.")


def create_review(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    inventory_item_id: int,
    review_type: str,
    assigned_user_id: int | None = None,
    queue_name: str | None = None,
) -> OrganizationReviewResponse:
    validate_review_access(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        inventory_item_id=inventory_item_id,
        action_key=MANAGE_PERMISSION,
    )
    status = REVIEW_STATUS_ASSIGNED if assigned_user_id is not None else REVIEW_STATUS_PENDING
    review = OrganizationReview(
        organization_id=organization_id,
        inventory_item_id=inventory_item_id,
        review_type=review_type.strip(),
        review_status=status,
        assigned_user_id=assigned_user_id,
        created_by_user_id=actor_user_id,
    )
    session.add(review)
    session.flush()
    assert review.id is not None
    target_queue = queue_name or DEFAULT_QUEUE_NAME
    _ensure_review_queue(
        session,
        organization_id=organization_id,
        review_id=int(review.id),
        inventory_item_id=inventory_item_id,
        queue_name=target_queue,
        actor_user_id=actor_user_id,
    )
    append_review_event(
        session,
        organization_id=organization_id,
        organization_review_id=int(review.id),
        inventory_item_id=inventory_item_id,
        actor_user_id=actor_user_id,
        event_type="review_created",
        event_payload_json={
            "review_id": int(review.id),
            "review_type": review.review_type,
            "review_status": review.review_status,
            "engine_version": ENGINE_VERSION,
        },
    )
    if assigned_user_id is not None:
        append_review_event(
            session,
            organization_id=organization_id,
            organization_review_id=int(review.id),
            inventory_item_id=inventory_item_id,
            actor_user_id=actor_user_id,
            event_type="review_assigned",
            event_payload_json={"assigned_user_id": assigned_user_id, "engine_version": ENGINE_VERSION},
        )
    session.commit()
    session.refresh(review)
    return _to_review_response(session, review)


def assign_review(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    organization_review_id: int,
    assigned_user_id: int,
) -> OrganizationReviewResponse:
    review = validate_review_assignment(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        organization_review_id=organization_review_id,
        assigned_user_id=assigned_user_id,
    )
    _require_mutable_review(review)
    review.assigned_user_id = assigned_user_id
    review.review_status = REVIEW_STATUS_ASSIGNED
    session.add(review)
    session.flush()
    append_review_event(
        session,
        organization_id=organization_id,
        organization_review_id=int(review.id or 0),
        inventory_item_id=int(review.inventory_item_id),
        actor_user_id=actor_user_id,
        event_type="review_assigned",
        event_payload_json={"assigned_user_id": assigned_user_id, "engine_version": ENGINE_VERSION},
    )
    session.commit()
    session.refresh(review)
    return _to_review_response(session, review)


def _append_decision(
    session: Session,
    *,
    review: OrganizationReview,
    actor_user_id: int,
    decision_type: str,
    decision_notes: str | None,
    event_type: str,
    next_status: str,
) -> OrganizationReviewResponse:
    _require_mutable_review(review)
    decision = OrganizationReviewDecision(
        organization_review_id=int(review.id or 0),
        actor_user_id=actor_user_id,
        decision_type=decision_type,
        decision_notes=decision_notes,
    )
    session.add(decision)
    review.review_status = next_status
    if next_status in {REVIEW_STATUS_APPROVED, REVIEW_STATUS_REJECTED, REVIEW_STATUS_COMPLETED}:
        review.completed_at = utc_now()
    session.add(review)
    session.flush()
    append_review_event(
        session,
        organization_id=int(review.organization_id),
        organization_review_id=int(review.id or 0),
        inventory_item_id=int(review.inventory_item_id),
        actor_user_id=actor_user_id,
        event_type=event_type,
        event_payload_json={
            "decision_id": int(decision.id or 0),
            "decision_type": decision_type,
            "engine_version": ENGINE_VERSION,
        },
    )
    from app.services.activity_feed_integration import record_review_activity

    notify_user_id = review.assigned_user_id if review.assigned_user_id != actor_user_id else None
    record_review_activity(
        session,
        organization_id=int(review.organization_id),
        actor_user_id=actor_user_id,
        event_kind=event_type.replace("review_", ""),
        payload={
            "title": "Review decision recorded",
            "body": f"Review #{review.id} is now {next_status.lower()}.",
            "organization_review_id": int(review.id or 0),
            "inventory_item_id": int(review.inventory_item_id),
            "decision_type": decision_type,
        },
        notify_user_id=notify_user_id,
    )
    from app.services.audit_ledger_integration import record_review_audit

    record_review_audit(
        session,
        organization_id=int(review.organization_id),
        actor_user_id=actor_user_id,
        audit_action=event_type,
        resource_type="organization_review",
        resource_id=int(review.id or 0),
        payload={
            "decision_id": int(decision.id or 0),
            "decision_type": decision_type,
            "inventory_item_id": int(review.inventory_item_id),
            "review_status": next_status,
        },
    )
    session.commit()
    session.refresh(review)
    return _to_review_response(session, review)


def approve_review(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    organization_review_id: int,
    decision_notes: str | None = None,
) -> OrganizationReviewResponse:
    review = validate_review_access(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        organization_review_id=organization_review_id,
        action_key=MANAGE_PERMISSION,
    )
    assert review is not None
    return _append_decision(
        session,
        review=review,
        actor_user_id=actor_user_id,
        decision_type=DECISION_APPROVED,
        decision_notes=decision_notes,
        event_type="review_approved",
        next_status=REVIEW_STATUS_APPROVED,
    )


def reject_review(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    organization_review_id: int,
    decision_notes: str | None = None,
) -> OrganizationReviewResponse:
    review = validate_review_access(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        organization_review_id=organization_review_id,
        action_key=MANAGE_PERMISSION,
    )
    assert review is not None
    return _append_decision(
        session,
        review=review,
        actor_user_id=actor_user_id,
        decision_type=DECISION_REJECTED,
        decision_notes=decision_notes,
        event_type="review_rejected",
        next_status=REVIEW_STATUS_REJECTED,
    )


def complete_review(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    organization_review_id: int,
) -> OrganizationReviewResponse:
    review = validate_review_access(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        organization_review_id=organization_review_id,
        action_key=MANAGE_PERMISSION,
    )
    assert review is not None
    _require_mutable_review(review)
    review.review_status = REVIEW_STATUS_COMPLETED
    review.completed_at = utc_now()
    session.add(review)
    session.flush()
    append_review_event(
        session,
        organization_id=int(review.organization_id),
        organization_review_id=int(review.id or 0),
        inventory_item_id=int(review.inventory_item_id),
        actor_user_id=actor_user_id,
        event_type="review_completed",
        event_payload_json={"engine_version": ENGINE_VERSION},
    )
    session.commit()
    session.refresh(review)
    return _to_review_response(session, review)


def move_review_queue(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    review_id: int,
    queue_name: str,
    queue_position: int | None = None,
) -> OrganizationApprovalQueueResponse:
    review = validate_review_queue_access(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        review_id=review_id,
    )
    _require_mutable_review(review)
    if queue_name not in ORG_REVIEW_QUEUE_NAMES:
        raise HTTPException(status_code=400, detail="Unsupported approval queue.")
    existing = session.exec(
        select(OrganizationApprovalQueue)
        .where(OrganizationApprovalQueue.organization_id == organization_id)
        .where(OrganizationApprovalQueue.review_id == review_id)
    ).first()
    if existing is None:
        position = queue_position or _next_queue_position(session, organization_id=organization_id, queue_name=queue_name)
        row = OrganizationApprovalQueue(
            organization_id=organization_id,
            queue_name=queue_name,
            review_id=review_id,
            queue_position=position,
            queue_status=ACTIVE_QUEUE_STATUS,
        )
        session.add(row)
        session.flush()
    else:
        previous_name = existing.queue_name
        previous_position = int(existing.queue_position)
        existing.queue_name = queue_name
        existing.queue_position = queue_position or _next_queue_position(
            session,
            organization_id=organization_id,
            queue_name=queue_name,
            exclude_review_id=review_id,
        )
        existing.queue_status = ACTIVE_QUEUE_STATUS
        session.add(existing)
        session.flush()
        row = existing
        append_review_event(
            session,
            organization_id=organization_id,
            organization_review_id=review_id,
            inventory_item_id=int(review.inventory_item_id),
            actor_user_id=actor_user_id,
            event_type="queue_moved",
            event_payload_json={
                "queue_name": queue_name,
                "queue_position": int(row.queue_position),
                "previous_queue_name": previous_name,
                "previous_queue_position": previous_position,
                "engine_version": ENGINE_VERSION,
            },
        )
    session.commit()
    session.refresh(row)
    return _to_queue_response(row)


def list_org_reviews(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int = 50,
    offset: int = 0,
    review_status: str | None = None,
) -> OrganizationReviewListResponse:
    validate_review_visibility(session, organization_id=organization_id, actor_user_id=actor_user_id)
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = (
        select(OrganizationReview)
        .where(OrganizationReview.organization_id == organization_id)
        .order_by(OrganizationReview.requested_at.desc(), OrganizationReview.id.desc())
    )
    if review_status:
        stmt = stmt.where(OrganizationReview.review_status == review_status)
    rows = session.exec(stmt.offset(offset).limit(limit)).all()
    count_stmt = (
        select(func.count())
        .select_from(OrganizationReview)
        .where(OrganizationReview.organization_id == organization_id)
    )
    if review_status:
        count_stmt = count_stmt.where(OrganizationReview.review_status == review_status)
    total = session.exec(count_stmt).one()
    return OrganizationReviewListResponse(
        items=[_to_review_response(session, row) for row in rows],
        total_items=int(total),
        limit=limit,
        offset=offset,
    )


def list_review_decisions(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    organization_review_id: int,
    limit: int = 50,
    offset: int = 0,
) -> OrganizationReviewDecisionListResponse:
    validate_review_access(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        organization_review_id=organization_review_id,
        action_key=VIEW_PERMISSION,
    )
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    rows = session.exec(
        select(OrganizationReviewDecision)
        .where(OrganizationReviewDecision.organization_review_id == organization_review_id)
        .order_by(OrganizationReviewDecision.created_at.asc(), OrganizationReviewDecision.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    total = session.exec(
        select(func.count())
        .select_from(OrganizationReviewDecision)
        .where(OrganizationReviewDecision.organization_review_id == organization_review_id)
    ).one()
    return OrganizationReviewDecisionListResponse(
        items=[_to_decision_response(row) for row in rows],
        total_items=int(total),
        limit=limit,
        offset=offset,
    )


def list_review_queues(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int = 100,
    offset: int = 0,
    queue_name: str | None = None,
) -> OrganizationApprovalQueueListResponse:
    validate_review_visibility(session, organization_id=organization_id, actor_user_id=actor_user_id)
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = (
        select(OrganizationApprovalQueue)
        .where(OrganizationApprovalQueue.organization_id == organization_id)
        .where(OrganizationApprovalQueue.queue_status == ACTIVE_QUEUE_STATUS)
        .order_by(
            OrganizationApprovalQueue.queue_name.asc(),
            OrganizationApprovalQueue.queue_position.asc(),
            OrganizationApprovalQueue.id.asc(),
        )
    )
    if queue_name:
        stmt = stmt.where(OrganizationApprovalQueue.queue_name == queue_name)
    rows = session.exec(stmt.offset(offset).limit(limit)).all()
    count_stmt = (
        select(func.count())
        .select_from(OrganizationApprovalQueue)
        .where(OrganizationApprovalQueue.organization_id == organization_id)
        .where(OrganizationApprovalQueue.queue_status == ACTIVE_QUEUE_STATUS)
    )
    if queue_name:
        count_stmt = count_stmt.where(OrganizationApprovalQueue.queue_name == queue_name)
    total = session.exec(count_stmt).one()
    return OrganizationApprovalQueueListResponse(
        items=[_to_queue_response(row) for row in rows],
        total_items=int(total),
        limit=limit,
        offset=offset,
    )


def review_metadata_for_inventory_ids(
    session: Session,
    *,
    organization_id: int,
    inventory_item_ids: tuple[int, ...],
) -> dict[int, dict[str, object]]:
    if not inventory_item_ids:
        return {}
    active_statuses = (REVIEW_STATUS_PENDING, REVIEW_STATUS_ASSIGNED)
    reviews = session.exec(
        select(OrganizationReview)
        .where(OrganizationReview.organization_id == organization_id)
        .where(OrganizationReview.inventory_item_id.in_(inventory_item_ids))
        .where(OrganizationReview.review_status.in_(active_statuses))
        .order_by(OrganizationReview.requested_at.desc(), OrganizationReview.id.desc())
    ).all()
    metadata: dict[int, dict[str, object]] = {}
    for review in reviews:
        inv_id = int(review.inventory_item_id)
        if inv_id in metadata:
            continue
        assert review.id is not None
        queue = _queue_for_review(session, organization_id=organization_id, review_id=int(review.id))
        metadata[inv_id] = {
            "organization_active_review_id": int(review.id),
            "organization_review_status": review.review_status,
            "organization_review_type": review.review_type,
            "organization_review_queue_name": queue.queue_name if queue else None,
        }
    return metadata
