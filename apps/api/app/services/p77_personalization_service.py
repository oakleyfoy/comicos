"""P77-02 personalized recommendation and quantity list services."""

from __future__ import annotations

from app.schemas.p77_personalization import (
    P77BudgetStatusRead,
    P77PersonalizationSnapshotRead,
    P77PersonalizedDashboardRead,
    P77PersonalizedQuantityListResponse,
    P77PersonalizedQuantityRead,
    P77PersonalizedRecommendationListResponse,
    P77PersonalizedRecommendationRead,
)
from app.services.acquisition_opportunities import refresh_and_list_latest_acquisition_opportunities
from app.services.p77_personalization_engine import (
    load_personalization_context,
    personalize_score,
    recommend_personalized_quantity,
)
from app.services.purchase_quantities import list_latest_purchase_quantity_recommendations
from app.services.unified_collector_intelligence import list_latest_unified_collector_recommendations
from sqlmodel import Session


def build_budget_status(session: Session, *, owner_user_id: int) -> P77BudgetStatusRead:
    ctx = load_personalization_context(session, owner_user_id=owner_user_id)
    utilization = (
        round(100.0 * ctx.monthly_spend / ctx.monthly_budget, 1) if ctx.monthly_budget > 0 else 0.0
    )
    return P77BudgetStatusRead(
        monthly_budget=ctx.monthly_budget,
        monthly_spend=ctx.monthly_spend,
        remaining_budget=ctx.remaining_budget,
        projected_spend=0.0,
        utilization_percent=utilization,
        budget_state=ctx.budget_state,  # type: ignore[arg-type]
    )


def list_personalized_recommendations(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 25,
    offset: int = 0,
    apply_budget_filter: bool = True,
) -> P77PersonalizedRecommendationListResponse:
    ctx = load_personalization_context(session, owner_user_id=owner_user_id)
    lim = max(1, min(limit, 100))
    off = max(0, offset)
    candidates: list[P77PersonalizedRecommendationRead] = []

    unified, _ = list_latest_unified_collector_recommendations(
        session, owner_user_id=owner_user_id, limit=60, offset=0
    )
    for row in unified:
        global_score = float(row.priority_score)
        personalized, adj, goal_alignment, budget_impact, adjustments, reasons = personalize_score(
            ctx,
            global_score=global_score,
            title=row.title,
            estimated_price=20.0,
        )
        candidates.append(
            P77PersonalizedRecommendationRead(
                source="P51_unified",
                title=row.title,
                subtitle=row.recommendation_type,
                global_score=global_score,
                collector_adjustment=round(adj, 1),
                personalized_score=personalized,
                budget_impact=round(budget_impact, 2),
                goal_alignment=round(goal_alignment, 1),
                quantity_recommendation=recommend_personalized_quantity(
                    ctx, global_quantity=2, global_score=personalized
                )[0],
                reasons=reasons[:6],
                adjustments=adjustments[:8],
            )
        )

    acq, _ = refresh_and_list_latest_acquisition_opportunities(
        session, owner_user_id=owner_user_id, limit=60, offset=0
    )
    for row in acq:
        global_score = float(row.priority_score)
        price = float(row.estimated_fmv or row.target_price or 15.0)
        title = f"{row.series_name} #{row.issue_number}".strip()
        personalized, adj, goal_alignment, budget_impact, adjustments, reasons = personalize_score(
            ctx,
            global_score=global_score,
            publisher=row.publisher,
            series_name=row.series_name,
            title=title,
            estimated_price=price,
        )
        candidates.append(
            P77PersonalizedRecommendationRead(
                source="P55_acquisition",
                title=title or row.series_name,
                subtitle=row.opportunity_type,
                global_score=global_score,
                collector_adjustment=round(adj, 1),
                personalized_score=personalized,
                budget_impact=round(budget_impact, 2),
                goal_alignment=round(goal_alignment, 1),
                quantity_recommendation=recommend_personalized_quantity(
                    ctx, global_quantity=2, global_score=personalized
                )[0],
                reasons=reasons[:6],
                adjustments=adjustments[:8],
            )
        )

    candidates.sort(key=lambda r: (-r.personalized_score, r.title.lower()))
    filtered = candidates
    estimated_spend = 0.0
    budget_filtered_count = 0
    if apply_budget_filter and ctx.monthly_budget > 0 and ctx.budget_state != "GREEN":
        cap = 8 if ctx.budget_state == "RED" else 15
        picked: list[P77PersonalizedRecommendationRead] = []
        spend = 0.0
        for item in candidates:
            if len(picked) >= cap:
                budget_filtered_count += 1
                continue
            price = max(5.0, item.budget_impact or 15.0)
            if spend + price > ctx.remaining_budget and ctx.remaining_budget > 0:
                budget_filtered_count += 1
                continue
            spend += price
            picked.append(item)
        filtered = picked
        estimated_spend = round(spend, 2)
    else:
        estimated_spend = round(sum(max(5.0, c.budget_impact or 15.0) for c in candidates[:8]), 2)

    total = len(filtered)
    page = filtered[off : off + lim]
    return P77PersonalizedRecommendationListResponse(
        items=page,
        total_items=total,
        limit=lim,
        offset=off,
        estimated_spend=estimated_spend,
        budget_filtered_count=budget_filtered_count,
    )


