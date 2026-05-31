"""P56-02 Hold vs Sell Intelligence — HOLD / WATCH / SELL guidance (no listings or grading advice)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, col, select

from app.models.asset_ledger import InventoryCopy, InventoryFmvSnapshot
from app.models.sell_candidate import KEEP_COPIES_DEFAULT
from app.services.exit_candidate_engine import ExitCandidateResult, generate_exit_candidates
from app.services.sell_candidate_engine import (
    CONCENTRATION_THRESHOLD,
    _profit_category,
    _split_identity_key,
    generate_sell_candidates,
)

REC_HOLD = "HOLD"
REC_WATCH = "WATCH"
REC_SELL = "SELL"


@dataclass(frozen=True)
class HoldSellResult:
    inventory_item_id: int
    recommendation: str
    conviction_score: float
    confidence_score: float
    estimated_fmv: float
    acquisition_cost: float
    unrealized_gain: float
    rationale: str
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


def _conviction_for_sell(*, strong: bool, exit_score: float) -> float:
    if strong:
        base = 88.0 + min(12.0, exit_score * 0.12)
        return round(min(100.0, max(85.0, base)), 1)
    base = 72.0 + min(12.0, exit_score * 0.15)
    return round(min(84.0, max(70.0, base)), 1)


def _conviction_for_watch(*, exit_score: float, profit_cat: str) -> float:
    base = 42.0
    if profit_cat == "moderate":
        base += 12.0
    base += min(17.0, exit_score * 0.35)
    return round(min(69.0, max(40.0, base)), 1)


def _conviction_for_hold(*, exit_score: float) -> float:
    return round(min(39.0, max(0.0, 32.0 - exit_score * 0.25)), 1)


def _confidence(
    *,
    recommendation: str,
    has_fmv: bool,
    concentration: float,
    exit_confidence: float,
    sell_consistency: float,
    signal_strength: float,
) -> float:
    base = {"SELL": 0.62, "WATCH": 0.52, "HOLD": 0.48}.get(recommendation, 0.5)
    if has_fmv:
        base += 0.12
    if concentration >= CONCENTRATION_THRESHOLD:
        base += 0.06
    base += exit_confidence * 0.12
    base += sell_consistency * 0.1
    base += signal_strength * 0.08
    return round(_clamp01(base), 4)


def _rationale_sell(
    *,
    duplicate_excess: bool,
    overexposed: bool,
    graded: bool,
    profit_cat: str,
    group_size: int,
) -> str:
    parts: list[str] = []
    if duplicate_excess and profit_cat in {"high", "moderate"}:
        parts.append("Duplicate inventory with strong unrealized gain.")
    elif duplicate_excess:
        parts.append(f"Excess duplicate copy in a {group_size}-copy holding.")
    if overexposed:
        parts.append("Portfolio overexposed to this title.")
    if graded and profit_cat == "high":
        parts.append("Graded copy with large unrealized profit.")
    if profit_cat == "high" and not parts:
        parts.append("Large unrealized gain supports exit timing.")
    if not parts:
        parts.append("Exit signals favor reducing this position.")
    return " ".join(parts)


def _evaluate_copy(
    *,
    copy: InventoryCopy,
    is_excess: bool,
    group_size: int,
    concentration: float,
    fmv: float,
    exit_row: ExitCandidateResult | None,
    sell_recommendation: str | None,
) -> HoldSellResult:
    cost = _money(copy.acquisition_cost)
    unrealized_gain = round(fmv - cost, 2)
    profit_cat = _profit_category(unrealized_gain, cost)
    graded = _is_graded(copy)
    exit_score = float(exit_row.candidate_score) if exit_row else 0.0
    exit_confidence = float(exit_row.confidence_score) if exit_row else 0.0
    exit_reason = exit_row.candidate_reason if exit_row else ""

    overexposed = concentration >= CONCENTRATION_THRESHOLD and unrealized_gain > 0
    duplicate_excess = is_excess and group_size > KEEP_COPIES_DEFAULT

    sell_consistency = 0.0
    if sell_recommendation == "STRONG_SELL":
        sell_consistency = 1.0
    elif sell_recommendation == "SELL":
        sell_consistency = 0.85
    elif sell_recommendation == "REVIEW":
        sell_consistency = 0.35

    signal_strength = min(1.0, exit_score / 100.0)

    if unrealized_gain <= 0 and not duplicate_excess:
        recommendation = REC_HOLD
        conviction = _conviction_for_hold(exit_score=exit_score)
        rationale = "Strategic position with limited near-term gain; hold for now."
        confidence = _confidence(
            recommendation=recommendation,
            has_fmv=fmv > 0,
            concentration=concentration,
            exit_confidence=exit_confidence,
            sell_consistency=sell_consistency,
            signal_strength=signal_strength,
        )
        publisher, series, issue_number, _ = _split_identity_key(copy.metadata_identity_key)
        return HoldSellResult(
            inventory_item_id=int(copy.id),
            recommendation=recommendation,
            conviction_score=conviction,
            confidence_score=confidence,
            estimated_fmv=round(fmv, 2),
            acquisition_cost=round(cost, 2),
            unrealized_gain=unrealized_gain,
            rationale=rationale,
            publisher=publisher,
            title=series or "Unknown",
            issue_number=issue_number,
        )

    strong_sell = (
        (duplicate_excess and profit_cat == "high")
        or (graded and profit_cat == "high")
        or (overexposed and profit_cat == "high")
        or (exit_reason == "MULTIPLE_SIGNALS" and exit_score >= 55.0 and unrealized_gain > 0)
        or sell_recommendation == "STRONG_SELL"
    )
    moderate_sell = (
        not strong_sell
        and (
            duplicate_excess
            or (overexposed and profit_cat in {"high", "moderate"})
            or profit_cat == "high"
            or sell_recommendation in {"SELL", "STRONG_SELL"}
            or (exit_score >= 45.0 and unrealized_gain > 0)
        )
    )

    if strong_sell or moderate_sell:
        recommendation = REC_SELL
        conviction = _conviction_for_sell(strong=strong_sell, exit_score=exit_score)
        rationale = _rationale_sell(
            duplicate_excess=duplicate_excess,
            overexposed=overexposed,
            graded=graded,
            profit_cat=profit_cat,
            group_size=group_size,
        )
    elif (
        (profit_cat == "moderate" and not overexposed and not duplicate_excess)
        or (0 < exit_score < 45 and unrealized_gain > 0 and not overexposed)
        or sell_recommendation == "REVIEW"
        or (exit_score > 0 and profit_cat != "high" and not duplicate_excess and not overexposed)
    ):
        recommendation = REC_WATCH
        conviction = _conviction_for_watch(exit_score=exit_score, profit_cat=profit_cat)
        rationale = "Moderate gain with limited exposure; monitor for improved exit timing."
        if exit_score > 0:
            rationale = "Potential future upside with moderate exit opportunity; watch price and exposure."
    else:
        recommendation = REC_HOLD
        conviction = _conviction_for_hold(exit_score=exit_score)
        rationale = "Long-term hold with limited gain opportunity."
        if unrealized_gain <= 0:
            rationale = "Strategic position with limited near-term gain; hold for now."

    confidence = _confidence(
        recommendation=recommendation,
        has_fmv=fmv > 0,
        concentration=concentration,
        exit_confidence=exit_confidence,
        sell_consistency=sell_consistency,
        signal_strength=signal_strength,
    )

    assert copy.id is not None
    publisher, series, issue_number, _ = _split_identity_key(copy.metadata_identity_key)
    return HoldSellResult(
        inventory_item_id=int(copy.id),
        recommendation=recommendation,
        conviction_score=conviction,
        confidence_score=confidence,
        estimated_fmv=round(fmv, 2),
        acquisition_cost=round(cost, 2),
        unrealized_gain=unrealized_gain,
        rationale=rationale,
        publisher=publisher,
        title=series or "Unknown",
        issue_number=issue_number,
    )


def generate_hold_sell_recommendations(session: Session, *, owner_user_id: int) -> list[HoldSellResult]:
    copies = list(
        session.exec(
            select(InventoryCopy)
            .where(InventoryCopy.user_id == owner_user_id)
            .order_by(InventoryCopy.metadata_identity_key.asc(), InventoryCopy.copy_number.asc(), InventoryCopy.id.asc())
        ).all()
    )
    if not copies:
        return []

    exit_by_id = {r.inventory_item_id: r for r in generate_exit_candidates(session, owner_user_id=owner_user_id)}
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

    results: list[HoldSellResult] = []
    for key, rows in sorted(groups.items()):
        concentration = (group_fmv[key] / total_fmv) if total_fmv > 0 else 0.0
        sorted_rows = sorted(rows, key=lambda r: (r.copy_number, int(r.id or 0)))
        excess_ids: set[int] = set()
        if len(sorted_rows) > KEEP_COPIES_DEFAULT:
            for row in sorted_rows[KEEP_COPIES_DEFAULT:]:
                excess_ids.add(int(row.id or 0))

        for copy in sorted_rows:
            assert copy.id is not None
            inv_id = int(copy.id)
            sell_rec = sell_by_id.get(inv_id)
            results.append(
                _evaluate_copy(
                    copy=copy,
                    is_excess=inv_id in excess_ids,
                    group_size=len(sorted_rows),
                    concentration=concentration,
                    fmv=fmv_by_id[inv_id],
                    exit_row=exit_by_id.get(inv_id),
                    sell_recommendation=sell_rec.recommendation if sell_rec else None,
                )
            )

    results.sort(key=lambda r: (r.recommendation, -r.conviction_score, r.inventory_item_id))
    return results
