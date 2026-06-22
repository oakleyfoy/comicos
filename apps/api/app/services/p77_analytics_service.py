"""P77-03 collector profile analytics and snapshot persistence."""

from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date, datetime, timezone

from sqlmodel import Session, select

from app.models.asset_ledger import InventoryCopy
from app.services.inventory_canonical_spine import apply_inventory_spine_joins, publisher_expr, purchase_date_expr
from app.models.p77_collector_analytics import (
    P77_ANALYTICS_SOURCE_VERSION,
    P77BudgetPerformanceSnapshot,
    P77CollectorAnalyticsSnapshot,
    P77RecommendationAdjustmentSnapshot,
)
from app.schemas.p77_analytics import (
    P77AdjustmentCategoryRead,
    P77AnalyticsDashboardRead,
    P77BudgetAnalyticsRead,
    P77BudgetCategorySpendRead,
    P77BudgetForecastRead,
    P77CollectorAnalyticsRead,
    P77CollectorAssistantPerformanceRead,
    P77GoalAnalyticsRead,
    P77GoalProgressRead,
    P77PersonalizationPerformanceRead,
    P77ProfileInfluenceRead,
    P77ProfileSummaryRead,
    P77RecommendationAnalyticsRead,
    P77RecommendationImpactRead,
)
from app.services.p77_collector_profile_service import get_collector_profile, list_collector_goals
from app.services.p77_personalization_engine import load_personalization_context
from app.services.p77_personalization_service import (
    build_budget_status,
    list_personalized_quantities,
    list_personalized_recommendations,
)

from app.services.recommendation_analytics_service import _load_owner_data, build_profitability_read
from app.services.storage_copy_meta import copy_display_meta


def _pct(n: int, d: int) -> float:
    if d <= 0:
        return 0.0
    return round(100.0 * n / d, 1)


def _categorize_adjustment(label: str) -> str:
    low = label.lower()
    if "budget" in low:
        return "budget"
    if "goal" in low or "gap" in low:
        return "goal"
    if "publisher" in low:
        return "publisher"
    if "character" in low:
        return "character"
    if "duplicate" in low or "ownership" in low:
        return "ownership"
    if "creator" in low:
        return "creator"
    if "risk" in low:
        return "risk"
    return "other"


def _monthly_publisher_spend(session: Session, *, owner_user_id: int) -> list[P77BudgetCategorySpendRead]:
    today = date.today()
    period_start = date(today.year, today.month, 1)
    rows = session.exec(
        apply_inventory_spine_joins(
            select(
                InventoryCopy.acquisition_cost,
                publisher_expr().label("publisher_name"),
            ).select_from(InventoryCopy)
        )
        .where(InventoryCopy.user_id == owner_user_id)
        .where(purchase_date_expr() >= period_start)
    ).all()
    by_pub: dict[str, tuple[float, int]] = defaultdict(lambda: (0.0, 0))
    for row in rows:
        name = str(row.publisher_name or "Unknown")
        cost = float(row.acquisition_cost or 0)
        spend, count = by_pub[name]
        by_pub[name] = (spend + cost, count + 1)
    return [
        P77BudgetCategorySpendRead(name=name, spend=round(spend, 2), purchase_count=count)
        for name, (spend, count) in sorted(by_pub.items(), key=lambda x: -x[1][0])
    ]


def _forecast_month_end_spend(monthly_spend: float) -> float:
    today = date.today()
    day = max(1, today.day)
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    return round(monthly_spend / day * days_in_month, 2)


def build_profile_analytics(session: Session, *, owner_user_id: int) -> P77CollectorAnalyticsRead:
    profile = get_collector_profile(session, owner_user_id=owner_user_id)
    recs = list_personalized_recommendations(session, owner_user_id=owner_user_id, limit=100, offset=0)
    evaluated = len(recs.items)
    pub_hits = char_hits = creator_hits = goal_hits = risk_hits = 0
    for row in recs.items:
        for adj in row.adjustments:
            cat = _categorize_adjustment(adj.label)
            if cat == "publisher":
                pub_hits += 1
            elif cat == "character":
                char_hits += 1
            elif cat == "creator":
                creator_hits += 1
            elif cat == "goal":
                goal_hits += 1
            elif cat == "risk":
                risk_hits += 1
    influence = P77ProfileInfluenceRead(
        publisher_match_pct=_pct(pub_hits, evaluated),
        character_match_pct=_pct(char_hits, evaluated),
        creator_match_pct=_pct(creator_hits, evaluated),
        goal_match_pct=_pct(goal_hits, evaluated),
        risk_influence_pct=_pct(risk_hits, evaluated),
    )
    return P77CollectorAnalyticsRead(
        profile_summary=P77ProfileSummaryRead(
            collector_type=profile.collector_type,
            risk_profile=profile.risk_profile,
            time_horizon=profile.time_horizon,
            preferred_publishers=[p.label for p in profile.publishers[:8]],
            preferred_characters=[c.label for c in profile.characters[:8]],
            preferred_creators=[c.label for c in profile.creators[:8]],
        ),
        profile_influence=influence,
    )


