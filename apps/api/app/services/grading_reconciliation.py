"""P37-05 deterministic grading reconciliation service."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.models import (
    ComicIssue,
    GraderPerformanceSnapshot,
    GradingCandidate,
    GradingReconciliationEvidence,
    GradingReconciliationHistory,
    GradingReconciliationRecord,
    GradingRoiSnapshot,
    GradingSpreadSnapshot,
    GradingSubmissionBatch,
    GradingSubmissionCostSnapshot,
    GradingSubmissionItem,
    InventoryCopy,
    InventoryFmvSnapshot,
    Listing,
    MarketFmvSnapshot,
    MarketSaleRecord,
    SaleRecord,
    Variant,
)
from app.schemas.grading_reconciliation import (
    GraderPerformanceSnapshotListResponse,
    GraderPerformanceSnapshotRead,
    GradingReconciliationDashboardSummary,
    GradingReconciliationDetailRead,
    GradingReconciliationEvidenceListResponse,
    GradingReconciliationEvidenceRead,
    GradingReconciliationHistoryListResponse,
    GradingReconciliationHistoryRead,
    GradingReconciliationListResponse,
    GradingReconciliationRead,
    GradingReconciliationReconcilePayload,
    InventoryGradingReconciliationBadge,
)

MONEY_QUANT = Decimal("0.01")
PCT_QUANT = Decimal("0.00000001")
GRADE_QUANT = Decimal("0.1")
ZERO = Decimal("0.00")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def clamp_grading_reconciliation_pagination(limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 500), max(offset, 0)


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


def _pct(value: Any | None) -> Decimal | None:
    dec = _decimal(value)
    if dec is None:
        return None
    return dec.quantize(PCT_QUANT, rounding=ROUND_HALF_UP)


def _grade_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value)).quantize(GRADE_QUANT, rounding=ROUND_HALF_UP)
    except Exception:
        return None


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        quant = value.quantize(PCT_QUANT if value.copy_abs() < Decimal("1000") else MONEY_QUANT)
        return format(quant, "f")
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


def _accuracy_status(expected_grade: str | None, final_grade: str | None) -> str:
    expected = _grade_decimal(expected_grade)
    actual = _grade_decimal(final_grade)
    if expected is None or actual is None:
        return "INSUFFICIENT_DATA"
    if actual > expected:
        return "ABOVE_EXPECTATION"
    if actual < expected:
        return "BELOW_EXPECTATION"
    return "MET_EXPECTATION"


def _confidence_level(
    *,
    payload_confidence: str | None,
    has_expected: bool,
    has_actual_grade: bool,
    has_realized_value: bool,
    evidence_count: int,
) -> str:
    if payload_confidence is not None:
        return payload_confidence
    if has_expected and has_actual_grade and has_realized_value and evidence_count >= 4:
        return "HIGH"
    if has_expected and has_actual_grade and evidence_count >= 2:
        return "MEDIUM"
    return "LOW"


def _record_read(row: GradingReconciliationRecord) -> GradingReconciliationRead:
    return GradingReconciliationRead.model_validate(row, from_attributes=True)


def _evidence_read(row: GradingReconciliationEvidence) -> GradingReconciliationEvidenceRead:
    return GradingReconciliationEvidenceRead.model_validate(row, from_attributes=True)


def _history_read(row: GradingReconciliationHistory) -> GradingReconciliationHistoryRead:
    return GradingReconciliationHistoryRead.model_validate(row, from_attributes=True)


def _performance_read(row: GraderPerformanceSnapshot) -> GraderPerformanceSnapshotRead:
    return GraderPerformanceSnapshotRead.model_validate(row, from_attributes=True)


def _detail_read(session: Session, row: GradingReconciliationRecord) -> GradingReconciliationDetailRead:
    rid = int(row.id or 0)
    evidence = session.exec(
        select(GradingReconciliationEvidence)
        .where(GradingReconciliationEvidence.grading_reconciliation_record_id == rid)
        .order_by(col(GradingReconciliationEvidence.created_at).asc(), col(GradingReconciliationEvidence.id).asc())
    ).all()
    history = session.exec(
        select(GradingReconciliationHistory)
        .where(GradingReconciliationHistory.grading_candidate_id == row.grading_candidate_id)
        .order_by(col(GradingReconciliationHistory.snapshot_date).desc(), col(GradingReconciliationHistory.id).desc())
    ).all()
    return GradingReconciliationDetailRead(
        record=_record_read(row),
        evidence=[_evidence_read(item) for item in evidence],
        history=[_history_read(item) for item in history],
    )


def _ensure_owner_record(session: Session, *, owner_user_id: int, record_id: int) -> GradingReconciliationRecord:
    row = session.get(GradingReconciliationRecord, record_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="grading reconciliation record not found")
    return row


def _ensure_ops_record(session: Session, *, record_id: int) -> GradingReconciliationRecord:
    row = session.get(GradingReconciliationRecord, record_id)
    if row is None:
        raise HTTPException(status_code=404, detail="grading reconciliation record not found")
    return row


def _submission_context(
    session: Session,
    *,
    owner_user_id: int,
    grading_submission_item_id: int,
) -> tuple[GradingSubmissionItem, GradingSubmissionBatch, GradingCandidate, InventoryCopy, int]:
    item = session.get(GradingSubmissionItem, grading_submission_item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="grading submission item not found")
    batch = session.get(GradingSubmissionBatch, item.grading_submission_batch_id)
    if batch is None or batch.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="grading submission batch not found")
    candidate = session.get(GradingCandidate, item.grading_candidate_id)
    if candidate is None or candidate.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="grading candidate not found")
    inventory = session.get(InventoryCopy, item.inventory_item_id)
    if inventory is None or inventory.user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="inventory item not found")
    issue_id = int(
        session.exec(
            select(Variant.comic_issue_id)
            .join(ComicIssue, Variant.comic_issue_id == ComicIssue.id)
            .where(Variant.id == inventory.variant_id)
        ).one()
    )
    return item, batch, candidate, inventory, issue_id


def _latest_cost_snapshot(session: Session, batch_id: int) -> GradingSubmissionCostSnapshot | None:
    return session.exec(
        select(GradingSubmissionCostSnapshot)
        .where(GradingSubmissionCostSnapshot.grading_submission_batch_id == batch_id)
        .order_by(col(GradingSubmissionCostSnapshot.created_at).desc(), col(GradingSubmissionCostSnapshot.id).desc())
    ).first()


def _latest_roi_snapshot(
    session: Session,
    *,
    owner_user_id: int,
    grading_candidate_id: int,
    inventory_item_id: int,
    target_grader: str,
    target_grade: str | None,
) -> GradingRoiSnapshot | None:
    stmt = (
        select(GradingRoiSnapshot)
        .where(GradingRoiSnapshot.owner_user_id == owner_user_id)
        .where(GradingRoiSnapshot.grading_candidate_id == grading_candidate_id)
        .where(GradingRoiSnapshot.inventory_item_id == inventory_item_id)
        .where(GradingRoiSnapshot.target_grader == target_grader)
    )
    if target_grade is not None:
        stmt = stmt.where(GradingRoiSnapshot.target_grade == target_grade)
    return session.exec(
        stmt.order_by(col(GradingRoiSnapshot.snapshot_date).desc(), col(GradingRoiSnapshot.id).desc())
    ).first()


def _latest_spread_snapshot(
    session: Session,
    *,
    owner_user_id: int,
    inventory_item_id: int,
    target_grader: str,
    target_grade: str | None,
) -> GradingSpreadSnapshot | None:
    stmt = (
        select(GradingSpreadSnapshot)
        .where(GradingSpreadSnapshot.owner_user_id == owner_user_id)
        .where(GradingSpreadSnapshot.inventory_item_id == inventory_item_id)
        .where(GradingSpreadSnapshot.target_grader == target_grader)
    )
    if target_grade is not None:
        stmt = stmt.where(GradingSpreadSnapshot.target_grade == target_grade)
    return session.exec(
        stmt.order_by(col(GradingSpreadSnapshot.snapshot_date).desc(), col(GradingSpreadSnapshot.id).desc())
    ).first()


def _latest_graded_market_fmv(
    session: Session,
    *,
    canonical_comic_issue_id: int,
    grader: str,
    final_grade: str,
) -> MarketFmvSnapshot | None:
    return session.exec(
        select(MarketFmvSnapshot)
        .where(MarketFmvSnapshot.canonical_issue_id == canonical_comic_issue_id)
        .where(MarketFmvSnapshot.grading_company == grader)
        .where(MarketFmvSnapshot.normalized_grade == final_grade)
        .order_by(col(MarketFmvSnapshot.snapshot_date).desc(), col(MarketFmvSnapshot.id).desc())
    ).first()


def _latest_inventory_fmv(session: Session, inventory_item_id: int) -> Decimal | None:
    row = session.exec(
        select(InventoryFmvSnapshot)
        .where(InventoryFmvSnapshot.inventory_copy_id == inventory_item_id)
        .order_by(col(InventoryFmvSnapshot.changed_at).desc(), col(InventoryFmvSnapshot.id).desc())
    ).first()
    if row is not None:
        return _money(row.new_fmv)
    inventory = session.get(InventoryCopy, inventory_item_id)
    return _money(inventory.current_fmv) if inventory is not None else None


def _latest_sale(session: Session, inventory_item_id: int) -> SaleRecord | None:
    return session.exec(
        select(SaleRecord)
        .join(Listing, SaleRecord.listing_id == Listing.id)
        .where(Listing.inventory_copy_id == inventory_item_id)
        .order_by(col(SaleRecord.sale_date).desc(), col(SaleRecord.id).desc())
    ).first()


def _latest_market_sale(session: Session, inventory_item_id: int) -> MarketSaleRecord | None:
    return session.exec(
        select(MarketSaleRecord)
        .join(Listing, MarketSaleRecord.source_listing_id == Listing.id)
        .where(Listing.inventory_copy_id == inventory_item_id)
        .order_by(col(MarketSaleRecord.sale_date).desc().nullslast(), col(MarketSaleRecord.id).desc())
    ).first()


def _item_cost_amount(
    session: Session,
    *,
    item: GradingSubmissionItem,
    batch: GradingSubmissionBatch,
) -> Decimal | None:
    item_count = max(1, int(batch.item_count))
    cost = _money(item.submission_fee) or ZERO
    snapshot = _latest_cost_snapshot(session, int(batch.id or 0))
    if snapshot is not None:
        shipping = snapshot.actual_shipping_cost if snapshot.actual_shipping_cost is not None else snapshot.estimated_shipping_cost
        insurance = snapshot.actual_insurance_cost if snapshot.actual_insurance_cost is not None else snapshot.estimated_insurance_cost
        cost += (_money(shipping) or ZERO) / Decimal(item_count)
        cost += (_money(insurance) or ZERO) / Decimal(item_count)
        return _money(cost)
    batch_total = batch.actual_total_cost if batch.actual_total_cost is not None else batch.estimated_total_cost
    if batch_total is not None:
        return _money((_money(batch_total) or ZERO) / Decimal(item_count))
    return _money(cost)


def _derive_roi(
    *,
    raw_value: Decimal | None,
    graded_value: Decimal | None,
    cost_amount: Decimal | None,
) -> Decimal | None:
    if raw_value is None or graded_value is None or cost_amount is None or cost_amount <= ZERO:
        return None
    net = graded_value - raw_value - cost_amount
    return _pct(net / cost_amount)


def _append_history(
    session: Session,
    *,
    owner_user_id: int,
    candidate_id: int,
    inventory_item_id: int,
    target_grader: str,
    expected_grade: str | None,
    final_grade: str | None,
    realized_roi: Decimal | None,
    roi_delta: Decimal | None,
    snapshot_date: date,
) -> None:
    checksum = deterministic_checksum(
        {
            "owner_user_id": owner_user_id,
            "grading_candidate_id": candidate_id,
            "inventory_item_id": inventory_item_id,
            "target_grader": target_grader,
            "expected_grade": expected_grade,
            "actual_grade": final_grade,
            "realized_roi": realized_roi,
            "roi_delta": roi_delta,
            "snapshot_date": snapshot_date,
        }
    )
    existing = session.exec(
        select(GradingReconciliationHistory)
        .where(GradingReconciliationHistory.owner_user_id == owner_user_id)
        .where(GradingReconciliationHistory.grading_candidate_id == candidate_id)
        .where(GradingReconciliationHistory.inventory_item_id == inventory_item_id)
        .where(GradingReconciliationHistory.target_grader == target_grader)
        .where(GradingReconciliationHistory.snapshot_date == snapshot_date)
        .where(GradingReconciliationHistory.checksum == checksum)
    ).first()
    if existing is not None:
        return
    session.add(
        GradingReconciliationHistory(
            owner_user_id=owner_user_id,
            grading_candidate_id=candidate_id,
            inventory_item_id=inventory_item_id,
            target_grader=target_grader,
            expected_grade=expected_grade,
            actual_grade=final_grade,
            realized_roi=realized_roi,
            roi_delta=roi_delta,
            snapshot_date=snapshot_date,
            checksum=checksum,
            created_at=utc_now(),
        )
    )


def _append_grader_performance_snapshot(
    session: Session,
    *,
    owner_user_id: int | None,
    grader: str,
    snapshot_date: date,
) -> None:
    stmt = select(GradingReconciliationRecord).where(GradingReconciliationRecord.target_grader == grader).where(
        GradingReconciliationRecord.reconciliation_status == "RECONCILED"
    )
    if owner_user_id is not None:
        stmt = stmt.where(GradingReconciliationRecord.owner_user_id == owner_user_id)
    rows = session.exec(stmt).all()
    submission_count = len(rows)
    above = sum(1 for row in rows if row.grading_accuracy_status == "ABOVE_EXPECTATION")
    met = sum(1 for row in rows if row.grading_accuracy_status == "MET_EXPECTATION")
    below = sum(1 for row in rows if row.grading_accuracy_status == "BELOW_EXPECTATION")
    roi_values = [row.roi_delta for row in rows if row.roi_delta is not None]
    turnaround_values: list[Decimal] = []
    for row in rows:
        item = session.get(GradingSubmissionItem, row.grading_submission_item_id)
        if item is None:
            continue
        batch = session.get(GradingSubmissionBatch, item.grading_submission_batch_id)
        if batch is None or batch.actual_turnaround_days is None:
            continue
        turnaround_values.append(Decimal(str(batch.actual_turnaround_days)))
    average_roi_delta = _pct(sum(roi_values, Decimal("0")) / Decimal(len(roi_values))) if roi_values else None
    average_turnaround = _money(sum(turnaround_values, Decimal("0")) / Decimal(len(turnaround_values))) if turnaround_values else None
    checksum = deterministic_checksum(
        {
            "owner_user_id": owner_user_id,
            "grader": grader,
            "submission_count": submission_count,
            "above_expectation_count": above,
            "met_expectation_count": met,
            "below_expectation_count": below,
            "average_roi_delta": average_roi_delta,
            "average_turnaround_days": average_turnaround,
            "snapshot_date": snapshot_date,
        }
    )
    existing = session.exec(
        select(GraderPerformanceSnapshot)
        .where(GraderPerformanceSnapshot.owner_user_id == owner_user_id)
        .where(GraderPerformanceSnapshot.grader == grader)
        .where(GraderPerformanceSnapshot.snapshot_date == snapshot_date)
        .where(GraderPerformanceSnapshot.checksum == checksum)
    ).first()
    if existing is not None:
        return
    session.add(
        GraderPerformanceSnapshot(
            owner_user_id=owner_user_id,
            grader=grader,
            submission_count=submission_count,
            above_expectation_count=above,
            met_expectation_count=met,
            below_expectation_count=below,
            average_roi_delta=average_roi_delta,
            average_turnaround_days=average_turnaround,
            checksum=checksum,
            snapshot_date=snapshot_date,
            created_at=utc_now(),
        )
    )


def reconcile_grading_result(
    session: Session,
    *,
    owner_user_id: int,
    payload: GradingReconciliationReconcilePayload,
) -> GradingReconciliationDetailRead:
    item, batch, candidate, inventory, issue_id = _submission_context(
        session,
        owner_user_id=owner_user_id,
        grading_submission_item_id=payload.grading_submission_item_id,
    )
    if batch.status not in {"RETURN_SHIPPED", "COMPLETED"}:
        raise HTTPException(status_code=409, detail="submission batch must be returned or completed before reconciliation")
    reconciled_at = payload.reconciled_at or utc_now()
    expected_grade = item.estimated_grade or candidate.target_grade
    expected_raw_value = _money(candidate.estimated_raw_value) or _money(item.declared_value) or _latest_inventory_fmv(
        session, int(inventory.id or 0)
    )
    expected_graded_value = _money(candidate.estimated_graded_value)
    cost_amount = _item_cost_amount(session, item=item, batch=batch)
    roi_snapshot = _latest_roi_snapshot(
        session,
        owner_user_id=owner_user_id,
        grading_candidate_id=int(candidate.id or 0),
        inventory_item_id=int(inventory.id or 0),
        target_grader=batch.target_grader,
        target_grade=expected_grade,
    )
    spread_snapshot = _latest_spread_snapshot(
        session,
        owner_user_id=owner_user_id,
        inventory_item_id=int(inventory.id or 0),
        target_grader=batch.target_grader,
        target_grade=expected_grade,
    )
    market_fmv_snapshot = _latest_graded_market_fmv(
        session,
        canonical_comic_issue_id=issue_id,
        grader=batch.target_grader,
        final_grade=payload.final_grade,
    )
    realized_graded_value = _money(payload.realized_graded_value) or (
        _money(market_fmv_snapshot.estimated_fmv) if market_fmv_snapshot is not None else None
    )
    expected_roi = _pct(roi_snapshot.estimated_roi_pct) if roi_snapshot is not None else _pct(candidate.estimated_roi)
    if expected_roi is None:
        expected_roi = _derive_roi(
            raw_value=expected_raw_value,
            graded_value=expected_graded_value,
            cost_amount=cost_amount,
        )
    realized_roi = _derive_roi(
        raw_value=expected_raw_value,
        graded_value=realized_graded_value,
        cost_amount=cost_amount,
    )
    roi_delta = _pct(realized_roi - expected_roi) if realized_roi is not None and expected_roi is not None else None
    accuracy_status = _accuracy_status(expected_grade, payload.final_grade)
    sale_record = _latest_sale(session, int(inventory.id or 0))
    market_sale = _latest_market_sale(session, int(inventory.id or 0))

    checksum = deterministic_checksum(
        {
            "owner_user_id": owner_user_id,
            "grading_submission_item_id": item.id,
            "grading_candidate_id": candidate.id,
            "inventory_item_id": inventory.id,
            "target_grader": batch.target_grader,
            "expected_grade": expected_grade,
            "final_grade": payload.final_grade,
            "expected_raw_value": expected_raw_value,
            "expected_graded_value": expected_graded_value,
            "realized_graded_value": realized_graded_value,
            "expected_roi": expected_roi,
            "realized_roi": realized_roi,
            "roi_delta": roi_delta,
            "snapshot_date": reconciled_at.date(),
        }
    )
    existing = session.exec(
        select(GradingReconciliationRecord)
        .where(GradingReconciliationRecord.grading_submission_item_id == int(item.id or 0))
        .where(GradingReconciliationRecord.checksum == checksum)
    ).first()
    if existing is not None:
        return _detail_read(session, existing)

    evidence_count = 1
    if roi_snapshot is not None:
        evidence_count += 1
    if spread_snapshot is not None:
        evidence_count += 1
    if market_fmv_snapshot is not None or payload.realized_graded_value is not None:
        evidence_count += 1
    if sale_record is not None:
        evidence_count += 1
    if market_sale is not None:
        evidence_count += 1

    record = GradingReconciliationRecord(
        owner_user_id=owner_user_id,
        grading_submission_item_id=int(item.id or 0),
        grading_candidate_id=int(candidate.id or 0),
        inventory_item_id=int(inventory.id or 0),
        target_grader=batch.target_grader,
        expected_grade=expected_grade,
        final_grade=payload.final_grade,
        expected_raw_value=expected_raw_value,
        expected_graded_value=expected_graded_value,
        realized_graded_value=realized_graded_value,
        expected_roi=expected_roi,
        realized_roi=realized_roi,
        roi_delta=roi_delta,
        grading_accuracy_status=accuracy_status,
        reconciliation_status="RECONCILED",
        confidence_level=_confidence_level(
            payload_confidence=payload.confidence_level,
            has_expected=expected_grade is not None and expected_raw_value is not None,
            has_actual_grade=payload.final_grade is not None,
            has_realized_value=realized_graded_value is not None,
            evidence_count=evidence_count,
        ),
        checksum=checksum,
        reconciled_at=reconciled_at,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(record)
    session.flush()

    item.final_grade = payload.final_grade
    item.updated_at = utc_now()
    session.add(item)

    evidence_rows: list[GradingReconciliationEvidence] = [
        GradingReconciliationEvidence(
            grading_reconciliation_record_id=int(record.id or 0),
            evidence_type="SUBMISSION_BATCH",
            source_id=int(batch.id or 0),
            source_table="grading_submission_batch",
            evidence_value_json=_json_safe(
                {
                    "batch_status": batch.status,
                    "batch_checksum": batch.checksum,
                    "item_status": item.status,
                    "declared_value": item.declared_value,
                    "submission_fee": item.submission_fee,
                    "cost_share_amount": cost_amount,
                    "actual_turnaround_days": batch.actual_turnaround_days,
                }
            ),
            created_at=utc_now(),
        )
    ]
    if roi_snapshot is not None:
        evidence_rows.append(
            GradingReconciliationEvidence(
                grading_reconciliation_record_id=int(record.id or 0),
                evidence_type="ROI_ENGINE",
                source_id=int(roi_snapshot.id or 0),
                source_table="grading_roi_snapshot",
                evidence_value_json=_json_safe(
                    {
                        "target_grade": roi_snapshot.target_grade,
                        "estimated_roi_pct": roi_snapshot.estimated_roi_pct,
                        "estimated_total_cost": roi_snapshot.estimated_total_cost,
                        "checksum": roi_snapshot.checksum,
                    }
                ),
                created_at=utc_now(),
            )
        )
    if spread_snapshot is not None:
        evidence_rows.append(
            GradingReconciliationEvidence(
                grading_reconciliation_record_id=int(record.id or 0),
                evidence_type="SPREAD_ENGINE",
                source_id=int(spread_snapshot.id or 0),
                source_table="grading_spread_snapshot",
                evidence_value_json=_json_safe(
                    {
                        "target_grade": spread_snapshot.target_grade,
                        "estimated_net_upside": spread_snapshot.estimated_net_upside,
                        "checksum": spread_snapshot.checksum,
                    }
                ),
                created_at=utc_now(),
            )
        )
    if payload.realized_graded_value is not None:
        evidence_rows.append(
            GradingReconciliationEvidence(
                grading_reconciliation_record_id=int(record.id or 0),
                evidence_type="MANUAL_ENTRY",
                source_id=None,
                source_table=None,
                evidence_value_json=_json_safe(
                    {
                        "realized_graded_value": payload.realized_graded_value,
                        "final_grade": payload.final_grade,
                    }
                ),
                created_at=utc_now(),
            )
        )
    elif market_fmv_snapshot is not None:
        evidence_rows.append(
            GradingReconciliationEvidence(
                grading_reconciliation_record_id=int(record.id or 0),
                evidence_type="FMV",
                source_id=int(market_fmv_snapshot.id or 0),
                source_table="market_fmv_snapshot",
                evidence_value_json=_json_safe(
                    {
                        "normalized_grade": market_fmv_snapshot.normalized_grade,
                        "estimated_fmv": market_fmv_snapshot.estimated_fmv,
                        "snapshot_date": market_fmv_snapshot.snapshot_date,
                    }
                ),
                created_at=utc_now(),
            )
        )
    if sale_record is not None:
        evidence_rows.append(
            GradingReconciliationEvidence(
                grading_reconciliation_record_id=int(record.id or 0),
                evidence_type="SALES_LEDGER",
                source_id=int(sale_record.id or 0),
                source_table="sale_record",
                evidence_value_json=_json_safe(
                    {
                        "gross_sale_amount": sale_record.gross_sale_amount,
                        "net_proceeds_amount": sale_record.net_proceeds_amount,
                        "sale_date": sale_record.sale_date,
                    }
                ),
                created_at=utc_now(),
            )
        )
    if market_sale is not None:
        evidence_rows.append(
            GradingReconciliationEvidence(
                grading_reconciliation_record_id=int(record.id or 0),
                evidence_type="MARKET_SALE",
                source_id=int(market_sale.id or 0),
                source_table="market_sale_record",
                evidence_value_json=_json_safe(
                    {
                        "sale_price": market_sale.sale_price,
                        "sale_date": market_sale.sale_date,
                        "normalized_grade": market_sale.normalized_grade,
                    }
                ),
                created_at=utc_now(),
            )
        )
    for evidence in evidence_rows:
        session.add(evidence)

    _append_history(
        session,
        owner_user_id=owner_user_id,
        candidate_id=int(candidate.id or 0),
        inventory_item_id=int(inventory.id or 0),
        target_grader=batch.target_grader,
        expected_grade=expected_grade,
        final_grade=payload.final_grade,
        realized_roi=realized_roi,
        roi_delta=roi_delta,
        snapshot_date=reconciled_at.date(),
    )
    _append_grader_performance_snapshot(
        session,
        owner_user_id=owner_user_id,
        grader=batch.target_grader,
        snapshot_date=reconciled_at.date(),
    )
    _append_grader_performance_snapshot(
        session,
        owner_user_id=None,
        grader=batch.target_grader,
        snapshot_date=reconciled_at.date(),
    )
    session.commit()
    session.refresh(record)
    return _detail_read(session, record)


def _records_query(
    *,
    owner_user_id: int | None = None,
    grading_candidate_id: int | None = None,
    inventory_item_id: int | None = None,
    target_grader: str | None = None,
    reconciliation_status: str | None = None,
    grading_accuracy_status: str | None = None,
    confidence_level: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
):
    stmt = select(GradingReconciliationRecord)
    if owner_user_id is not None:
        stmt = stmt.where(GradingReconciliationRecord.owner_user_id == owner_user_id)
    if grading_candidate_id is not None:
        stmt = stmt.where(GradingReconciliationRecord.grading_candidate_id == grading_candidate_id)
    if inventory_item_id is not None:
        stmt = stmt.where(GradingReconciliationRecord.inventory_item_id == inventory_item_id)
    if target_grader is not None:
        stmt = stmt.where(GradingReconciliationRecord.target_grader == target_grader)
    if reconciliation_status is not None:
        stmt = stmt.where(GradingReconciliationRecord.reconciliation_status == reconciliation_status)
    if grading_accuracy_status is not None:
        stmt = stmt.where(GradingReconciliationRecord.grading_accuracy_status == grading_accuracy_status)
    if confidence_level is not None:
        stmt = stmt.where(GradingReconciliationRecord.confidence_level == confidence_level)
    if date_from is not None:
        stmt = stmt.where(func.date(GradingReconciliationRecord.created_at) >= date_from)
    if date_to is not None:
        stmt = stmt.where(func.date(GradingReconciliationRecord.created_at) <= date_to)
    return stmt


def _evidence_query(
    *,
    owner_user_id: int | None = None,
    record_id: int | None = None,
):
    stmt = select(GradingReconciliationEvidence).join(
        GradingReconciliationRecord,
        GradingReconciliationEvidence.grading_reconciliation_record_id == GradingReconciliationRecord.id,
    )
    if owner_user_id is not None:
        stmt = stmt.where(GradingReconciliationRecord.owner_user_id == owner_user_id)
    if record_id is not None:
        stmt = stmt.where(GradingReconciliationEvidence.grading_reconciliation_record_id == record_id)
    return stmt


def _history_query(
    *,
    owner_user_id: int | None = None,
    grading_candidate_id: int | None = None,
    inventory_item_id: int | None = None,
    target_grader: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
):
    stmt = select(GradingReconciliationHistory)
    if owner_user_id is not None:
        stmt = stmt.where(GradingReconciliationHistory.owner_user_id == owner_user_id)
    if grading_candidate_id is not None:
        stmt = stmt.where(GradingReconciliationHistory.grading_candidate_id == grading_candidate_id)
    if inventory_item_id is not None:
        stmt = stmt.where(GradingReconciliationHistory.inventory_item_id == inventory_item_id)
    if target_grader is not None:
        stmt = stmt.where(GradingReconciliationHistory.target_grader == target_grader)
    if date_from is not None:
        stmt = stmt.where(GradingReconciliationHistory.snapshot_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(GradingReconciliationHistory.snapshot_date <= date_to)
    return stmt


def _performance_query(
    *,
    owner_user_id: int | None = None,
    grader: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
):
    stmt = select(GraderPerformanceSnapshot)
    if owner_user_id is not None:
        stmt = stmt.where(GraderPerformanceSnapshot.owner_user_id == owner_user_id)
    if grader is not None:
        stmt = stmt.where(GraderPerformanceSnapshot.grader == grader)
    if date_from is not None:
        stmt = stmt.where(GraderPerformanceSnapshot.snapshot_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(GraderPerformanceSnapshot.snapshot_date <= date_to)
    return stmt


def list_records_owner(
    session: Session,
    *,
    owner_user_id: int,
    grading_candidate_id: int | None,
    inventory_item_id: int | None,
    target_grader: str | None,
    reconciliation_status: str | None,
    grading_accuracy_status: str | None,
    confidence_level: str | None,
    date_from: date | None,
    date_to: date | None,
    limit: int,
    offset: int,
) -> tuple[list[GradingReconciliationRecord], int]:
    stmt = _records_query(
        owner_user_id=owner_user_id,
        grading_candidate_id=grading_candidate_id,
        inventory_item_id=inventory_item_id,
        target_grader=target_grader,
        reconciliation_status=reconciliation_status,
        grading_accuracy_status=grading_accuracy_status,
        confidence_level=confidence_level,
        date_from=date_from,
        date_to=date_to,
    )
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(col(GradingReconciliationRecord.created_at).desc(), col(GradingReconciliationRecord.id).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return list(rows), total


def list_records_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    grading_candidate_id: int | None,
    inventory_item_id: int | None,
    target_grader: str | None,
    reconciliation_status: str | None,
    grading_accuracy_status: str | None,
    confidence_level: str | None,
    date_from: date | None,
    date_to: date | None,
    limit: int,
    offset: int,
) -> tuple[list[GradingReconciliationRecord], int]:
    stmt = _records_query(
        owner_user_id=owner_user_id,
        grading_candidate_id=grading_candidate_id,
        inventory_item_id=inventory_item_id,
        target_grader=target_grader,
        reconciliation_status=reconciliation_status,
        grading_accuracy_status=grading_accuracy_status,
        confidence_level=confidence_level,
        date_from=date_from,
        date_to=date_to,
    )
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(col(GradingReconciliationRecord.created_at).desc(), col(GradingReconciliationRecord.id).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return list(rows), total


def list_evidence_owner(
    session: Session,
    *,
    owner_user_id: int,
    record_id: int | None,
    limit: int,
    offset: int,
) -> tuple[list[GradingReconciliationEvidence], int]:
    stmt = _evidence_query(owner_user_id=owner_user_id, record_id=record_id)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(col(GradingReconciliationEvidence.created_at).desc(), col(GradingReconciliationEvidence.id).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return list(rows), total


def list_evidence_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    record_id: int | None,
    limit: int,
    offset: int,
) -> tuple[list[GradingReconciliationEvidence], int]:
    stmt = _evidence_query(owner_user_id=owner_user_id, record_id=record_id)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(col(GradingReconciliationEvidence.created_at).desc(), col(GradingReconciliationEvidence.id).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return list(rows), total


def list_history_owner(
    session: Session,
    *,
    owner_user_id: int,
    grading_candidate_id: int | None,
    inventory_item_id: int | None,
    target_grader: str | None,
    date_from: date | None,
    date_to: date | None,
    limit: int,
    offset: int,
) -> tuple[list[GradingReconciliationHistory], int]:
    stmt = _history_query(
        owner_user_id=owner_user_id,
        grading_candidate_id=grading_candidate_id,
        inventory_item_id=inventory_item_id,
        target_grader=target_grader,
        date_from=date_from,
        date_to=date_to,
    )
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(col(GradingReconciliationHistory.snapshot_date).desc(), col(GradingReconciliationHistory.id).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return list(rows), total


def list_history_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    grading_candidate_id: int | None,
    inventory_item_id: int | None,
    target_grader: str | None,
    date_from: date | None,
    date_to: date | None,
    limit: int,
    offset: int,
) -> tuple[list[GradingReconciliationHistory], int]:
    stmt = _history_query(
        owner_user_id=owner_user_id,
        grading_candidate_id=grading_candidate_id,
        inventory_item_id=inventory_item_id,
        target_grader=target_grader,
        date_from=date_from,
        date_to=date_to,
    )
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(col(GradingReconciliationHistory.snapshot_date).desc(), col(GradingReconciliationHistory.id).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return list(rows), total


def list_performance_owner(
    session: Session,
    *,
    owner_user_id: int,
    grader: str | None,
    date_from: date | None,
    date_to: date | None,
    limit: int,
    offset: int,
) -> tuple[list[GraderPerformanceSnapshot], int]:
    stmt = _performance_query(owner_user_id=owner_user_id, grader=grader, date_from=date_from, date_to=date_to)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(col(GraderPerformanceSnapshot.snapshot_date).desc(), col(GraderPerformanceSnapshot.id).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return list(rows), total


def list_performance_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    grader: str | None,
    date_from: date | None,
    date_to: date | None,
    limit: int,
    offset: int,
) -> tuple[list[GraderPerformanceSnapshot], int]:
    stmt = _performance_query(owner_user_id=owner_user_id, grader=grader, date_from=date_from, date_to=date_to)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = session.exec(
        stmt.order_by(col(GraderPerformanceSnapshot.snapshot_date).desc(), col(GraderPerformanceSnapshot.id).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return list(rows), total


def get_record_owner(session: Session, *, owner_user_id: int, record_id: int) -> GradingReconciliationRecord:
    return _ensure_owner_record(session, owner_user_id=owner_user_id, record_id=record_id)


def get_record_ops(session: Session, *, record_id: int) -> GradingReconciliationRecord:
    return _ensure_ops_record(session, record_id=record_id)


def dashboard_summary_owner(session: Session, *, owner_user_id: int) -> GradingReconciliationDashboardSummary:
    rows = session.exec(
        select(GradingReconciliationRecord).where(GradingReconciliationRecord.owner_user_id == owner_user_id)
    ).all()
    reconciled = [row for row in rows if row.reconciliation_status == "RECONCILED"]
    deltas = [row.roi_delta for row in reconciled if row.roi_delta is not None]
    perf_rows = session.exec(
        select(GraderPerformanceSnapshot)
        .where(GraderPerformanceSnapshot.owner_user_id == owner_user_id)
        .order_by(col(GraderPerformanceSnapshot.snapshot_date).desc(), col(GraderPerformanceSnapshot.id).desc())
    ).all()
    latest_by_grader: dict[str, GraderPerformanceSnapshot] = {}
    for row in perf_rows:
        latest_by_grader.setdefault(row.grader, row)
    return GradingReconciliationDashboardSummary(
        reconciled_count=len(reconciled),
        above_expectation_count=sum(1 for row in reconciled if row.grading_accuracy_status == "ABOVE_EXPECTATION"),
        below_expectation_count=sum(1 for row in reconciled if row.grading_accuracy_status == "BELOW_EXPECTATION"),
        average_roi_delta=_pct(sum(deltas, Decimal("0")) / Decimal(len(deltas))) if deltas else None,
        grader_performance=[_performance_read(row) for row in sorted(latest_by_grader.values(), key=lambda item: item.grader)],
    )


def dashboard_summary_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
) -> GradingReconciliationDashboardSummary:
    stmt = select(GradingReconciliationRecord)
    if owner_user_id is not None:
        stmt = stmt.where(GradingReconciliationRecord.owner_user_id == owner_user_id)
    rows = session.exec(stmt).all()
    reconciled = [row for row in rows if row.reconciliation_status == "RECONCILED"]
    deltas = [row.roi_delta for row in reconciled if row.roi_delta is not None]
    perf_stmt = select(GraderPerformanceSnapshot)
    if owner_user_id is not None:
        perf_stmt = perf_stmt.where(GraderPerformanceSnapshot.owner_user_id == owner_user_id)
    else:
        perf_stmt = perf_stmt.where(GraderPerformanceSnapshot.owner_user_id.is_(None))
    perf_rows = session.exec(
        perf_stmt.order_by(col(GraderPerformanceSnapshot.snapshot_date).desc(), col(GraderPerformanceSnapshot.id).desc())
    ).all()
    latest_by_grader: dict[str, GraderPerformanceSnapshot] = {}
    for row in perf_rows:
        latest_by_grader.setdefault(row.grader, row)
    return GradingReconciliationDashboardSummary(
        reconciled_count=len(reconciled),
        above_expectation_count=sum(1 for row in reconciled if row.grading_accuracy_status == "ABOVE_EXPECTATION"),
        below_expectation_count=sum(1 for row in reconciled if row.grading_accuracy_status == "BELOW_EXPECTATION"),
        average_roi_delta=_pct(sum(deltas, Decimal("0")) / Decimal(len(deltas))) if deltas else None,
        grader_performance=[_performance_read(row) for row in sorted(latest_by_grader.values(), key=lambda item: item.grader)],
    )


def records_response_from_rows(
    *,
    rows: list[GradingReconciliationRecord],
    total: int,
    limit: int,
    offset: int,
) -> GradingReconciliationListResponse:
    return GradingReconciliationListResponse(
        items=[_record_read(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def evidence_response_from_rows(
    *,
    rows: list[GradingReconciliationEvidence],
    total: int,
    limit: int,
    offset: int,
) -> GradingReconciliationEvidenceListResponse:
    return GradingReconciliationEvidenceListResponse(
        items=[_evidence_read(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def history_response_from_rows(
    *,
    rows: list[GradingReconciliationHistory],
    total: int,
    limit: int,
    offset: int,
) -> GradingReconciliationHistoryListResponse:
    return GradingReconciliationHistoryListResponse(
        items=[_history_read(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def performance_response_from_rows(
    *,
    rows: list[GraderPerformanceSnapshot],
    total: int,
    limit: int,
    offset: int,
) -> GraderPerformanceSnapshotListResponse:
    return GraderPerformanceSnapshotListResponse(
        items=[_performance_read(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def inventory_grading_reconciliation_badge(
    session: Session,
    *,
    owner_user_id: int,
    inventory_item_id: int,
) -> InventoryGradingReconciliationBadge | None:
    row = session.exec(
        select(GradingReconciliationRecord)
        .where(GradingReconciliationRecord.owner_user_id == owner_user_id)
        .where(GradingReconciliationRecord.inventory_item_id == inventory_item_id)
        .order_by(col(GradingReconciliationRecord.created_at).desc(), col(GradingReconciliationRecord.id).desc())
    ).first()
    if row is None:
        return None
    return InventoryGradingReconciliationBadge(
        grading_reconciliation_record_id=int(row.id or 0),
        target_grader=row.target_grader,
        final_grade=row.final_grade,
        roi_delta=row.roi_delta,
        grading_accuracy_status=row.grading_accuracy_status,
        reconciliation_status=row.reconciliation_status,
    )
