"""P37-04 deterministic grading submission batch orchestration."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.models import (
    GradingCandidate,
    GradingSubmissionBatch,
    GradingSubmissionCostSnapshot,
    GradingSubmissionItem,
    GradingSubmissionLifecycleEvent,
    GradingSubmissionShipment,
    InventoryCopy,
)
from app.schemas.grading_submission import (
    GradingSubmissionBatchRead,
    GradingSubmissionCreatePayload,
    GradingSubmissionDashboardSummary,
    GradingSubmissionDetailRead,
    GradingSubmissionEventListResponse,
    GradingSubmissionItemRead,
    GradingSubmissionLifecycleEventRead,
    GradingSubmissionListResponse,
    GradingSubmissionPatchPayload,
    GradingSubmissionShipmentCreatePayload,
    GradingSubmissionShipmentListResponse,
    GradingSubmissionShipmentRead,
    InventoryGradingSubmissionBadge,
)
from app.services.grading_candidate_service import append_snapshot as append_candidate_snapshot
from app.services.grading_candidate_service import emit_lifecycle as emit_candidate_lifecycle
from app.services.grading_candidate_service import get_owner_candidate

MONEY_QUANT = Decimal("0.01")
ZERO = Decimal("0.00")
ACTIVE_BATCH_STATUSES = {"DRAFT", "READY", "SHIPPED", "RECEIVED_BY_GRADER", "GRADING", "RETURN_SHIPPED"}
TERMINAL_BATCH_STATUSES = {"COMPLETED", "CANCELLED"}

GRADER_FEE_SCHEDULE: dict[str, dict[str, Decimal | int]] = {
    "PSA": {
        "per_item_fee": Decimal("25.00"),
        "outbound_shipping": Decimal("18.00"),
        "return_shipping": Decimal("18.00"),
        "insurance_rate": Decimal("0.0125"),
        "insurance_floor": Decimal("5.00"),
        "turnaround_days": 75,
    },
    "CGC": {
        "per_item_fee": Decimal("30.00"),
        "outbound_shipping": Decimal("20.00"),
        "return_shipping": Decimal("20.00"),
        "insurance_rate": Decimal("0.0150"),
        "insurance_floor": Decimal("5.00"),
        "turnaround_days": 90,
    },
    "CBCS": {
        "per_item_fee": Decimal("28.00"),
        "outbound_shipping": Decimal("19.00"),
        "return_shipping": Decimal("19.00"),
        "insurance_rate": Decimal("0.0140"),
        "insurance_floor": Decimal("5.00"),
        "turnaround_days": 85,
    },
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _decimal(value: Any | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _money(value: Any | None) -> Decimal | None:
    dec = _decimal(value)
    if dec is None:
        return None
    return dec.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP), "f")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def deterministic_checksum(payload: dict[str, Any]) -> str:
    raw = json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def clamp_grading_submission_pagination(limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 500), max(offset, 0)


def _schedule(target_grader: str) -> dict[str, Decimal | int]:
    return GRADER_FEE_SCHEDULE.get(target_grader.upper(), GRADER_FEE_SCHEDULE["PSA"])


def _is_active_batch_status(status_value: str) -> bool:
    return status_value in ACTIVE_BATCH_STATUSES


def _batch_signature(
    *,
    owner_user_id: int,
    target_grader: str,
    batch_name: str,
    candidate_ids: list[int],
    submission_date: date | None,
    estimated_turnaround_days: int | None,
    notes: str | None,
) -> str:
    return deterministic_checksum(
        {
            "owner_user_id": owner_user_id,
            "target_grader": target_grader,
            "batch_name": batch_name,
            "candidate_ids": candidate_ids,
            "submission_date": submission_date,
            "estimated_turnaround_days": estimated_turnaround_days,
            "notes": notes,
        }
    )


def _candidate_batch_conflict(session: Session, candidate_id: int) -> GradingSubmissionBatch | None:
    row = session.exec(
        select(GradingSubmissionBatch)
        .join(GradingSubmissionItem, GradingSubmissionItem.grading_submission_batch_id == GradingSubmissionBatch.id)
        .where(GradingSubmissionItem.grading_candidate_id == candidate_id)
        .where(GradingSubmissionBatch.status.not_in(TERMINAL_BATCH_STATUSES))
        .order_by(col(GradingSubmissionBatch.created_at).desc(), col(GradingSubmissionBatch.id).desc())
    ).first()
    return row


def _batch_query(
    session: Session,
    *,
    owner_user_id: int | None = None,
    target_grader: str | None = None,
    status: str | None = None,
    submission_date_from: date | None = None,
    submission_date_to: date | None = None,
) -> Any:
    q = select(GradingSubmissionBatch)
    if owner_user_id is not None:
        q = q.where(GradingSubmissionBatch.owner_user_id == owner_user_id)
    if target_grader is not None:
        q = q.where(GradingSubmissionBatch.target_grader == target_grader)
    if status is not None:
        q = q.where(GradingSubmissionBatch.status == status)
    if submission_date_from is not None:
        q = q.where(GradingSubmissionBatch.submission_date >= submission_date_from)
    if submission_date_to is not None:
        q = q.where(GradingSubmissionBatch.submission_date <= submission_date_to)
    return q


def _batch_read(row: GradingSubmissionBatch) -> GradingSubmissionBatchRead:
    return GradingSubmissionBatchRead.model_validate(row, from_attributes=True)


def _item_read(row: GradingSubmissionItem) -> GradingSubmissionItemRead:
    return GradingSubmissionItemRead.model_validate(row, from_attributes=True)


def _shipment_read(row: GradingSubmissionShipment) -> GradingSubmissionShipmentRead:
    return GradingSubmissionShipmentRead.model_validate(row, from_attributes=True)


def _event_read(row: GradingSubmissionLifecycleEvent) -> GradingSubmissionLifecycleEventRead:
    return GradingSubmissionLifecycleEventRead.model_validate(row, from_attributes=True)


def _cost_read(row: GradingSubmissionCostSnapshot) -> Any:
    from app.schemas.grading_submission import GradingSubmissionCostSnapshotRead

    return GradingSubmissionCostSnapshotRead.model_validate(row, from_attributes=True)


def _detail_read(session: Session, batch: GradingSubmissionBatch) -> GradingSubmissionDetailRead:
    bid = int(batch.id or 0)
    items = session.exec(
        select(GradingSubmissionItem)
        .where(GradingSubmissionItem.grading_submission_batch_id == bid)
        .order_by(col(GradingSubmissionItem.id).asc())
    ).all()
    shipments = session.exec(
        select(GradingSubmissionShipment)
        .where(GradingSubmissionShipment.grading_submission_batch_id == bid)
        .order_by(col(GradingSubmissionShipment.created_at).asc(), col(GradingSubmissionShipment.id).asc())
    ).all()
    events = session.exec(
        select(GradingSubmissionLifecycleEvent)
        .where(GradingSubmissionLifecycleEvent.grading_submission_batch_id == bid)
        .order_by(col(GradingSubmissionLifecycleEvent.created_at).asc(), col(GradingSubmissionLifecycleEvent.id).asc())
    ).all()
    costs = session.exec(
        select(GradingSubmissionCostSnapshot)
        .where(GradingSubmissionCostSnapshot.grading_submission_batch_id == bid)
        .order_by(col(GradingSubmissionCostSnapshot.created_at).asc(), col(GradingSubmissionCostSnapshot.id).asc())
    ).all()
    return GradingSubmissionDetailRead(
        batch=_batch_read(batch),
        items=[_item_read(row) for row in items],
        shipments=[_shipment_read(row) for row in shipments],
        lifecycle_events=[_event_read(row) for row in events],
        cost_snapshots=[_cost_read(row) for row in costs],
    )


def _ensure_owner_batch(session: Session, *, owner_user_id: int, batch_id: int) -> GradingSubmissionBatch:
    batch = session.get(GradingSubmissionBatch, batch_id)
    if batch is None or batch.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="grading submission batch not found")
    return batch


def _ensure_ops_batch(session: Session, *, batch_id: int) -> GradingSubmissionBatch:
    batch = session.get(GradingSubmissionBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="grading submission batch not found")
    return batch


def _append_batch_event(
    session: Session,
    *,
    batch: GradingSubmissionBatch,
    event_type: str,
    prior_status: str | None,
    new_status: str | None,
    actor_user_id: int | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    session.add(
        GradingSubmissionLifecycleEvent(
            grading_submission_batch_id=int(batch.id or 0),
            event_type=event_type,
            prior_status=prior_status,
            new_status=new_status,
            metadata_json=_json_safe(metadata or {}),
            created_by_user_id=actor_user_id,
            created_at=utc_now(),
        )
    )


def _batch_cost_components(session: Session, batch: GradingSubmissionBatch) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    items = session.exec(
        select(GradingSubmissionItem).where(GradingSubmissionItem.grading_submission_batch_id == int(batch.id or 0))
    ).all()
    schedule = _schedule(batch.target_grader)
    grading_fees = ZERO
    declared_total = ZERO
    for item in items:
        fee = _money(item.submission_fee) or _money(schedule["per_item_fee"]) or ZERO
        grading_fees += fee
        declared_total += _money(item.declared_value) or ZERO
    shipping = _money(schedule["outbound_shipping"]) or ZERO
    if batch.status in {"RETURN_SHIPPED", "COMPLETED"}:
        shipping += _money(schedule["return_shipping"]) or ZERO
    insurance = max(
        _money(schedule["insurance_floor"]) or ZERO,
        _money(declared_total * (_decimal(schedule["insurance_rate"]) or ZERO)) or ZERO,
    )
    total = _money(grading_fees + shipping + insurance) or ZERO
    return _money(grading_fees) or ZERO, _money(shipping) or ZERO, _money(insurance) or ZERO, total


def _append_cost_snapshot(session: Session, batch: GradingSubmissionBatch, *, actuals_from_shipments: bool = False) -> GradingSubmissionCostSnapshot:
    estimated_grading_fees, estimated_shipping_cost, estimated_insurance_cost, estimated_total = _batch_cost_components(
        session, batch
    )
    shipments = session.exec(
        select(GradingSubmissionShipment).where(GradingSubmissionShipment.grading_submission_batch_id == int(batch.id or 0))
    ).all()
    actual_shipping = None
    actual_insurance = None
    if actuals_from_shipments:
        actual_shipping = _money(sum((_money(s.shipping_cost) or ZERO for s in shipments), ZERO))
        actual_insurance = _money(sum((_money(s.insured_amount) or ZERO for s in shipments), ZERO))
    checksum = deterministic_checksum(
        {
            "batch_id": int(batch.id or 0),
            "estimated_grading_fees": estimated_grading_fees,
            "estimated_shipping_cost": estimated_shipping_cost,
            "estimated_insurance_cost": estimated_insurance_cost,
            "actual_grading_fees": estimated_grading_fees if actuals_from_shipments else None,
            "actual_shipping_cost": actual_shipping,
            "actual_insurance_cost": actual_insurance,
        }
    )
    row = GradingSubmissionCostSnapshot(
        grading_submission_batch_id=int(batch.id or 0),
        estimated_grading_fees=estimated_grading_fees,
        estimated_shipping_cost=estimated_shipping_cost,
        estimated_insurance_cost=estimated_insurance_cost,
        actual_grading_fees=estimated_grading_fees if actuals_from_shipments else None,
        actual_shipping_cost=actual_shipping,
        actual_insurance_cost=actual_insurance,
        checksum=checksum,
        created_at=utc_now(),
    )
    session.add(row)
    batch.estimated_total_cost = estimated_total
    batch.actual_total_cost = _money((actual_shipping or ZERO) + (actual_insurance or ZERO) + (estimated_grading_fees if actuals_from_shipments else ZERO))
    session.add(batch)
    session.flush()
    return row


def _update_batch_runtime_fields(batch: GradingSubmissionBatch) -> None:
    now = utc_now()
    batch.updated_at = now
    if batch.submission_date and batch.completed_date:
        batch.actual_turnaround_days = max(0, (batch.completed_date - batch.submission_date).days)


def _set_item_status(
    session: Session,
    *,
    item: GradingSubmissionItem,
    status_value: str,
    actor_user_id: int | None,
    final_grade: str | None = None,
) -> None:
    before = _item_read(item)
    item.status = status_value
    if final_grade is not None:
        item.final_grade = final_grade
    item.updated_at = utc_now()
    session.add(item)
    session.flush()
    _append_batch_event(
        session,
        batch=session.get(GradingSubmissionBatch, item.grading_submission_batch_id) or GradingSubmissionBatch(),
        event_type="UPDATED",
        prior_status=before.status,
        new_status=status_value,
        actor_user_id=actor_user_id,
        metadata={"item_id": item.id, "grading_candidate_id": item.grading_candidate_id},
    )


def _transition_candidate_to_submitted(session: Session, *, owner_user_id: int, candidate: GradingCandidate) -> None:
    if candidate.status != "READY_FOR_SUBMISSION":
        raise HTTPException(status_code=409, detail="candidate must be READY_FOR_SUBMISSION")
    prev = str(candidate.status)
    now = utc_now()
    candidate.status = "SUBMITTED"
    candidate.submitted_at = now
    candidate.updated_at = now
    emit_candidate_lifecycle(
        session,
        grading_candidate_id=int(candidate.id or 0),
        event_type="SUBMITTED",
        from_status=prev,
        to_status="SUBMITTED",
        payload={"submission_batch_inclusion": True},
    )
    append_candidate_snapshot(session, candidate)


def _transition_candidate_to_graded(session: Session, *, candidate: GradingCandidate) -> None:
    if candidate.status != "SUBMITTED":
        return
    prev = str(candidate.status)
    now = utc_now()
    candidate.status = "GRADED"
    candidate.graded_at = now
    candidate.updated_at = now
    emit_candidate_lifecycle(
        session,
        grading_candidate_id=int(candidate.id or 0),
        event_type="GRADED",
        from_status=prev,
        to_status="GRADED",
        payload={"submission_batch_completed": True},
    )
    append_candidate_snapshot(session, candidate)


def _normalize_candidate_ids(candidate_ids: Iterable[int]) -> list[int]:
    cleaned = sorted({int(candidate_id) for candidate_id in candidate_ids if int(candidate_id) > 0})
    return cleaned


def _get_candidate_or_404(session: Session, *, owner_user_id: int, candidate_id: int) -> GradingCandidate:
    row = get_owner_candidate(session, owner_user_id=owner_user_id, candidate_id=candidate_id)
    return row


def _create_batch_internal(
    session: Session,
    *,
    owner_user_id: int,
    payload: GradingSubmissionCreatePayload,
) -> GradingSubmissionDetailRead:
    candidate_ids = _normalize_candidate_ids(payload.grading_candidate_ids)
    if not candidate_ids:
        raise HTTPException(status_code=422, detail="at least one grading candidate is required")
    signature = _batch_signature(
        owner_user_id=owner_user_id,
        target_grader=payload.target_grader.upper(),
        batch_name=payload.batch_name.strip(),
        candidate_ids=candidate_ids,
        submission_date=payload.submission_date,
        estimated_turnaround_days=payload.estimated_turnaround_days,
        notes=payload.notes,
    )
    existing = session.exec(
        select(GradingSubmissionBatch).where(
            GradingSubmissionBatch.owner_user_id == owner_user_id,
            GradingSubmissionBatch.checksum == signature,
        )
    ).first()
    if existing is not None:
        return _detail_read(session, existing)
    for candidate_id in candidate_ids:
        conflict = _candidate_batch_conflict(session, candidate_id)
        if conflict is not None:
            raise HTTPException(status_code=409, detail="candidate already belongs to an active submission batch")
    candidate_rows = [
        _get_candidate_or_404(session, owner_user_id=owner_user_id, candidate_id=candidate_id) for candidate_id in candidate_ids
    ]
    batch = GradingSubmissionBatch(
        owner_user_id=owner_user_id,
        target_grader=payload.target_grader.upper(),
        batch_name=payload.batch_name.strip(),
        status="DRAFT",
        submission_date=payload.submission_date,
        shipped_date=None,
        grader_received_date=None,
        grading_started_date=None,
        return_shipped_date=None,
        completed_date=None,
        estimated_turnaround_days=payload.estimated_turnaround_days or int(_schedule(payload.target_grader)["turnaround_days"]),
        actual_turnaround_days=None,
        estimated_total_cost=ZERO,
        actual_total_cost=None,
        item_count=len(candidate_rows),
        replay_key=payload.replay_key.strip() if payload.replay_key else None,
        checksum=signature,
        notes=payload.notes,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(batch)
    session.flush()
    for candidate in candidate_rows:
        inventory = session.get(InventoryCopy, candidate.inventory_item_id)
        if inventory is None:
            raise HTTPException(status_code=404, detail="inventory item not found")
        item_fee = _money(candidate.estimated_grading_cost) or _money(_schedule(payload.target_grader)["per_item_fee"]) or ZERO
        item = GradingSubmissionItem(
            grading_submission_batch_id=int(batch.id or 0),
            grading_candidate_id=int(candidate.id or 0),
            inventory_item_id=int(inventory.id or 0),
            declared_value=_money(candidate.estimated_raw_value) or _money(inventory.current_fmv),
            estimated_grade=candidate.target_grade,
            final_grade=None,
            submission_fee=item_fee,
            status="INCLUDED",
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(item)
        _transition_candidate_to_submitted(session, owner_user_id=owner_user_id, candidate=candidate)
    _append_batch_event(
        session,
        batch=batch,
        event_type="CREATED",
        prior_status=None,
        new_status="DRAFT",
        actor_user_id=owner_user_id,
        metadata={"candidate_ids": candidate_ids, "target_grader": batch.target_grader},
    )
    _append_cost_snapshot(session, batch)
    session.commit()
    session.refresh(batch)
    return _detail_read(session, batch)


def create_batch_owner(
    session: Session,
    *,
    owner_user_id: int,
    payload: GradingSubmissionCreatePayload,
) -> GradingSubmissionDetailRead:
    return _create_batch_internal(session, owner_user_id=owner_user_id, payload=payload)


def patch_batch_owner(
    session: Session,
    *,
    owner_user_id: int,
    batch_id: int,
    payload: GradingSubmissionPatchPayload,
) -> GradingSubmissionDetailRead:
    batch = _ensure_owner_batch(session, owner_user_id=owner_user_id, batch_id=batch_id)
    before = _batch_read(batch)
    if payload.batch_name is not None:
        batch.batch_name = payload.batch_name.strip()
    if payload.notes is not None:
        batch.notes = payload.notes
    if payload.estimated_turnaround_days is not None:
        batch.estimated_turnaround_days = payload.estimated_turnaround_days
    _update_batch_runtime_fields(batch)
    session.add(batch)
    _append_batch_event(
        session,
        batch=batch,
        event_type="UPDATED",
        prior_status=before.status,
        new_status=batch.status,
        actor_user_id=owner_user_id,
        metadata={"batch_name": batch.batch_name, "notes": batch.notes},
    )
    _append_cost_snapshot(session, batch)
    session.commit()
    session.refresh(batch)
    return _detail_read(session, batch)


def _transition_batch(
    session: Session,
    *,
    owner_user_id: int,
    batch_id: int,
    next_status: str,
    required_statuses: set[str],
    event_type: str,
    batch_field: str | None = None,
) -> GradingSubmissionDetailRead:
    batch = _ensure_owner_batch(session, owner_user_id=owner_user_id, batch_id=batch_id)
    if batch.status not in required_statuses:
        raise HTTPException(status_code=409, detail=f"batch must be in {sorted(required_statuses)[0]} state")
    prior = str(batch.status)
    now = utc_now()
    batch.status = next_status
    if next_status == "READY" and batch.submission_date is None:
        batch.submission_date = now.date()
    if next_status == "SHIPPED" and batch.shipped_date is None:
        batch.shipped_date = now.date()
    if next_status == "RECEIVED_BY_GRADER" and batch.grader_received_date is None:
        batch.grader_received_date = now.date()
    if next_status == "GRADING" and batch.grading_started_date is None:
        batch.grading_started_date = now.date()
    if next_status == "RETURN_SHIPPED" and batch.return_shipped_date is None:
        batch.return_shipped_date = now.date()
    if next_status == "COMPLETED" and batch.completed_date is None:
        return_shipment = session.exec(
            select(GradingSubmissionShipment)
            .where(GradingSubmissionShipment.grading_submission_batch_id == int(batch.id or 0))
            .where(GradingSubmissionShipment.shipment_direction == "RETURN")
            .order_by(
                col(GradingSubmissionShipment.delivered_date).desc(),
                col(GradingSubmissionShipment.created_at).desc(),
                col(GradingSubmissionShipment.id).desc(),
            )
        ).first()
        batch.completed_date = (
            return_shipment.delivered_date
            if return_shipment is not None and return_shipment.delivered_date is not None
            else now.date()
        )
        if batch.submission_date is not None:
            batch.actual_turnaround_days = max(0, (batch.completed_date - batch.submission_date).days)
        for item in session.exec(
            select(GradingSubmissionItem).where(GradingSubmissionItem.grading_submission_batch_id == int(batch.id or 0))
        ).all():
            item.status = "RETURNED"
            item.updated_at = now
            session.add(item)
            candidate = session.get(GradingCandidate, item.grading_candidate_id)
            if candidate is not None:
                _transition_candidate_to_graded(session, candidate=candidate)
    if next_status == "CANCELLED":
        for item in session.exec(
            select(GradingSubmissionItem).where(GradingSubmissionItem.grading_submission_batch_id == int(batch.id or 0))
        ).all():
            item.status = "CANCELLED"
            item.updated_at = now
            session.add(item)
    batch.updated_at = now
    session.add(batch)
    _append_batch_event(
        session,
        batch=batch,
        event_type=event_type,
        prior_status=prior,
        new_status=next_status,
        actor_user_id=owner_user_id,
        metadata={batch_field: getattr(batch, batch_field)} if batch_field else {},
    )
    _append_cost_snapshot(session, batch, actuals_from_shipments=batch.status in {"RETURN_SHIPPED", "COMPLETED"})
    session.commit()
    session.refresh(batch)
    return _detail_read(session, batch)


def mark_ready_owner(session: Session, *, owner_user_id: int, batch_id: int) -> GradingSubmissionDetailRead:
    return _transition_batch(
        session,
        owner_user_id=owner_user_id,
        batch_id=batch_id,
        next_status="READY",
        required_statuses={"DRAFT"},
        event_type="READY",
    )


def mark_shipped_owner(session: Session, *, owner_user_id: int, batch_id: int) -> GradingSubmissionDetailRead:
    return _transition_batch(
        session,
        owner_user_id=owner_user_id,
        batch_id=batch_id,
        next_status="SHIPPED",
        required_statuses={"READY"},
        event_type="SHIPPED",
        batch_field="shipped_date",
    )


def mark_received_owner(session: Session, *, owner_user_id: int, batch_id: int) -> GradingSubmissionDetailRead:
    return _transition_batch(
        session,
        owner_user_id=owner_user_id,
        batch_id=batch_id,
        next_status="RECEIVED_BY_GRADER",
        required_statuses={"SHIPPED"},
        event_type="RECEIVED_BY_GRADER",
        batch_field="grader_received_date",
    )


def mark_grading_owner(session: Session, *, owner_user_id: int, batch_id: int) -> GradingSubmissionDetailRead:
    return _transition_batch(
        session,
        owner_user_id=owner_user_id,
        batch_id=batch_id,
        next_status="GRADING",
        required_statuses={"RECEIVED_BY_GRADER"},
        event_type="GRADING_STARTED",
        batch_field="grading_started_date",
    )


def mark_return_shipped_owner(session: Session, *, owner_user_id: int, batch_id: int) -> GradingSubmissionDetailRead:
    return _transition_batch(
        session,
        owner_user_id=owner_user_id,
        batch_id=batch_id,
        next_status="RETURN_SHIPPED",
        required_statuses={"GRADING"},
        event_type="RETURN_SHIPPED",
        batch_field="return_shipped_date",
    )


def mark_complete_owner(session: Session, *, owner_user_id: int, batch_id: int) -> GradingSubmissionDetailRead:
    return _transition_batch(
        session,
        owner_user_id=owner_user_id,
        batch_id=batch_id,
        next_status="COMPLETED",
        required_statuses={"RETURN_SHIPPED"},
        event_type="COMPLETED",
        batch_field="completed_date",
    )


def mark_cancelled_owner(session: Session, *, owner_user_id: int, batch_id: int) -> GradingSubmissionDetailRead:
    return _transition_batch(
        session,
        owner_user_id=owner_user_id,
        batch_id=batch_id,
        next_status="CANCELLED",
        required_statuses=ACTIVE_BATCH_STATUSES,
        event_type="CANCELLED",
    )


def add_shipment_owner(
    session: Session,
    *,
    owner_user_id: int,
    batch_id: int,
    payload: GradingSubmissionShipmentCreatePayload,
) -> GradingSubmissionDetailRead:
    batch = _ensure_owner_batch(session, owner_user_id=owner_user_id, batch_id=batch_id)
    now = utc_now()
    shipment = GradingSubmissionShipment(
        grading_submission_batch_id=int(batch.id or 0),
        shipment_direction=payload.shipment_direction,
        carrier=payload.carrier,
        tracking_number=payload.tracking_number,
        shipped_date=payload.shipped_date,
        delivered_date=payload.delivered_date,
        insured_amount=_money(payload.insured_amount),
        shipping_cost=_money(payload.shipping_cost),
        notes=payload.notes,
        created_at=now,
    )
    session.add(shipment)
    session.flush()
    _append_batch_event(
        session,
        batch=batch,
        event_type="UPDATED",
        prior_status=batch.status,
        new_status=batch.status,
        actor_user_id=owner_user_id,
        metadata={"shipment_direction": payload.shipment_direction, "tracking_number": payload.tracking_number},
    )
    _append_cost_snapshot(session, batch, actuals_from_shipments=True)
    session.commit()
    session.refresh(batch)
    return _detail_read(session, batch)


def list_batches_owner(
    session: Session,
    *,
    owner_user_id: int,
    target_grader: str | None = None,
    status: str | None = None,
    submission_date_from: date | None = None,
    submission_date_to: date | None = None,
    limit: int,
    offset: int,
) -> tuple[list[GradingSubmissionBatch], int]:
    q = _batch_query(
        session,
        owner_user_id=owner_user_id,
        target_grader=target_grader,
        status=status,
        submission_date_from=submission_date_from,
        submission_date_to=submission_date_to,
    )
    total = int(session.exec(select(func.count()).select_from(q.subquery())).one() or 0)
    rows = session.exec(
        q.order_by(col(GradingSubmissionBatch.created_at).desc(), col(GradingSubmissionBatch.id).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return list(rows), total


def list_batches_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    target_grader: str | None = None,
    status: str | None = None,
    submission_date_from: date | None = None,
    submission_date_to: date | None = None,
    limit: int,
    offset: int,
) -> tuple[list[GradingSubmissionBatch], int]:
    q = _batch_query(
        session,
        owner_user_id=owner_user_id,
        target_grader=target_grader,
        status=status,
        submission_date_from=submission_date_from,
        submission_date_to=submission_date_to,
    )
    total = int(session.exec(select(func.count()).select_from(q.subquery())).one() or 0)
    rows = session.exec(
        q.order_by(col(GradingSubmissionBatch.created_at).desc(), col(GradingSubmissionBatch.id).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return list(rows), total


def get_batch_owner(session: Session, *, owner_user_id: int, batch_id: int) -> GradingSubmissionBatch:
    return _ensure_owner_batch(session, owner_user_id=owner_user_id, batch_id=batch_id)


def get_batch_ops(session: Session, *, batch_id: int) -> GradingSubmissionBatch:
    return _ensure_ops_batch(session, batch_id=batch_id)


def list_shipments_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    batch_id: int | None = None,
    limit: int,
    offset: int,
) -> tuple[list[GradingSubmissionShipment], int]:
    q = select(GradingSubmissionShipment).join(
        GradingSubmissionBatch,
        GradingSubmissionShipment.grading_submission_batch_id == GradingSubmissionBatch.id,
    )
    if owner_user_id is not None:
        q = q.where(GradingSubmissionBatch.owner_user_id == owner_user_id)
    if batch_id is not None:
        q = q.where(GradingSubmissionShipment.grading_submission_batch_id == batch_id)
    total = int(session.exec(select(func.count()).select_from(q.subquery())).one() or 0)
    rows = session.exec(
        q.order_by(col(GradingSubmissionShipment.created_at).desc(), col(GradingSubmissionShipment.id).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return list(rows), total


def list_events_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    batch_id: int | None = None,
    limit: int,
    offset: int,
) -> tuple[list[GradingSubmissionLifecycleEvent], int]:
    q = select(GradingSubmissionLifecycleEvent).join(
        GradingSubmissionBatch,
        GradingSubmissionLifecycleEvent.grading_submission_batch_id == GradingSubmissionBatch.id,
    )
    if owner_user_id is not None:
        q = q.where(GradingSubmissionBatch.owner_user_id == owner_user_id)
    if batch_id is not None:
        q = q.where(GradingSubmissionLifecycleEvent.grading_submission_batch_id == batch_id)
    total = int(session.exec(select(func.count()).select_from(q.subquery())).one() or 0)
    rows = session.exec(
        q.order_by(col(GradingSubmissionLifecycleEvent.created_at).asc(), col(GradingSubmissionLifecycleEvent.id).asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return list(rows), total


def dashboard_summary_owner(session: Session, *, owner_user_id: int) -> GradingSubmissionDashboardSummary:
    rows = session.exec(select(GradingSubmissionBatch).where(GradingSubmissionBatch.owner_user_id == owner_user_id)).all()
    active = sum(1 for row in rows if _is_active_batch_status(row.status))
    shipped = sum(1 for row in rows if row.status == "SHIPPED")
    grading = sum(1 for row in rows if row.status == "GRADING")
    completed = sum(1 for row in rows if row.status == "COMPLETED")
    turnaround_values = [Decimal(str(row.estimated_turnaround_days)) for row in rows if row.estimated_turnaround_days is not None]
    average = (
        _money(sum(turnaround_values, ZERO) / Decimal(len(turnaround_values))) if turnaround_values else None
    )
    return GradingSubmissionDashboardSummary(
        active_batch_count=active,
        shipped_batch_count=shipped,
        grading_batch_count=grading,
        completed_batch_count=completed,
        average_turnaround_days=average,
    )


def dashboard_summary_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
) -> GradingSubmissionDashboardSummary:
    rows = session.exec(select(GradingSubmissionBatch)).all()
    if owner_user_id is not None:
        rows = [row for row in rows if row.owner_user_id == owner_user_id]
    active = sum(1 for row in rows if _is_active_batch_status(row.status))
    shipped = sum(1 for row in rows if row.status == "SHIPPED")
    grading = sum(1 for row in rows if row.status == "GRADING")
    completed = sum(1 for row in rows if row.status == "COMPLETED")
    turnaround_values = [Decimal(str(row.estimated_turnaround_days)) for row in rows if row.estimated_turnaround_days is not None]
    average = (
        _money(sum(turnaround_values, ZERO) / Decimal(len(turnaround_values))) if turnaround_values else None
    )
    return GradingSubmissionDashboardSummary(
        active_batch_count=active,
        shipped_batch_count=shipped,
        grading_batch_count=grading,
        completed_batch_count=completed,
        average_turnaround_days=average,
    )


def batch_response_from_rows(
    *,
    rows: list[GradingSubmissionBatch],
    total: int,
    limit: int,
    offset: int,
) -> GradingSubmissionListResponse:
    return GradingSubmissionListResponse(items=[_batch_read(row) for row in rows], total_items=total, limit=limit, offset=offset)


def shipment_response_from_rows(
    *,
    rows: list[GradingSubmissionShipment],
    total: int,
    limit: int,
    offset: int,
) -> GradingSubmissionShipmentListResponse:
    return GradingSubmissionShipmentListResponse(
        items=[_shipment_read(row) for row in rows], total_items=total, limit=limit, offset=offset
    )


def event_response_from_rows(
    *,
    rows: list[GradingSubmissionLifecycleEvent],
    total: int,
    limit: int,
    offset: int,
) -> GradingSubmissionEventListResponse:
    return GradingSubmissionEventListResponse(
        items=[_event_read(row) for row in rows], total_items=total, limit=limit, offset=offset
    )


def inventory_grading_submission_badge(
    session: Session,
    *,
    owner_user_id: int,
    inventory_item_id: int,
) -> InventoryGradingSubmissionBadge | None:
    row = session.exec(
        select(GradingSubmissionBatch)
        .join(GradingSubmissionItem, GradingSubmissionItem.grading_submission_batch_id == GradingSubmissionBatch.id)
        .where(GradingSubmissionBatch.owner_user_id == owner_user_id)
        .where(GradingSubmissionItem.inventory_item_id == inventory_item_id)
        .order_by(col(GradingSubmissionBatch.created_at).desc(), col(GradingSubmissionBatch.id).desc())
    ).first()
    if row is None:
        return None
    shipment_state = session.exec(
        select(GradingSubmissionShipment.shipment_direction)
        .where(GradingSubmissionShipment.grading_submission_batch_id == int(row.id or 0))
        .order_by(col(GradingSubmissionShipment.created_at).desc(), col(GradingSubmissionShipment.id).desc())
    ).first()
    return InventoryGradingSubmissionBadge(
        grading_submission_batch_id=int(row.id or 0),
        status=row.status,
        target_grader=row.target_grader,
        batch_name=row.batch_name,
        shipment_state=shipment_state,
        item_count=row.item_count,
    )