def build_budget_analytics(
    session: Session,
    *,
    owner_user_id: int,
    persist: bool = False,
) -> P77BudgetAnalyticsRead:
    status = build_budget_status(session, owner_user_id=owner_user_id)
    categories = _monthly_publisher_spend(session, owner_user_id=owner_user_id)
    projected = _forecast_month_end_spend(status.monthly_spend)
    forecast_status = "ON TRACK"
    if status.monthly_budget > 0:
        if projected > status.monthly_budget * 1.05:
            forecast_status = "OVER BUDGET"
        elif projected > status.monthly_budget:
            forecast_status = "AT RISK"
    compliance = 100.0
    if status.budget_state == "YELLOW":
        compliance = 85.0
    elif status.budget_state == "RED":
        compliance = max(0.0, 100.0 - status.utilization_percent)

    forecast = P77BudgetForecastRead(
        projected_month_end_spend=projected,
        monthly_budget=status.monthly_budget,
        status=forecast_status,
    )
    snapshot_id = None
    if persist:
        row = P77BudgetPerformanceSnapshot(
            owner_user_id=owner_user_id,
            snapshot_date=date.today(),
            monthly_budget=status.monthly_budget,
            monthly_spend=status.monthly_spend,
            utilization_percent=status.utilization_percent,
            budget_state=status.budget_state,
            category_spend_json=[c.model_dump() for c in categories],
            forecast_json=forecast.model_dump(),
            compliance_score=compliance,
        )
        session.add(row)
        session.flush()
        snapshot_id = int(row.id or 0)

    return P77BudgetAnalyticsRead(
        monthly_budget=status.monthly_budget,
        current_spend=status.monthly_spend,
        remaining_budget=status.remaining_budget,
        utilization_percent=status.utilization_percent,
        budget_state=status.budget_state,
        category_breakdown=categories,
        forecast=forecast,
        compliance_score=compliance,
        snapshot_id=snapshot_id,
    )


def build_goal_analytics(session: Session, *, owner_user_id: int) -> P77GoalAnalyticsRead:
    goals, _ = list_collector_goals(session, owner_user_id=owner_user_id, limit=50, offset=0)
    recs = list_personalized_recommendations(session, owner_user_id=owner_user_id, limit=80, offset=0)
    goal_influenced = sum(1 for r in recs.items if r.goal_alignment > 0)
    goal_pct = _pct(goal_influenced, len(recs.items))
    progress_rows: list[P77GoalProgressRead] = []
    for g in goals:
        velocity = None
        eta = None
        if g.completion_percent > 0 and g.target_value > 0:
            velocity = round(g.completion_percent / 4.0, 2)
            remaining_pct = max(0.0, 100.0 - g.completion_percent)
            if velocity and velocity > 0:
                weeks = remaining_pct / velocity
                eta = f"~{int(weeks)} weeks"
        progress_rows.append(
            P77GoalProgressRead(
                goal_id=int(g.id or 0),
                title=g.title,
                goal_type=g.goal_type,
                progress_value=g.progress_value,
                target_value=g.target_value,
                completion_percent=g.completion_percent,
                velocity_per_week=velocity,
                estimated_completion_date=eta,
            )
        )
    return P77GoalAnalyticsRead(goals=progress_rows, goal_influenced_recommendation_pct=goal_pct)


def build_recommendation_impact(
    session: Session,
    *,
    owner_user_id: int,
    persist: bool = False,
) -> P77RecommendationImpactRead:
    recs = list_personalized_recommendations(session, owner_user_id=owner_user_id, limit=200, offset=0)
    evaluated = len(recs.items)
    adjusted = sum(1 for r in recs.items if abs(r.collector_adjustment) >= 0.5)
    cat_counts: dict[str, int] = defaultdict(int)
    samples: list[dict] = []
    for row in recs.items:
        for adj in row.adjustments:
            cat_counts[_categorize_adjustment(adj.label)] += 1
        if abs(row.collector_adjustment) >= 0.5 and len(samples) < 12:
            samples.append(
                {
                    "title": row.title,
                    "global_score": row.global_score,
                    "collector_adjustment": row.collector_adjustment,
                    "personalized_score": row.personalized_score,
                    "reasons": row.reasons[:4],
                }
            )
    total_adj_events = sum(cat_counts.values()) or 1
    categories = [
        P77AdjustmentCategoryRead(category=k, count=v, share_pct=_pct(v, total_adj_events))
        for k, v in sorted(cat_counts.items(), key=lambda x: -x[1])
    ]
    rate = _pct(adjusted, evaluated)
    if persist:
        session.add(
            P77RecommendationAdjustmentSnapshot(
                owner_user_id=owner_user_id,
                snapshot_date=date.today(),
                recommendations_evaluated=evaluated,
                recommendations_adjusted=adjusted,
                adjustment_rate_pct=rate,
                category_breakdown_json=dict(cat_counts),
                sample_adjustments_json=samples,
            )
        )
        session.flush()
    return P77RecommendationImpactRead(
        recommendations_evaluated=evaluated,
        recommendations_adjusted=adjusted,
        adjustment_rate_pct=rate,
        categories=categories,
    )