def list_personalized_quantities(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 25,
    offset: int = 0,
) -> P77PersonalizedQuantityListResponse:
    ctx = load_personalization_context(session, owner_user_id=owner_user_id)
    lim = max(1, min(limit, 100))
    off = max(0, offset)
    rows, total = list_latest_purchase_quantity_recommendations(
        session, owner_user_id=owner_user_id, limit=100, offset=0
    )
    items: list[P77PersonalizedQuantityRead] = []
    for row in rows:
        global_score = float(row.confidence_score) * 100.0
        personalized, _, _, _, _, reasons = personalize_score(
            ctx,
            global_score=global_score,
            publisher=row.publisher,
            series_name=row.series_name,
            title=row.title,
        )
        pq, qty_reasons = recommend_personalized_quantity(
            ctx,
            global_quantity=int(row.quantity_recommended),
            global_score=personalized,
            is_key_issue=row.recommendation_tier in {"STRONG_BUY", "MUST_BUY"},
        )
        items.append(
            P77PersonalizedQuantityRead(
                release_id=row.release_id,
                title=row.title or f"{row.series_name} #{row.issue_number}",
                series_name=row.series_name,
                publisher=row.publisher,
                global_quantity=int(row.quantity_recommended),
                personalized_quantity=pq,
                global_score=global_score,
                personalized_score=personalized,
                reasons=(reasons + qty_reasons)[:6],
            )
        )
    items.sort(key=lambda r: (-r.personalized_score, r.title.lower()))
    total_items = len(items)
    return P77PersonalizedQuantityListResponse(
        items=items[off : off + lim],
        total_items=total_items,
        limit=lim,
        offset=off,
    )


def build_personalized_dashboard(session: Session, *, owner_user_id: int) -> P77PersonalizedDashboardRead:
    ctx = load_personalization_context(session, owner_user_id=owner_user_id)
    recs = list_personalized_recommendations(session, owner_user_id=owner_user_id, limit=8, offset=0)
    qty = list_personalized_quantities(session, owner_user_id=owner_user_id, limit=6, offset=0)
    status = build_budget_status(session, owner_user_id=owner_user_id)
    status.projected_spend = recs.estimated_spend
    return P77PersonalizedDashboardRead(
        budget_status=status,
        top_recommendations=recs.items,
        quantity_highlights=qty.items,
        profile_summary={
            "collector_type": ctx.profile.collector_type,
            "risk_profile": ctx.profile.risk_profile,
            "default_copy_count": ctx.profile.default_copy_count,
            "goal_count": len(ctx.goals),
        },
    )


def personalization_for_scan(
    session: Session,
    *,
    owner_user_id: int,
    global_score: float | None,
    publisher: str,
    series_name: str,
    title: str,
    owned_copies: int,
    gap_completion: bool,
    estimated_fmv: float | None,
) -> P77PersonalizationSnapshotRead:
    from app.services.p77_personalization_engine import build_scan_personalization

    ctx = load_personalization_context(session, owner_user_id=owner_user_id)
    return build_scan_personalization(
        ctx,
        global_score=global_score,
        publisher=publisher,
        series_name=series_name,
        title=title,
        owned_copies=owned_copies,
        gap_completion=gap_completion,
        estimated_fmv=estimated_fmv,
    )
