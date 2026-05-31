"""P53-04 Budget Allocation Engine — deterministic capital distribution by tier."""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, select

from app.models.purchase_budget import PurchaseBudget
from app.models.purchase_quantity import PurchaseQuantityRecommendation
from app.models.purchase_variant import PurchaseVariantRecommendation
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.schemas.purchase_profile import PurchaseProfileRead
from app.services.purchase_profiles import get_purchase_profile

TIER_ORDER = ("MUST_BUY", "STRONG_BUY", "BUY", "WATCH", "PASS")

BASE_TIER_SHARES: dict[str, float] = {
    "MUST_BUY": 0.50,
    "STRONG_BUY": 0.30,
    "BUY": 0.15,
    "WATCH": 0.05,
    "PASS": 0.0,
}

PROFILE_TIER_SHARES: dict[str, dict[str, float]] = {
    "INVESTOR": {
        "MUST_BUY": 0.55,
        "STRONG_BUY": 0.28,
        "BUY": 0.12,
        "WATCH": 0.05,
        "PASS": 0.0,
    },
    "COLLECTOR": dict(BASE_TIER_SHARES),
    "READER": {
        "MUST_BUY": 0.38,
        "STRONG_BUY": 0.28,
        "BUY": 0.24,
        "WATCH": 0.10,
        "PASS": 0.0,
    },
    "VARIANT_HUNTER": {
        "MUST_BUY": 0.48,
        "STRONG_BUY": 0.30,
        "BUY": 0.17,
        "WATCH": 0.05,
        "PASS": 0.0,
    },
    "LONG_TERM_HOLD": {
        "MUST_BUY": 0.52,
        "STRONG_BUY": 0.32,
        "BUY": 0.13,
        "WATCH": 0.03,
        "PASS": 0.0,
    },
}

PROFILE_BUDGET_UTILIZATION: dict[str, float] = {
    "INVESTOR": 1.0,
    "COLLECTOR": 0.95,
    "READER": 0.82,
    "VARIANT_HUNTER": 0.92,
    "LONG_TERM_HOLD": 0.90,
}


@dataclass(frozen=True)
class BudgetAllocationResult:
    release_id: int
    recommendation_tier: str
    allocated_amount: float
    priority_rank: int
    rationale: str


def _round_money(value: float) -> float:
    return round(max(0.0, float(value)), 2)


def _tier_shares(profile_type: str) -> dict[str, float]:
    key = profile_type.strip().upper()
    shares = dict(PROFILE_TIER_SHARES.get(key, BASE_TIER_SHARES))
    total = sum(shares[t] for t in TIER_ORDER if t != "PASS")
    if total <= 0:
        return dict(BASE_TIER_SHARES)
    if abs(total - 1.0) > 1e-6:
        scale = 1.0 / total
        for tier in ("MUST_BUY", "STRONG_BUY", "BUY", "WATCH"):
            shares[tier] = shares[tier] * scale
    shares["PASS"] = 0.0
    return shares


def _latest_quantity_by_release(session: Session, *, owner_user_id: int) -> dict[int, PurchaseQuantityRecommendation]:
    rows = session.exec(
        select(PurchaseQuantityRecommendation)
        .where(PurchaseQuantityRecommendation.owner_user_id == owner_user_id)
        .order_by(PurchaseQuantityRecommendation.created_at.desc(), PurchaseQuantityRecommendation.id.desc())
    ).all()
    latest: dict[int, PurchaseQuantityRecommendation] = {}
    for row in rows:
        if row.release_id not in latest:
            latest[row.release_id] = row
    return latest


def _variant_buy_boost(session: Session, *, owner_user_id: int, release_id: int) -> float:
    rows = session.exec(
        select(PurchaseVariantRecommendation)
        .where(PurchaseVariantRecommendation.owner_user_id == owner_user_id)
        .where(PurchaseVariantRecommendation.release_id == release_id)
        .order_by(PurchaseVariantRecommendation.created_at.desc(), PurchaseVariantRecommendation.id.desc())
    ).all()
    seen: set[int | None] = set()
    boost = 0.0
    for row in rows:
        if row.variant_id in seen:
            continue
        seen.add(row.variant_id)
        if row.recommendation == "BUY":
            boost += 0.08
        elif row.recommendation == "WATCH":
            boost += 0.03
    return min(boost, 0.15)


def _release_weight(qty: PurchaseQuantityRecommendation, variant_boost: float) -> float:
    if qty.recommendation_tier == "PASS" or qty.quantity_recommended <= 0:
        return 0.0
    return (qty.quantity_recommended * qty.confidence_score) + variant_boost


