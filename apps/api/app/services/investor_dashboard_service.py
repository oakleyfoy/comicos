"""P67-05 Investor dashboard — aggregates latest P67 snapshots."""

from __future__ import annotations

from datetime import date

from sqlmodel import Session, select

from app.models.portfolio_analytics_platform import P67InvestorDashboardSnapshot, utc_now
from app.services.collection_analytics_service import get_latest_collection_analytics_snapshot
from app.services.grading_analytics_service import get_latest_grading_opportunity_snapshot, list_grading_opportunity_items
from app.services.portfolio_analytics_service import get_latest_portfolio_analytics_snapshot, list_portfolio_analytics_items
from app.services.recommendation_performance_service import (
    get_latest_recommendation_performance_snapshot,
    list_recommendation_performance_items,
)


def get_latest_investor_dashboard_snapshot(session: Session, *, owner_user_id: int) -> P67InvestorDashboardSnapshot | None:
    return session.exec(
        select(P67InvestorDashboardSnapshot)
        .where(P67InvestorDashboardSnapshot.owner_user_id == owner_user_id)
        .order_by(P67InvestorDashboardSnapshot.generated_at.desc(), P67InvestorDashboardSnapshot.id.desc())
    ).first()


def build_investor_dashboard_snapshot(session: Session, *, owner_user_id: int) -> P67InvestorDashboardSnapshot:
    today = date.today()
    perf = get_latest_portfolio_analytics_snapshot(session, owner_user_id=owner_user_id)
    coll = get_latest_collection_analytics_snapshot(session, owner_user_id=owner_user_id)
    rec = get_latest_recommendation_performance_snapshot(session, owner_user_id=owner_user_id)
    grade = get_latest_grading_opportunity_snapshot(session, owner_user_id=owner_user_id)

    winners: list[dict] = []
    losers: list[dict] = []
    largest: list[dict] = []
    grading_top: list[dict] = []
    rec_scorecard: dict = {}

    if perf:
        items = list_portfolio_analytics_items(session, snapshot_id=int(perf.id or 0), limit=50)
        for item in sorted(items, key=lambda i: i.unrealized_gain_pct, reverse=True)[:5]:
            winners.append({"title": item.title, "roi_pct": item.roi_pct, "gain": item.unrealized_gain})
        for item in sorted(items, key=lambda i: i.unrealized_gain_pct)[:5]:
            losers.append({"title": item.title, "roi_pct": item.roi_pct, "gain": item.unrealized_gain})
        for item in sorted(items, key=lambda i: i.estimated_value, reverse=True)[:5]:
            largest.append({"title": item.title, "value": item.estimated_value})

    if grade:
        for g in list_grading_opportunity_items(session, snapshot_id=int(grade.id or 0), limit=8):
            grading_top.append({"title": g.title, "estimated_roi_pct": g.estimated_roi_pct, "priority": g.submission_priority})

    if rec:
        rec_scorecard = {
            "hit_rate_pct": rec.hit_rate_pct,
            "average_return_pct": rec.average_return_pct,
            "recommendation_roi_pct": rec.recommendation_roi_pct,
            "confidence_accuracy_pct": rec.confidence_accuracy_pct,
            "best": rec.best_recommendation_title,
            "worst": rec.worst_recommendation_title,
        }

    health = 50.0
    if perf and perf.total_cost_basis > 0:
        health += min(30.0, perf.total_unrealized_gain_pct * 0.5)
    if coll:
        health += min(20.0, coll.metadata_json.get("diversification_score", 0) * 0.2)

    snap = P67InvestorDashboardSnapshot(
        owner_user_id=owner_user_id,
        snapshot_date=today,
        generated_at=utc_now(),
        collection_value=float(perf.total_estimated_value if perf else 0),
        cost_basis=float(perf.total_cost_basis if perf else 0),
        unrealized_gain=float(perf.total_unrealized_gain if perf else 0),
        realized_gain=float(perf.total_realized_gain if perf else 0),
        portfolio_health_score=round(min(100.0, health), 2),
        cards_json={
            "best_winners": winners,
            "worst_losers": losers,
            "top_grading_opportunities": grading_top,
            "recommendation_scorecard": rec_scorecard,
            "largest_holdings": largest,
            "collection_concentration": coll.concentration_score if coll else None,
        },
    )
    session.add(snap)
    session.flush()
    return snap
