"""P71-05 Investor sell dashboard."""

from __future__ import annotations

from datetime import date

from sqlmodel import Session, select

from app.models.sell_intelligence_platform import (
    EXIT_SELL_NOW,
    EXIT_TRIM,
    LIQ_LOW,
    P71InvestorSellDashboardSnapshot,
    utc_now,
)
from app.services.exit_queue_service import get_latest_exit_queue_snapshot, list_exit_queue_items
from app.services.exit_recommendation_service import get_latest_exit_recommendation_snapshot, list_exit_recommendation_items
from app.services.liquidity_intelligence_service import get_latest_liquidity_snapshot, list_liquidity_items
from app.services.p71_sell_context import load_sell_intel_contexts


def get_latest_investor_sell_dashboard(session: Session, *, owner_user_id: int) -> P71InvestorSellDashboardSnapshot | None:
    return session.exec(
        select(P71InvestorSellDashboardSnapshot)
        .where(P71InvestorSellDashboardSnapshot.owner_user_id == owner_user_id)
        .order_by(P71InvestorSellDashboardSnapshot.generated_at.desc(), P71InvestorSellDashboardSnapshot.id.desc())
    ).first()


def build_investor_sell_dashboard_snapshot(session: Session, *, owner_user_id: int) -> P71InvestorSellDashboardSnapshot:
    today = date.today()
    contexts = load_sell_intel_contexts(session, owner_user_id=owner_user_id)
    exit_snap = get_latest_exit_recommendation_snapshot(session, owner_user_id=owner_user_id)
    liq_snap = get_latest_liquidity_snapshot(session, owner_user_id=owner_user_id)
    queue_snap = get_latest_exit_queue_snapshot(session, owner_user_id=owner_user_id)

    exit_items = list_exit_recommendation_items(session, snapshot_id=int(exit_snap.id or 0)) if exit_snap else []
    liq_items = list_liquidity_items(session, snapshot_id=int(liq_snap.id or 0)) if liq_snap else []
    queue_items = list_exit_queue_items(session, snapshot_id=int(queue_snap.id or 0)) if queue_snap else []

    top_sell = [
        {"title": i.title, "action": i.recommendation, "score": i.exit_score}
        for i in sorted(exit_items, key=lambda x: x.exit_score, reverse=True)[:5]
    ]
    largest_gains = sorted(
        [{"title": c.title, "gain": round(c.unrealized_gain, 2), "roi_pct": round(c.unrealized_gain_pct, 1)} for c in contexts],
        key=lambda x: x["gain"],
        reverse=True,
    )[:5]
    largest_positions = sorted(
        [{"title": c.title, "fmv": round(c.estimated_fmv, 2)} for c in contexts if c.estimated_fmv > 0],
        key=lambda x: x["fmv"],
        reverse=True,
    )[:5]
    concentration = [
        {"title": c.title, "share_pct": round(c.portfolio_share_pct, 1)}
        for c in sorted(contexts, key=lambda x: x.portfolio_share_pct, reverse=True)[:5]
        if c.portfolio_share_pct >= 5
    ]
    illiquid = [{"title": i.title, "band": i.liquidity_band} for i in liq_items if i.liquidity_band == LIQ_LOW][:5]
    fast = [{"title": i.title, "days": i.days_to_sell_estimate} for i in sorted(liq_items, key=lambda x: x.days_to_sell_estimate)[:5]]
    expected_profit = sum(float(q.expected_profit) for q in queue_items if q.recommended_action in (EXIT_SELL_NOW, EXIT_TRIM))

    cards = {
        "top_sell_opportunities": top_sell,
        "largest_gains": largest_gains,
        "largest_positions": largest_positions,
        "concentration_risks": concentration,
        "illiquid_positions": illiquid,
        "fast_movers": fast,
        "exit_queue_summary": {
            "queued": len(queue_items),
            "top_priority": queue_items[0].title if queue_items else None,
        },
    }

    snap = P71InvestorSellDashboardSnapshot(
        owner_user_id=owner_user_id,
        snapshot_date=today,
        generated_at=utc_now(),
        expected_realized_profit=round(expected_profit, 2),
        cards_json=cards,
        metadata_json={"read_only": True},
    )
    session.add(snap)
    session.flush()
    return snap