def _build_rationale(*, tier: str, confidence: float, series_name: str) -> str:
    t = tier.strip().upper()
    if t == "MUST_BUY":
        return "High conviction launch title."
    if t == "STRONG_BUY":
        return "Strong franchise with active pull-list support."
    if t == "BUY":
        return f"Solid {series_name or 'series'} fit with balanced purchase confidence."
    if t == "WATCH":
        return "Watch allocation only due to moderate confidence."
    return "No budget allocated for pass-tier recommendation."


def generate_budget_allocations(
    session: Session,
    *,
    owner_user_id: int,
    budget: PurchaseBudget | None = None,
    profile: PurchaseProfileRead | None = None,
) -> tuple[list[BudgetAllocationResult], float]:
    """
    Compute allocations for owner. Returns (results, total_budget_used_as_cap).
    Uses monthly_budget as the allocation cap when active.
    """
    if budget is None:
        from app.services.purchase_budgets import get_purchase_budget_row

        budget = get_purchase_budget_row(session, owner_user_id=owner_user_id)
    if profile is None:
        profile = get_purchase_profile(session, owner_user_id=owner_user_id)

    cap = _round_money(float(budget.monthly_budget))
    if not budget.is_active or cap <= 0:
        return [], cap

    util = PROFILE_BUDGET_UTILIZATION.get(profile.profile_type.strip().upper(), 0.95)
    spendable = _round_money(cap * util)
    shares = _tier_shares(profile.profile_type)
    qty_by_release = _latest_quantity_by_release(session, owner_user_id=owner_user_id)

    by_tier: dict[str, list[tuple[int, float, PurchaseQuantityRecommendation]]] = {t: [] for t in TIER_ORDER}
    for release_id, qty in qty_by_release.items():
        tier = qty.recommendation_tier.strip().upper()
        if tier not in by_tier:
            tier = "PASS"
        boost = _variant_buy_boost(session, owner_user_id=owner_user_id, release_id=release_id)
        weight = _release_weight(qty, boost)
        by_tier[tier].append((release_id, weight, qty))

    for tier in by_tier:
        by_tier[tier].sort(key=lambda x: (-x[1], x[0]))

    raw_alloc: dict[int, tuple[str, float, PurchaseQuantityRecommendation]] = {}
    for tier in ("MUST_BUY", "STRONG_BUY", "BUY", "WATCH", "PASS"):
        pool = _round_money(spendable * shares.get(tier, 0.0))
        items = by_tier[tier]
        if tier == "PASS" or pool <= 0 or not items:
            for release_id, _, qty in items:
                raw_alloc[release_id] = (tier, 0.0, qty)
            continue
        total_weight = sum(w for _, w, _ in items if w > 0)
        if total_weight <= 0:
            equal = _round_money(pool / len(items)) if items else 0.0
            for release_id, _, qty in items:
                raw_alloc[release_id] = (tier, equal, qty)
            continue
        for release_id, weight, qty in items:
            if weight <= 0:
                raw_alloc[release_id] = (tier, 0.0, qty)
            else:
                raw_alloc[release_id] = (tier, _round_money(pool * (weight / total_weight)), qty)

    # Reconcile rounding: trim from lowest priority if over spendable
    ordered_release_ids: list[int] = []
    for tier in ("MUST_BUY", "STRONG_BUY", "BUY", "WATCH", "PASS"):
        ordered_release_ids.extend(release_id for release_id, _, _ in by_tier[tier])

    total_allocated = _round_money(sum(amt for _, amt, _ in raw_alloc.values()))
    if total_allocated > spendable and ordered_release_ids:
        excess = _round_money(total_allocated - spendable)
        for release_id in reversed(ordered_release_ids):
            if excess <= 0:
                break
            tier, amt, qty = raw_alloc[release_id]
            if amt <= 0:
                continue
            cut = min(amt, excess)
            raw_alloc[release_id] = (tier, _round_money(amt - cut), qty)
            excess = _round_money(excess - cut)

    results: list[BudgetAllocationResult] = []
    rank = 1
    for tier in ("MUST_BUY", "STRONG_BUY", "BUY", "WATCH", "PASS"):
        for release_id, _, qty in by_tier[tier]:
            tier_name, amount, q = raw_alloc[release_id]
            issue = session.get(ReleaseIssue, release_id)
            series = session.get(ReleaseSeries, issue.series_id) if issue else None
            series_name = series.series_name if series else ""
            rationale = _build_rationale(tier=tier_name, confidence=float(q.confidence_score), series_name=series_name)
            results.append(
                BudgetAllocationResult(
                    release_id=release_id,
                    recommendation_tier=tier_name,
                    allocated_amount=amount,
                    priority_rank=rank,
                    rationale=rationale,
                )
            )
            rank += 1

    return results, cap
