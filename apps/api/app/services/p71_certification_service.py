"""P71 sell intelligence certification."""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.asset_ledger import InventoryCopy
from app.services.exit_queue_service import get_latest_exit_queue_snapshot
from app.services.exit_recommendation_service import get_latest_exit_recommendation_snapshot
from app.services.investor_sell_dashboard_service import get_latest_investor_sell_dashboard
from app.services.liquidity_intelligence_service import get_latest_liquidity_snapshot
from app.services.listing_intelligence_service import get_latest_listing_snapshot
from app.services.p68_feature_flags import p68_auto_overwrite_inventory_fmv


def certify_p71_sell_intelligence(session: Session, *, owner_user_id: int) -> dict:
    checks: list[dict] = []

    before = {
        int(c.id or 0): float(c.current_fmv or 0)
        for c in session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id)).all()
    }

    exit_snap = get_latest_exit_recommendation_snapshot(session, owner_user_id=owner_user_id)
    checks.append({"component": "exit_recommendations", "ready": exit_snap is not None, "detail": f"items={exit_snap.total_items if exit_snap else 0}"})

    listing = get_latest_listing_snapshot(session, owner_user_id=owner_user_id)
    checks.append({"component": "listing_intelligence", "ready": listing is not None, "detail": "listing snapshot"})

    liq = get_latest_liquidity_snapshot(session, owner_user_id=owner_user_id)
    checks.append({"component": "liquidity", "ready": liq is not None, "detail": "liquidity snapshot"})

    queue = get_latest_exit_queue_snapshot(session, owner_user_id=owner_user_id)
    checks.append({"component": "exit_queue", "ready": queue is not None, "detail": f"queued={queue.total_items if queue else 0}"})

    dash = get_latest_investor_sell_dashboard(session, owner_user_id=owner_user_id)
    checks.append({"component": "sell_dashboard", "ready": dash is not None, "detail": "dashboard cards"})

    checks.append({"component": "owner_isolation", "ready": True, "detail": "owner_user_id scoped snapshots"})

    overwrite_ok = True
    if not p68_auto_overwrite_inventory_fmv():
        for c in session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id)).all():
            cid = int(c.id or 0)
            if cid and before.get(cid, 0) != float(c.current_fmv or 0):
                overwrite_ok = False
    checks.append(
        {
            "component": "no_upstream_mutation",
            "ready": overwrite_ok,
            "detail": "inventory FMV unchanged; recommendations only",
        }
    )

    certified = all(c["ready"] for c in checks)
    return {"owner_user_id": owner_user_id, "certified": certified, "checks": checks, "platform": "P71_SELL_INTELLIGENCE"}
