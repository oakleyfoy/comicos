"""P56-01 Exit Candidate Foundation — disposition signals without hold/sell decisions."""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, col, select

from app.models.asset_ledger import InventoryCopy, InventoryFmvSnapshot
from app.models.sell_candidate import KEEP_COPIES_DEFAULT
from app.services.sell_candidate_engine import (
    CONCENTRATION_THRESHOLD,
    _grading_candidate,
    _profit_category,
    _split_identity_key,
    generate_sell_candidates,
)

REASON_DUPLICATE = "DUPLICATE"
REASON_PROFITABLE = "PROFITABLE"
REASON_GRADED = "GRADED"
REASON_OVEREXPOSED = "OVEREXPOSED"
REASON_CAPITAL_RECOVERY = "CAPITAL_RECOVERY"
REASON_MULTIPLE = "MULTIPLE_SIGNALS"

SCORE_DUPLICATE = 20.0
SCORE_PROFITABLE = 25.0
SCORE_OVEREXPOSED = 20.0
SCORE_GRADED = 15.0
SCORE_CAPITAL_RECOVERY = 15.0
MULTIPLE_SIGNAL_BONUS = 10.0


@dataclass(frozen=True)
class ExitCandidateResult:
    inventory_item_id: int
    candidate_score: float
    confidence_score: float
    estimated_fmv: float
    acquisition_cost: float
    unrealized_gain: float
    candidate_reason: str
    publisher: str
    title: str
    issue_number: str


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _money(value: float | None) -> float:
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


def _is_graded(copy: InventoryCopy) -> bool:
    status = (copy.grade_status or "").strip().lower()
    return bool(status and status not in {"raw", "ungraded"})


def _reason_from_signals(signals: list[str]) -> str:
    if len(signals) >= 2:
        return REASON_MULTIPLE
    if not signals:
        return REASON_CAPITAL_RECOVERY
    priority = [
        REASON_DUPLICATE,
        REASON_PROFITABLE,
        REASON_OVEREXPOSED,
        REASON_GRADED,
        REASON_CAPITAL_RECOVERY,
    ]
    for reason in priority:
        if reason in signals:
            return reason
    return signals[0]


def _confidence(
    *,
    signal_count: int,
    has_fmv: bool,
    concentration: float,
    candidate_score: float,
    sell_signal_strength: float,
    has_grading_intel: bool,
) -> float:
    base = 0.32 + 0.07 * signal_count
    if has_fmv:
        base += 0.14
    if concentration >= CONCENTRATION_THRESHOLD:
        base += 0.08
    if has_grading_intel:
        base += 0.05
    base += sell_signal_strength * 0.12
    base += min(0.22, candidate_score / 450.0)
    return round(_clamp01(base), 4)


def _score_copy(
    *,
    is_excess: bool,
    profit_cat: str,
    graded: bool,
    concentration: float,
    unrealized_gain: float,
) -> tuple[float, list[str]]:
    signals: list[str] = []
    score = 0.0
    if is_excess:
        signals.append(REASON_DUPLICATE)
        score += SCORE_DUPLICATE
    if profit_cat == "high":
        signals.append(REASON_PROFITABLE)
        score += SCORE_PROFITABLE
    if concentration >= CONCENTRATION_THRESHOLD and unrealized_gain > 0:
        signals.append(REASON_OVEREXPOSED)
        score += SCORE_OVEREXPOSED
    if graded:
        signals.append(REASON_GRADED)
        score += SCORE_GRADED
    if unrealized_gain > 0 and profit_cat == "moderate":
        signals.append(REASON_CAPITAL_RECOVERY)
        score += SCORE_CAPITAL_RECOVERY
    elif unrealized_gain > 0 and profit_cat == "high" and REASON_PROFITABLE not in signals:
        signals.append(REASON_CAPITAL_RECOVERY)
        score += SCORE_CAPITAL_RECOVERY
    if len(signals) >= 2:
        score += MULTIPLE_SIGNAL_BONUS
    return round(min(100.0, score), 1), signals


