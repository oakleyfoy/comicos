"""P77-02 collector-aware scoring and quantity adjustments."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlmodel import Session, select

from app.models.asset_ledger import Order
from app.schemas.p77_collector_profile import P77CollectorGoalRead, P77CollectorProfileRead
from app.schemas.p77_personalization import P77PersonalizationAdjustmentRead, P77PersonalizationSnapshotRead
from app.services.p77_collector_profile_service import get_collector_budget, get_collector_profile, list_collector_goals


@dataclass
class CollectorPersonalizationContext:
    profile: P77CollectorProfileRead
    monthly_budget: float
    monthly_spend: float
    remaining_budget: float
    budget_state: str
    goals: list[P77CollectorGoalRead] = field(default_factory=list)


def _clamp_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 1)


def compute_monthly_spend(session: Session, *, owner_user_id: int) -> float:
    today = date.today()
    period_start = date(today.year, today.month, 1)
    rows = session.exec(
        select(Order).where(Order.user_id == owner_user_id).where(Order.order_date >= period_start)
    ).all()
    return round(sum(float(row.total_amount or 0) for row in rows), 2)


def budget_state_for(*, monthly_budget: float, monthly_spend: float) -> str:
    if monthly_budget <= 0:
        return "GREEN"
    ratio = monthly_spend / monthly_budget
    if ratio >= 1.0:
        return "RED"
    if ratio >= 0.75:
        return "YELLOW"
    return "GREEN"


def load_personalization_context(session: Session, *, owner_user_id: int) -> CollectorPersonalizationContext:
    profile = get_collector_profile(session, owner_user_id=owner_user_id)
    budget = get_collector_budget(session, owner_user_id=owner_user_id)
    goals, _ = list_collector_goals(session, owner_user_id=owner_user_id, limit=50, offset=0)
    monthly_budget = float(budget.monthly_budget)
    monthly_spend = compute_monthly_spend(session, owner_user_id=owner_user_id)
    remaining = max(0.0, monthly_budget - monthly_spend) if monthly_budget > 0 else 0.0
    return CollectorPersonalizationContext(
        profile=profile,
        monthly_budget=monthly_budget,
        monthly_spend=monthly_spend,
        remaining_budget=remaining,
        budget_state=budget_state_for(monthly_budget=monthly_budget, monthly_spend=monthly_spend),
        goals=goals,
    )


def _text_haystack(*parts: str) -> str:
    return " ".join(p.strip().lower() for p in parts if p and p.strip())


def _interest_boost(ctx: CollectorPersonalizationContext, *, haystack: str) -> tuple[float, list[P77PersonalizationAdjustmentRead], list[str]]:
    adjustment = 0.0
    adjustments: list[P77PersonalizationAdjustmentRead] = []
    reasons: list[str] = []
    for item in ctx.profile.publishers:
        if item.label.lower() in haystack:
            delta = max(3.0, 9.0 - float(item.priority_rank))
            adjustment += delta
            adjustments.append(P77PersonalizationAdjustmentRead(label=f"Publisher: {item.label}", delta=delta))
            reasons.append(f"Preferred publisher ({item.label})")
    for item in ctx.profile.characters:
        if item.label.lower() in haystack:
            delta = max(4.0, 10.0 - float(item.priority_rank))
            adjustment += delta
            adjustments.append(P77PersonalizationAdjustmentRead(label=f"Character: {item.label}", delta=delta))
            reasons.append(f"Character focus ({item.label})")
    for item in ctx.profile.creators:
        if item.label.lower() in haystack:
            delta = 5.0
            adjustment += delta
            adjustments.append(P77PersonalizationAdjustmentRead(label=f"Creator: {item.label}", delta=delta))
            reasons.append(f"Preferred creator ({item.label})")
    return adjustment, adjustments, reasons


def _goal_boost(ctx: CollectorPersonalizationContext, *, haystack: str) -> tuple[float, float, list[P77PersonalizationAdjustmentRead], list[str]]:
    adjustment = 0.0
    alignment = 0.0
    adjustments: list[P77PersonalizationAdjustmentRead] = []
    reasons: list[str] = []
    for goal in ctx.goals:
        title = goal.title.strip().lower()
        if not title:
            continue
        if title in haystack or haystack in title:
            delta = 8.0 if goal.goal_type == "RUN_COMPLETION" else 6.0
            adjustment += delta
            alignment = max(alignment, min(100.0, goal.completion_percent))
            adjustments.append(P77PersonalizationAdjustmentRead(label=f"Goal: {goal.title}", delta=delta))
            reasons.append(f"Aligns with goal ({goal.title})")
        if goal.goal_type == "PUBLISHER_FOCUS" and title in haystack:
            adjustment += 6.0
            alignment = max(alignment, goal.completion_percent)
    return adjustment, alignment, adjustments, reasons


def personalize_score(
    ctx: CollectorPersonalizationContext,
    *,
    global_score: float,
    publisher: str = "",
    series_name: str = "",
    title: str = "",
    owned_copies: int = 0,
    gap_completion: bool = False,
    estimated_price: float = 0.0,
) -> tuple[float, float, float, float, list[P77PersonalizationAdjustmentRead], list[str]]:
    haystack = _text_haystack(publisher, series_name, title)
    collector_adj = 0.0
    all_adjustments: list[P77PersonalizationAdjustmentRead] = []
    reasons: list[str] = []

    interest_adj, interest_rows, interest_reasons = _interest_boost(ctx, haystack=haystack)
    collector_adj += interest_adj
    all_adjustments.extend(interest_rows)
    reasons.extend(interest_reasons)

    goal_adj, goal_alignment, goal_rows, goal_reasons = _goal_boost(ctx, haystack=haystack)
    collector_adj += goal_adj
    all_adjustments.extend(goal_rows)
    reasons.extend(goal_reasons)

    if gap_completion:
        collector_adj += 10.0
        all_adjustments.append(P77PersonalizationAdjustmentRead(label="Collection gap completion", delta=10.0))
        reasons.append("Fills collection gap")
        goal_alignment = max(goal_alignment, 90.0)

    if ctx.profile.time_horizon == "LONG_TERM" or ctx.profile.time_horizon == "LEGACY_COLLECTION":
        collector_adj += 3.0
        all_adjustments.append(P77PersonalizationAdjustmentRead(label="Long-term collector", delta=3.0))

    target = ctx.profile.default_copy_count
    if owned_copies > target:
        excess = owned_copies - target
        penalty = min(20.0, float(excess) * 4.0)
        collector_adj -= penalty
        all_adjustments.append(P77PersonalizationAdjustmentRead(label="Duplicate ownership", delta=-penalty))
        reasons.append(f"Already owns {owned_copies} copies (target {target})")

    budget_impact = 0.0
    if ctx.budget_state == "RED":
        collector_adj -= 8.0
        all_adjustments.append(P77PersonalizationAdjustmentRead(label="Budget exhausted", delta=-8.0))
        reasons.append("Budget exhausted")
        budget_impact = estimated_price
    elif ctx.budget_state == "YELLOW":
        collector_adj -= 4.0
        all_adjustments.append(P77PersonalizationAdjustmentRead(label="Budget pressure", delta=-4.0))
        reasons.append("Budget nearly exhausted")
        budget_impact = estimated_price * 0.5

    if ctx.profile.risk_profile == "CONSERVATIVE" and global_score >= 80:
        collector_adj -= 2.0
        all_adjustments.append(P77PersonalizationAdjustmentRead(label="Conservative risk profile", delta=-2.0))
    elif ctx.profile.risk_profile == "AGGRESSIVE" and global_score >= 70:
        collector_adj += 2.0
        all_adjustments.append(P77PersonalizationAdjustmentRead(label="Aggressive risk profile", delta=2.0))

    personalized = _clamp_score(global_score + collector_adj)
    return personalized, collector_adj, goal_alignment, budget_impact, all_adjustments, reasons


def recommend_personalized_quantity(
    ctx: CollectorPersonalizationContext,
    *,
    global_quantity: int,
    global_score: float,
    owned_copies: int = 0,
    is_key_issue: bool = False,
) -> tuple[int, list[str]]:
    base = ctx.profile.key_issue_copy_count if is_key_issue else ctx.profile.default_copy_count
    if ctx.profile.risk_profile == "CONSERVATIVE":
        base = max(1, base - 1)
    elif ctx.profile.risk_profile == "AGGRESSIVE":
        base = min(5, base + 1)
    if ctx.profile.collector_type in {"INVESTOR", "SPECULATOR"} and global_score >= 85:
        base = min(5, base + 1)
    if ctx.budget_state == "RED":
        base = min(base, 1)
    elif ctx.budget_state == "YELLOW":
        base = min(base, max(1, ctx.profile.default_copy_count))
    needed = max(0, base - owned_copies)
    if global_quantity > 0:
        needed = min(needed, global_quantity) if ctx.profile.risk_profile != "AGGRESSIVE" else max(needed, min(global_quantity, base))
    reasons = [f"Profile target {base} copies", f"Owned {owned_copies}"]
    if ctx.budget_state != "GREEN":
        reasons.append(f"Budget state {ctx.budget_state}")
    return int(needed), reasons


def build_scan_personalization(
    ctx: CollectorPersonalizationContext,
    *,
    global_score: float | None,
    publisher: str,
    series_name: str,
    title: str,
    owned_copies: int,
    gap_completion: bool,
    estimated_fmv: float | None,
) -> P77PersonalizationSnapshotRead:
    base = float(global_score or 0.0)
    price = float(estimated_fmv or 0.0)
    personalized, adj, goal_alignment, budget_impact, _, reasons = personalize_score(
        ctx,
        global_score=base,
        publisher=publisher,
        series_name=series_name,
        title=title,
        owned_copies=owned_copies,
        gap_completion=gap_completion,
        estimated_price=price,
    )
    qty, qty_reasons = recommend_personalized_quantity(
        ctx,
        global_quantity=ctx.profile.default_copy_count,
        global_score=personalized,
        owned_copies=owned_copies,
        is_key_issue=False,
    )
    return P77PersonalizationSnapshotRead(
        global_score=base if global_score is not None else None,
        collector_adjustment=round(adj, 1),
        personalized_score=personalized,
        budget_impact=round(budget_impact, 2),
        goal_alignment=round(goal_alignment, 1),
        quantity_recommendation=qty,
        budget_state=ctx.budget_state,  # type: ignore[arg-type]
        reasons=(reasons + qty_reasons)[:8],
    )
