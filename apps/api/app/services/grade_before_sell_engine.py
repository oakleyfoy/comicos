"""P56-03 Grade Before Sell Intelligence — grade vs sell raw guidance (no submissions or sales)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlmodel import Session, col, select

from app.models.asset_ledger import InventoryCopy, InventoryFmvSnapshot
from app.models.grading_candidate import GradingCandidate
from app.services.hold_sell_engine import generate_hold_sell_recommendations
from app.services.sell_candidate_engine import _grading_candidate, _split_identity_key

REC_GRADE = "GRADE_BEFORE_SELL"
REC_SELL_RAW = "SELL_RAW"
REC_REVIEW = "HOLD_FOR_REVIEW"

DEFAULT_GRADING_COST = 40.0
HIGH_PRIORITY = frozenset({"HIGH", "CRITICAL", "ELITE"})


@dataclass(frozen=True)
class GradeBeforeSellResult:
    inventory_item_id: int
    recommendation: str
    current_estimated_value: float
    expected_graded_value: float
    estimated_grading_cost: float
    expected_value_gain: float
    expected_roi: float
    confidence_score: float
    rationale: str
    publisher: str
    title: str
    issue_number: str


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _money(value: Decimal | float | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def _latest_fmv(session: Session, *, inventory_item_id: int, copy: InventoryCopy) -> float:
    row = session.exec(
        select(InventoryFmvSnapshot)
        .where(InventoryFmvSnapshot.inventory_copy_id == inventory_item_id)
        .order_by(col(InventoryFmvSnapshot.changed_at).desc())
        .order_by(col(InventoryFmvSnapshot.id).desc())
    ).first()
    if row is not None:
        return _money(row.new_fmv)
    return _money(copy.current_fmv)


def _is_raw(copy: InventoryCopy) -> bool:
    status = (copy.grade_status or "").strip().lower()
    return not status or status in {"raw", "ungraded"}


def _value_gain(*, expected_graded: float, current: float, cost: float) -> float:
    return round(expected_graded - current - cost, 2)


def _roi(*, gain: float, cost: float) -> float:
    if cost <= 0:
        return 0.0
    return round(gain / cost, 4)


def _resolve_estimates(
    *,
    copy: InventoryCopy,
    candidate: GradingCandidate | None,
    current_fmv: float,
) -> tuple[float, float | None, float | None, bool]:
    """Returns current value, expected graded, cost, and whether estimates are complete."""
    current = current_fmv
    if candidate is not None and candidate.estimated_raw_value is not None:
        current = _money(candidate.estimated_raw_value) or current_fmv

    graded: float | None = None
    cost: float | None = None
    if candidate is not None:
        if candidate.estimated_graded_value is not None:
            graded = _money(candidate.estimated_graded_value)
        if candidate.estimated_grading_cost is not None:
            cost = _money(candidate.estimated_grading_cost)
        elif candidate.estimated_roi is not None and graded is not None and cost is None:
            pass

    complete = graded is not None and cost is not None and cost > 0
    return current, graded, cost, complete


def _confidence(
    *,
    recommendation: str,
    complete: bool,
    priority: str | None,
    hold_sell_rec: str | None,
    gain: float,
) -> float:
    base = {"GRADE_BEFORE_SELL": 0.68, "SELL_RAW": 0.62, "HOLD_FOR_REVIEW": 0.48}.get(recommendation, 0.5)
    if complete:
        base += 0.14
    if priority in HIGH_PRIORITY:
        base += 0.1
    elif priority:
        base += 0.04
    if hold_sell_rec == "SELL":
        base += 0.06
    elif hold_sell_rec == "WATCH":
        base += 0.03
    if gain > 50:
        base += 0.06
    return round(_clamp01(base), 4)


def _evaluate(
    *,
    copy: InventoryCopy,
    candidate: GradingCandidate | None,
    current_fmv: float,
    hold_sell_rec: str | None,
) -> GradeBeforeSellResult:
    assert copy.id is not None
    inv_id = int(copy.id)
    publisher, series, issue_number, _ = _split_identity_key(copy.metadata_identity_key)
    title = series or "Unknown"

    if not _is_raw(copy):
        return GradeBeforeSellResult(
            inventory_item_id=inv_id,
            recommendation=REC_SELL_RAW,
            current_estimated_value=round(current_fmv, 2),
            expected_graded_value=round(current_fmv, 2),
            estimated_grading_cost=0.0,
            expected_value_gain=0.0,
            expected_roi=0.0,
            confidence_score=_confidence(
                recommendation=REC_SELL_RAW,
                complete=True,
                priority=None,
                hold_sell_rec=hold_sell_rec,
                gain=0.0,
            ),
            rationale="Already graded; sell as slab without additional raw grading upside.",
            publisher=publisher,
            title=title,
            issue_number=issue_number,
        )

    current, graded, cost, complete = _resolve_estimates(copy=copy, candidate=candidate, current_fmv=current_fmv)
    priority = candidate.candidate_priority if candidate else None

    if not complete or graded is None or cost is None:
        cost_val = cost if cost is not None else DEFAULT_GRADING_COST
        return GradeBeforeSellResult(
            inventory_item_id=inv_id,
            recommendation=REC_REVIEW,
            current_estimated_value=round(current, 2),
            expected_graded_value=round(graded, 2) if graded is not None else round(current, 2),
            estimated_grading_cost=round(cost_val, 2),
            expected_value_gain=0.0,
            expected_roi=0.0,
            confidence_score=_confidence(
                recommendation=REC_REVIEW,
                complete=False,
                priority=priority,
                hold_sell_rec=hold_sell_rec,
                gain=0.0,
            ),
            rationale="Requires further review due to uncertain valuation.",
            publisher=publisher,
            title=title,
            issue_number=issue_number,
        )

    gain = _value_gain(expected_graded=graded, current=current, cost=cost)
    roi = _roi(gain=gain, cost=cost)

    strong_upside = (
        gain > 0
        and roi >= 1.0
        and (priority in HIGH_PRIORITY or roi >= 1.25 or gain >= 50.0)
    )
    weak_upside = gain <= 0 or roi < 0.25

    if strong_upside:
        recommendation = REC_GRADE
        rationale = "Expected PSA upside significantly exceeds grading cost."
        if priority in HIGH_PRIORITY:
            rationale = "High grade candidate with strong ROI and significant value increase."
    elif weak_upside:
        recommendation = REC_SELL_RAW
        rationale = "Limited grading benefit; sell raw."
        if gain <= 0:
            rationale = "Negative ROI after grading cost; sell raw."
    else:
        recommendation = REC_REVIEW
        rationale = "Borderline ROI; hold for review before choosing grade vs raw sale."

    confidence = _confidence(
        recommendation=recommendation,
        complete=True,
        priority=priority,
        hold_sell_rec=hold_sell_rec,
        gain=gain,
    )

    return GradeBeforeSellResult(
        inventory_item_id=inv_id,
        recommendation=recommendation,
        current_estimated_value=round(current, 2),
        expected_graded_value=round(graded, 2),
        estimated_grading_cost=round(cost, 2),
        expected_value_gain=gain,
        expected_roi=roi,
        confidence_score=confidence,
        rationale=rationale,
        publisher=publisher,
        title=title,
        issue_number=issue_number,
    )


def generate_grade_before_sell_recommendations(session: Session, *, owner_user_id: int) -> list[GradeBeforeSellResult]:
    copies = list(
        session.exec(
            select(InventoryCopy)
            .where(InventoryCopy.user_id == owner_user_id)
            .order_by(InventoryCopy.id.asc())
        ).all()
    )
    if not copies:
        return []

    hold_by_id = {r.inventory_item_id: r for r in generate_hold_sell_recommendations(session, owner_user_id=owner_user_id)}

    results: list[GradeBeforeSellResult] = []
    for copy in copies:
        assert copy.id is not None
        inv_id = int(copy.id)
        fmv = _latest_fmv(session, inventory_item_id=inv_id, copy=copy)
        candidate = _grading_candidate(session, owner_user_id=owner_user_id, inventory_item_id=inv_id)
        hold = hold_by_id.get(inv_id)
        hold_rec = hold.recommendation if hold else None
        results.append(
            _evaluate(
                copy=copy,
                candidate=candidate,
                current_fmv=fmv,
                hold_sell_rec=hold_rec,
            )
        )

    results.sort(key=lambda r: (r.recommendation, -r.expected_roi, r.inventory_item_id))
    return results
