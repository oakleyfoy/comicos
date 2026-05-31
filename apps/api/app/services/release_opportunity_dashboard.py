from __future__ import annotations



from sqlmodel import Session



from app.schemas.release_platform import ReleaseOpportunityDashboardRead

from app.services.continue_run_planning import build_continue_run_planning

from app.services.future_buy_queue import build_future_buy_queue

from app.services.opportunity_intelligence import build_opportunity_intelligence

from app.services.release_budget_planner import build_budget_forecast

from app.services.release_horizon_engine import build_release_horizons
from app.services.release_variant_metrics import (
    count_cover_variants_for_owner,
    count_ratio_variants_for_owner,
    count_variants_for_owner,
    list_recent_variants,
    list_top_ratio_variants,
)





def build_release_opportunity_dashboard(session: Session, *, owner_user_id: int) -> ReleaseOpportunityDashboardRead:

    horizons = build_release_horizons(session, owner_user_id=owner_user_id)

    opportunities = build_opportunity_intelligence(session, owner_user_id=owner_user_id)

    queue = build_future_buy_queue(session, owner_user_id=owner_user_id)

    budget = build_budget_forecast(session, owner_user_id=owner_user_id)

    run_plans = build_continue_run_planning(session, owner_user_id=owner_user_id)

    continue_alerts = [plan for plan in run_plans if plan.plan_type == "CONTINUE_RUN"][:20]

    start_following = [plan for plan in run_plans if plan.plan_type == "START_FOLLOWING"][:20]

    new_opportunities = [plan for plan in run_plans if plan.plan_type == "NEW_OPPORTUNITY"][:20]



    return ReleaseOpportunityDashboardRead(

        new_announcements=horizons.announced[:20],

        next_30_days=horizons.next_30_days[:20],

        next_60_days=horizons.next_60_days[:20],

        next_90_days=horizons.next_90_days[:20],

        continue_run_alerts=continue_alerts,

        start_following_alerts=start_following,

        new_opportunity_alerts=new_opportunities,

        top_new_number_ones=opportunities.top_new_number_ones[:15],

        top_first_appearances=opportunities.top_first_appearances[:15],

        top_milestone_issues=opportunities.top_milestone_books[:15],

        top_variants=opportunities.top_variant_opportunities[:15],

        top_spec_opportunities=opportunities.top_spec_opportunities[:15],

        future_buy_queue=queue,

        budget_forecast=budget,

        variant_count=count_variants_for_owner(session, owner_user_id=owner_user_id),

        ratio_variant_count=count_ratio_variants_for_owner(session, owner_user_id=owner_user_id),

        cover_variant_count=count_cover_variants_for_owner(session, owner_user_id=owner_user_id),

        top_ratio_variants=list_top_ratio_variants(session, owner_user_id=owner_user_id, limit=15),

        top_new_variants=list_recent_variants(session, owner_user_id=owner_user_id, limit=15),

    )

