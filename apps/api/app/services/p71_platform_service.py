"""P71 platform build orchestration."""

from __future__ import annotations

from sqlmodel import Session

from app.services.exit_queue_service import build_exit_queue_snapshot
from app.services.exit_recommendation_service import build_exit_recommendation_snapshot
from app.services.investor_sell_dashboard_service import build_investor_sell_dashboard_snapshot
from app.services.liquidity_intelligence_service import build_liquidity_snapshot
from app.services.listing_intelligence_service import build_listing_recommendation_snapshot


def run_p71_platform_build(session: Session, *, owner_user_id: int) -> dict:
    exit_snap = build_exit_recommendation_snapshot(session, owner_user_id=owner_user_id)
    listing_snap = build_listing_recommendation_snapshot(session, owner_user_id=owner_user_id)
    liq_snap = build_liquidity_snapshot(session, owner_user_id=owner_user_id)
    queue_snap = build_exit_queue_snapshot(session, owner_user_id=owner_user_id)
    dash_snap = build_investor_sell_dashboard_snapshot(session, owner_user_id=owner_user_id)
    return {
        "steps": [
            {"step": "exit_recommendations", "snapshot_id": int(exit_snap.id or 0)},
            {"step": "listing_intelligence", "snapshot_id": int(listing_snap.id or 0)},
            {"step": "liquidity", "snapshot_id": int(liq_snap.id or 0)},
            {"step": "exit_queue", "snapshot_id": int(queue_snap.id or 0)},
            {"step": "sell_dashboard", "snapshot_id": int(dash_snap.id or 0)},
        ],
        "exit_recommendation_snapshot_id": int(exit_snap.id or 0),
        "listing_recommendation_snapshot_id": int(listing_snap.id or 0),
        "liquidity_snapshot_id": int(liq_snap.id or 0),
        "exit_queue_snapshot_id": int(queue_snap.id or 0),
        "investor_sell_dashboard_snapshot_id": int(dash_snap.id or 0),
    }
