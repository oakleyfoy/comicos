"""P72-03 grading outcome tracking (expected vs actual)."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from sqlmodel import Session, select

from app.models import InventoryCopy
from app.models.p72_grading_analytics import P72GradingOutcome
from app.models.p72_grading_operations import P72GradingQueueEntry
from app.services.grading_candidate_engine import build_grading_decision_for_copy
from app.services.grading_roi_service import GRADE_FMV_MULTIPLIERS

MONEY = Decimal("0.01")


def _d(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)


def _graded_value_for_grade(*, raw_fmv: Decimal, grade: str) -> Decimal:
    key = grade if grade in GRADE_FMV_MULTIPLIERS else "other"
    mult = GRADE_FMV_MULTIPLIERS.get(key, 1.25)
    return _d(float(raw_fmv) * mult)


def _era_from_year(release_year: int | None) -> str:
    if release_year is None:
        return "unknown"
    if release_year >= 2015:
        return "modern"
    if release_year >= 1985:
        return "copper_modern"
    if release_year >= 1956:
        return "silver_bronze"
    return "golden_age"


def _accuracy_label(*, expected_roi: Decimal, actual_roi: Decimal, recommendation: str) -> str:
    if recommendation in {"DO_NOT_GRADE", "WATCH"}:
        return "N/A"
    delta = abs(float(expected_roi) - float(actual_roi))
    if actual_roi < 0:
        return "LOW"
    if delta <= 15:
        return "HIGH"
    if delta <= 35:
        return "MEDIUM"
    return "LOW"


def record_outcome_for_queue_entry(
    session: Session,
    *,
    owner_user_id: int,
    entry: P72GradingQueueEntry,
    queue_status: str,
    final_grading_cost: Decimal | float | None = None,
    actual_grade: str | None = None,
) -> P72GradingOutcome:
    existing = session.exec(
        select(P72GradingOutcome).where(P72GradingOutcome.queue_entry_id == entry.id)
    ).first()
    if existing is not None:
        existing.queue_status = queue_status
        session.add(existing)
        session.flush()
        return existing

    copy = session.get(InventoryCopy, entry.inventory_copy_id)
    decision = None
    if copy is not None:
        decision = build_grading_decision_for_copy(session, owner_user_id=owner_user_id, copy=copy)

    raw = _d(decision.raw_fmv if decision else entry.estimated_grading_cost or 0)
    if raw <= 0 and copy and copy.current_fmv:
        raw = _d(copy.current_fmv)

    actual_grade = actual_grade or entry.actual_grade or "9.0"
    if final_grading_cost is not None:
        cost = _d(final_grading_cost)
    elif entry.final_grading_cost is not None:
        cost = _d(entry.final_grading_cost)
    elif decision is not None:
        cost = _d(decision.expected_total_cost)
    else:
        cost = _d(38)
    graded_val = _graded_value_for_grade(raw_fmv=raw, grade=actual_grade)
    actual_profit = _d(float(graded_val) - float(raw) - float(cost))
    actual_roi = _d((float(actual_profit) / float(cost) * 100.0) if float(cost) > 0 else 0)

    expected_grade = decision.expected_grade if decision else "9.6"
    expected_roi = _d(decision.expected_roi_pct if decision else 0)
    expected_profit = _d(decision.expected_profit if decision else 0)
    recommendation = decision.recommendation if decision else "GRADE"
    press_rec = decision.pressing_recommendation if decision else "DO_NOT_PRESS"
    was_pressed = False
    if decision:
        cb = (decision.factors_json.get("roi_calculation") or {}).get("cost_breakdown") or {}
        was_pressed = float(cb.get("pressing_fee") or 0) > 0

    release_year = copy.release_year if copy else None
    row = P72GradingOutcome(
        owner_user_id=owner_user_id,
        queue_entry_id=int(entry.id or 0),
        inventory_copy_id=entry.inventory_copy_id,
        title=entry.title,
        publisher=entry.publisher,
        issue_number=entry.issue_number,
        series=entry.title,
        era=_era_from_year(release_year),
        recommendation=recommendation,
        pressing_recommended=press_rec,
        was_pressed=was_pressed,
        expected_grade=expected_grade,
        actual_grade=actual_grade,
        expected_roi_pct=expected_roi,
        actual_roi_pct=actual_roi,
        expected_profit=expected_profit,
        actual_profit=actual_profit,
        raw_fmv=raw,
        graded_value_estimate=graded_val,
        actual_grading_cost=cost,
        recommendation_accuracy=_accuracy_label(
            expected_roi=expected_roi,
            actual_roi=actual_roi,
            recommendation=recommendation,
        ),
        queue_status=queue_status,
        metadata_json={
            "certification_number": entry.certification_number,
            "slab_notes": entry.slab_notes,
        },
    )
    session.add(row)
    session.flush()
    return row


def list_outcomes(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 100,
) -> list[P72GradingOutcome]:
    return list(
        session.exec(
            select(P72GradingOutcome)
            .where(P72GradingOutcome.owner_user_id == owner_user_id)
            .order_by(P72GradingOutcome.recorded_at.desc(), P72GradingOutcome.id.desc())
            .limit(min(max(limit, 1), 500))
        ).all()
    )


def sync_outcomes_from_queue(
    session: Session,
    *,
    owner_user_id: int,
) -> int:
    """Backfill outcomes for returned+ queue rows missing outcome records."""
    from app.services.grading_queue_service import COMPLETED_STATUSES

    entries = session.exec(
        select(P72GradingQueueEntry)
        .where(P72GradingQueueEntry.owner_user_id == owner_user_id)
        .where(P72GradingQueueEntry.status.in_(list(COMPLETED_STATUSES)))
        .where(P72GradingQueueEntry.actual_grade.isnot(None))
    ).all()
    count = 0
    for entry in entries:
        if entry.actual_grade:
            record_outcome_for_queue_entry(
                session,
                owner_user_id=owner_user_id,
                entry=entry,
                queue_status=entry.status,
            )
            count += 1
    session.commit()
    return count
