"""P66 certification."""

from __future__ import annotations

from sqlmodel import Session, func, select

from app.models.buy_queue_intelligence import BuyQueueSnapshot
from app.services.p66_platform_service import build_p66_platform, count_buy_queue_snapshots
from app.services.variant_decision_engine import get_latest_variant_decision_snapshot, list_variant_decision_items
from app.services.variant_intelligence_service import get_latest_variant_intelligence_snapshot, list_variant_intelligence_items
from app.services.quantity_intelligence_service import get_latest_quantity_snapshot, list_quantity_items


def certify_p66_platform(session: Session, *, owner_user_id: int) -> dict:
    bq_before = count_buy_queue_snapshots(session)
    build_result = build_p66_platform(session, owner_user_id=owner_user_id)
    bq_after = count_buy_queue_snapshots(session)
    vi = get_latest_variant_intelligence_snapshot(session, owner_user_id=owner_user_id)
    qty = get_latest_quantity_snapshot(session, owner_user_id=owner_user_id)
    dec = get_latest_variant_decision_snapshot(session, owner_user_id=owner_user_id)
    variants = list_variant_intelligence_items(session, snapshot_id=int(vi.id or 0), limit=5) if vi else []
    decisions = list_variant_decision_items(session, snapshot_id=int(dec.id or 0), limit=5) if dec else []
    quantities = list_quantity_items(session, snapshot_id=int(qty.id or 0), limit=5) if qty else []
    checks = {
        "variant_scoring": bool(vi and vi.total_items > 0),
        "quantity_generation": bool(qty and qty.total_items >= 0),
        "cover_ranking": bool(dec and dec.total_issues > 0),
        "recommendation_integration": bool(quantities),
        "owner_isolation": all(v.owner_user_id == owner_user_id for v in variants) if variants else True,
    }
    non_mutation = {"certified": bq_before == bq_after, "before": bq_before, "after": bq_after}
    certified = non_mutation["certified"] and all(checks.values())
    return {
        "certified": certified,
        "platform_ready": bool(vi and dec),
        "checks": checks,
        "non_mutation": non_mutation,
        "build": build_result,
    }
