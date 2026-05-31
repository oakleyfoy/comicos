"""P54-05 Sell Candidate Intelligence — deterministic hold vs sell guidance."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlmodel import Session, col, select

from app.models.asset_ledger import InventoryCopy, InventoryFmvSnapshot
from app.models.grading_candidate import GradingCandidate
from app.models.sell_candidate import KEEP_COPIES_DEFAULT

REC_STRONG_SELL = "STRONG_SELL"
REC_SELL = "SELL"
REC_HOLD = "HOLD"
REC_REVIEW = "REVIEW"

HIGH_PROFIT_RATIO = 0.50
MODERATE_PROFIT_RATIO = 0.20
CONCENTRATION_THRESHOLD = 0.18


@dataclass(frozen=True)
class SellCandidateResult:
    inventory_item_id: int
    recommendation: str
    confidence_score: float
    rationale: str
    estimated_fmv: float
    estimated_profit: float
    publisher: str
    title: str
    issue_number: str


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _money(value: Decimal | float | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def _split_identity_key(key: str | None) -> tuple[str, str, str, str]:
    if not key:
        return "", "", "", ""
    parts = key.split("|")
    while len(parts) < 4:
        parts.append("")
    return parts[0], parts[1], parts[2], parts[3]


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


def _grading_candidate(session: Session, *, owner_user_id: int, inventory_item_id: int) -> GradingCandidate | None:
    return session.exec(
        select(GradingCandidate)
        .where(GradingCandidate.owner_user_id == owner_user_id)
        .where(GradingCandidate.inventory_item_id == inventory_item_id)
        .order_by(col(GradingCandidate.updated_at).desc())
        .order_by(col(GradingCandidate.id).desc())
    ).first()


def _high_grade_potential(copy: InventoryCopy, candidate: GradingCandidate | None) -> bool:
    if copy.grade_status and copy.grade_status.lower() != "raw":
        return False
    if copy.star_rating is not None and int(copy.star_rating) >= 4:
        return True
    if candidate is not None and candidate.candidate_priority in {"HIGH", "CRITICAL"}:
        return True
    if candidate is not None and candidate.estimated_roi is not None and float(candidate.estimated_roi) >= 0.35:
        return True
    return False


def _profit_category(profit: float, cost: float) -> str:
    if cost <= 0:
        return "moderate" if profit > 0 else "low"
    ratio = profit / cost
    if ratio >= HIGH_PROFIT_RATIO:
        return "high"
    if ratio >= MODERATE_PROFIT_RATIO:
        return "moderate"
    return "low"


def _confidence(
    *,
    recommendation: str,
    profit_cat: str,
    duplicate_count: int,
    is_excess: bool,
    concentration: float,
    liquidity_score: float,
) -> float:
    base = {
        REC_STRONG_SELL: 0.78,
        REC_SELL: 0.68,
        REC_HOLD: 0.58,
        REC_REVIEW: 0.62,
    }.get(recommendation, 0.55)
    if profit_cat == "high":
        base += 0.12
    elif profit_cat == "moderate":
        base += 0.06
    if is_excess and duplicate_count >= 3:
        base += 0.08
    if concentration >= CONCENTRATION_THRESHOLD:
        base += 0.06
    base += liquidity_score * 0.05
    return round(_clamp01(base), 4)


def evaluate_sell_candidate_for_copy(
    *,
    copy: InventoryCopy,
    copy_index_in_group: int,
    group_size: int,
    is_excess: bool,
    concentration_score: float,
    fmv: float,
    grading: GradingCandidate | None,
    liquidity_score: float,
) -> tuple[str, float, str]:
    cost = _money(copy.acquisition_cost)
    profit = round(fmv - cost, 2)
    profit_cat = _profit_category(profit, cost)
    graded = copy.grade_status and copy.grade_status.lower() not in {"raw", "ungraded", ""}

    if _high_grade_potential(copy, grading) and profit_cat != "high":
        return (
            REC_REVIEW,
            _confidence(
                recommendation=REC_REVIEW,
                profit_cat=profit_cat,
                duplicate_count=group_size,
                is_excess=is_excess,
                concentration=concentration_score,
                liquidity_score=liquidity_score,
            ),
            "Consider grading before sale; high raw grade potential.",
        )

    if is_excess and group_size >= 3:
        if profit_cat == "high":
            return (
                REC_STRONG_SELL,
                _confidence(
                    recommendation=REC_STRONG_SELL,
                    profit_cat=profit_cat,
                    duplicate_count=group_size,
                    is_excess=True,
                    concentration=concentration_score,
                    liquidity_score=liquidity_score,
                ),
                f"Owns {group_size} copies with significant unrealized gain.",
            )
        if profit > 0:
            return (
                REC_SELL,
                _confidence(
                    recommendation=REC_SELL,
                    profit_cat=profit_cat,
                    duplicate_count=group_size,
                    is_excess=True,
                    concentration=concentration_score,
                    liquidity_score=liquidity_score,
                ),
                f"Excess duplicate copy {copy_index_in_group + 1} of {group_size}; consider selling {max(0, group_size - KEEP_COPIES_DEFAULT)} surplus.",
            )

    if concentration_score >= CONCENTRATION_THRESHOLD and profit > 0:
        return (
            REC_SELL,
            _confidence(
                recommendation=REC_SELL,
                profit_cat=profit_cat,
                duplicate_count=group_size,
                is_excess=is_excess,
                concentration=concentration_score,
                liquidity_score=liquidity_score,
            ),
            "Portfolio overexposed to this title.",
        )

    if graded and profit_cat == "high":
        return (
            REC_STRONG_SELL,
            _confidence(
                recommendation=REC_STRONG_SELL,
                profit_cat=profit_cat,
                duplicate_count=group_size,
                is_excess=is_excess,
                concentration=concentration_score,
                liquidity_score=liquidity_score,
            ),
            "Graded copy with large unrealized profit.",
        )

    if profit_cat == "high":
        return (
            REC_SELL,
            _confidence(
                recommendation=REC_SELL,
                profit_cat=profit_cat,
                duplicate_count=group_size,
                is_excess=is_excess,
                concentration=concentration_score,
                liquidity_score=liquidity_score,
            ),
            "Capital better deployed elsewhere.",
        )

    if profit <= 0 and group_size == 1:
        return (
            REC_HOLD,
            _confidence(
                recommendation=REC_HOLD,
                profit_cat=profit_cat,
                duplicate_count=group_size,
                is_excess=False,
                concentration=concentration_score,
                liquidity_score=liquidity_score,
            ),
            "Single copy with limited upside; hold for now.",
        )

    return (
        REC_HOLD,
        _confidence(
            recommendation=REC_HOLD,
            profit_cat=profit_cat,
            duplicate_count=group_size,
            is_excess=is_excess,
            concentration=concentration_score,
            liquidity_score=liquidity_score,
        ),
        "Low upside remaining.",
    )


def generate_sell_candidates(session: Session, *, owner_user_id: int) -> list[SellCandidateResult]:
    copies = list(
        session.exec(
            select(InventoryCopy)
            .where(InventoryCopy.user_id == owner_user_id)
            .order_by(InventoryCopy.metadata_identity_key.asc(), InventoryCopy.copy_number.asc(), InventoryCopy.id.asc())
        ).all()
    )
    if not copies:
        return []

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

    results: list[SellCandidateResult] = []
    for key, rows in sorted(groups.items()):
        concentration = (group_fmv[key] / total_fmv) if total_fmv > 0 else 0.0
        sorted_rows = sorted(rows, key=lambda r: (r.copy_number, int(r.id or 0)))
        excess_ids = set()
        if len(sorted_rows) > KEEP_COPIES_DEFAULT:
            for row in sorted_rows[KEEP_COPIES_DEFAULT:]:
                excess_ids.add(int(row.id or 0))

        publisher, series, issue_number, _variant = _split_identity_key(key if "|" in key else rows[0].metadata_identity_key)
        title = series or "Unknown"

        for idx, copy in enumerate(sorted_rows):
            assert copy.id is not None
            inv_id = int(copy.id)
            grading = _grading_candidate(session, owner_user_id=owner_user_id, inventory_item_id=inv_id)
            liquidity_score = 0.55 if fmv_by_id[inv_id] >= 25 else 0.35
            rec, conf, rationale = evaluate_sell_candidate_for_copy(
                copy=copy,
                copy_index_in_group=idx,
                group_size=len(sorted_rows),
                is_excess=inv_id in excess_ids,
                concentration_score=concentration,
                fmv=fmv_by_id[inv_id],
                grading=grading,
                liquidity_score=liquidity_score,
            )
            cost = _money(copy.acquisition_cost)
            results.append(
                SellCandidateResult(
                    inventory_item_id=inv_id,
                    recommendation=rec,
                    confidence_score=conf,
                    rationale=rationale,
                    estimated_fmv=round(fmv_by_id[inv_id], 2),
                    estimated_profit=round(fmv_by_id[inv_id] - cost, 2),
                    publisher=publisher,
                    title=title,
                    issue_number=issue_number,
                )
            )

    results.sort(key=lambda r: (r.recommendation, -r.confidence_score, r.inventory_item_id))
    return results
