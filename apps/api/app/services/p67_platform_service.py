"""P67 platform build orchestration."""

from __future__ import annotations

from sqlmodel import Session

from app.services.collection_analytics_service import build_collection_analytics_snapshot
from app.services.grading_analytics_service import build_grading_opportunity_snapshot
from app.services.investor_dashboard_service import build_investor_dashboard_snapshot
from app.services.portfolio_analytics_service import build_portfolio_analytics_snapshot
from app.services.recommendation_performance_service import build_recommendation_performance_snapshot


def run_p67_platform_build(session: Session, *, owner_user_id: int) -> dict:
    perf = build_portfolio_analytics_snapshot(session, owner_user_id=owner_user_id)
    coll = build_collection_analytics_snapshot(session, owner_user_id=owner_user_id)
    rec = build_recommendation_performance_snapshot(session, owner_user_id=owner_user_id)
    grade = build_grading_opportunity_snapshot(session, owner_user_id=owner_user_id)
    dash = build_investor_dashboard_snapshot(session, owner_user_id=owner_user_id)
    return {
        "steps": [
            {"step": "portfolio_analytics", "snapshot_id": int(perf.id or 0)},
            {"step": "collection_analytics", "snapshot_id": int(coll.id or 0)},
            {"step": "recommendation_performance", "snapshot_id": int(rec.id or 0)},
            {"step": "grading_analytics", "snapshot_id": int(grade.id or 0)},
            {"step": "investor_dashboard", "snapshot_id": int(dash.id or 0)},
        ],
        "portfolio_performance_snapshot_id": int(perf.id or 0),
        "collection_analytics_snapshot_id": int(coll.id or 0),
        "recommendation_performance_snapshot_id": int(rec.id or 0),
        "grading_opportunity_snapshot_id": int(grade.id or 0),
        "investor_dashboard_snapshot_id": int(dash.id or 0),
    }