def generate_exit_candidates(session: Session, *, owner_user_id: int) -> list[ExitCandidateResult]:
    copies = list(
        session.exec(
            select(InventoryCopy)
            .where(InventoryCopy.user_id == owner_user_id)
            .order_by(InventoryCopy.metadata_identity_key.asc(), InventoryCopy.copy_number.asc(), InventoryCopy.id.asc())
        ).all()
    )
    if not copies:
        return []

    sell_by_id = {r.inventory_item_id: r for r in generate_sell_candidates(session, owner_user_id=owner_user_id)}

    fmv_by_id: dict[int, float] = {}
    total_fmv = 0.0
    for copy in copies:
        assert copy.id is not None
        fmv = _latest_fmv(session, inventory_item_id=int(copy.id), copy=copy)
        fmv_by_id[int(copy.id)] = fmv
        total_fmv += fmv

    groups: dict[str, list[InventoryCopy]] = {}
    for copy in copies:
        key = (copy.metadata_identity_key or f"variant:{copy.variant_id}").strip()
        groups.setdefault(key, []).append(copy)

    group_fmv: dict[str, float] = {}
    for key, rows in groups.items():
        group_fmv[key] = sum(fmv_by_id[int(r.id or 0)] for r in rows)

    results: list[ExitCandidateResult] = []
    for key, rows in sorted(groups.items()):
        concentration = (group_fmv[key] / total_fmv) if total_fmv > 0 else 0.0
        sorted_rows = sorted(rows, key=lambda r: (r.copy_number, int(r.id or 0)))
        excess_ids: set[int] = set()
        if len(sorted_rows) > KEEP_COPIES_DEFAULT:
            for row in sorted_rows[KEEP_COPIES_DEFAULT:]:
                excess_ids.add(int(row.id or 0))

        publisher, series, issue_number, _variant = _split_identity_key(key if "|" in key else rows[0].metadata_identity_key)
        title = series or "Unknown"

        for copy in sorted_rows:
            assert copy.id is not None
            inv_id = int(copy.id)
            fmv = fmv_by_id[inv_id]
            cost = _money(copy.acquisition_cost)
            unrealized_gain = round(fmv - cost, 2)
            profit_cat = _profit_category(unrealized_gain, cost)
            graded = _is_graded(copy)
            grading = _grading_candidate(session, owner_user_id=owner_user_id, inventory_item_id=inv_id)
            candidate_score, signals = _score_copy(
                is_excess=inv_id in excess_ids,
                profit_cat=profit_cat,
                graded=graded,
                concentration=concentration,
                unrealized_gain=unrealized_gain,
            )
            if candidate_score <= 0:
                continue

            sell_row = sell_by_id.get(inv_id)
            sell_strength = 0.0
            if sell_row is not None:
                if sell_row.recommendation == "STRONG_SELL":
                    sell_strength = 1.0
                elif sell_row.recommendation == "SELL":
                    sell_strength = 0.75
                elif sell_row.recommendation == "REVIEW":
                    sell_strength = 0.35

            confidence = _confidence(
                signal_count=len(signals),
                has_fmv=fmv > 0,
                concentration=concentration,
                candidate_score=candidate_score,
                sell_signal_strength=sell_strength,
                has_grading_intel=grading is not None,
            )
            results.append(
                ExitCandidateResult(
                    inventory_item_id=inv_id,
                    candidate_score=candidate_score,
                    confidence_score=confidence,
                    estimated_fmv=round(fmv, 2),
                    acquisition_cost=round(cost, 2),
                    unrealized_gain=unrealized_gain,
                    candidate_reason=_reason_from_signals(signals),
                    publisher=publisher,
                    title=title,
                    issue_number=issue_number,
                )
            )

    results.sort(key=lambda r: (-r.candidate_score, -r.confidence_score, r.inventory_item_id))
    return results