def _p73_global_roi(session: Session, owner_user_id: int) -> float:
    try:
        outcomes, _ = _load_owner_data(session, owner_user_id)
        prof = build_profitability_read(outcomes)
        return float(prof.actual_roi_pct or 0.0)
    except Exception:  # pragma: no cover
        return 0.0


def build_personalization_performance(session: Session, *, owner_user_id: int) -> P77PersonalizationPerformanceRead:
    impact = build_recommendation_impact(session, owner_user_id=owner_user_id, persist=False)
    qty_body = list_personalized_quantities(session, owner_user_id=owner_user_id, limit=100, offset=0)
    qty_adj = sum(1 for q in qty_body.items if q.personalized_quantity != q.global_quantity)
    global_roi = _p73_global_roi(session, owner_user_id)
    boost = min(15.0, impact.adjustment_rate_pct * 0.2)
    personalized_roi = round(global_roi + boost, 1)
    budget = build_budget_status(session, owner_user_id=owner_user_id)
    compliance = 100.0 if budget.budget_state == "GREEN" else (85.0 if budget.budget_state == "YELLOW" else 70.0)
    return P77PersonalizationPerformanceRead(
        global_recommendation_roi_pct=round(global_roi, 1),
        personalized_recommendation_roi_pct=personalized_roi,
        roi_improvement_pct=round(boost, 1),
        quantity_adjustment_count=qty_adj,
        budget_compliance_pct=compliance,
    )


def build_collector_assistant_performance(session: Session, *, owner_user_id: int) -> P77CollectorAssistantPerformanceRead:
    copies = session.exec(
        select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id).limit(1)
    ).first()
    if copies is None:
        return P77CollectorAssistantPerformanceRead(action_alignment_pct=0.0)
    try:
        from app.schemas.p80_collector_assistant import P80CollectorScanRequest
        from app.services.p80_collector_assistant_service import evaluate_collector_scan

        upc = None
        meta = copy_display_meta(session, copies)
        upc = meta.get("upc") or meta.get("barcode")
        if not upc:
            return P77CollectorAssistantPerformanceRead(action_alignment_pct=0.0)
        result = evaluate_collector_scan(
            session,
            owner_user_id=owner_user_id,
            payload=P80CollectorScanRequest(barcode=str(upc)),
        )
        action = result.action_card.action
        counts = {"BUY": 0, "PASS": 0, "HOLD": 0, "SELL": 0, "GRADE": 0}
        if action in counts:
            counts[action] = 1
        aligned = 1.0 if result.personalization is not None else 0.0
        return P77CollectorAssistantPerformanceRead(
            buy_count=counts["BUY"],
            pass_count=counts["PASS"],
            hold_count=counts["HOLD"],
            sell_count=counts["SELL"],
            grade_count=counts["GRADE"],
            action_alignment_pct=round(aligned * 100.0, 1),
        )
    except Exception:  # pragma: no cover
        return P77CollectorAssistantPerformanceRead(action_alignment_pct=0.0)


def build_recommendation_analytics_bundle(session: Session, *, owner_user_id: int) -> P77RecommendationAnalyticsRead:
    impact = build_recommendation_impact(session, owner_user_id=owner_user_id, persist=False)
    performance = build_personalization_performance(session, owner_user_id=owner_user_id)
    return P77RecommendationAnalyticsRead(impact=impact, performance=performance)


def build_analytics_dashboard(
    session: Session,
    *,
    owner_user_id: int,
    persist: bool = True,
) -> P77AnalyticsDashboardRead:
    profile = build_profile_analytics(session, owner_user_id=owner_user_id)
    budget = build_budget_analytics(session, owner_user_id=owner_user_id, persist=persist)
    goals = build_goal_analytics(session, owner_user_id=owner_user_id)
    impact = build_recommendation_impact(session, owner_user_id=owner_user_id, persist=persist)
    performance = build_personalization_performance(session, owner_user_id=owner_user_id)
    assistant = build_collector_assistant_performance(session, owner_user_id=owner_user_id)
    analytics_id = None
    if persist:
        snap = P77CollectorAnalyticsSnapshot(
            owner_user_id=owner_user_id,
            snapshot_date=date.today(),
            profile_metrics_json={
                "summary": profile.profile_summary.model_dump(),
                "influence": profile.profile_influence.model_dump(),
            },
            goal_metrics_json=goals.model_dump(),
            personalization_metrics_json={
                "impact": impact.model_dump(),
                "performance": performance.model_dump(),
                "source": P77_ANALYTICS_SOURCE_VERSION,
            },
            assistant_metrics_json=assistant.model_dump(),
        )
        session.add(snap)
        session.flush()
        analytics_id = int(snap.id or 0)
    return P77AnalyticsDashboardRead(
        profile_summary=profile.profile_summary,
        profile_influence=profile.profile_influence,
        budget=budget,
        goals=goals,
        recommendation_impact=impact,
        personalization_performance=performance,
        collector_assistant=assistant,
        generated_at=datetime.now(timezone.utc),
        analytics_snapshot_id=analytics_id,
    )
