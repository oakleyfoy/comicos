"""P66 platform orchestration and P62/P65 integration helpers."""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.buy_queue_intelligence import BuyQueueSnapshot
from app.models.variant_market_intelligence import VariantDecisionItem
from app.services.market_pricing_service import build_market_prices
from app.services.quantity_intelligence_service import build_quantity_recommendations
from app.services.variant_decision_engine import build_variant_decisions, get_latest_variant_decision_snapshot, list_variant_decision_items
from app.services.variant_intelligence_service import build_variant_intelligence


def build_p66_platform(session: Session, *, owner_user_id: int) -> dict:
    """Run P66 pipeline in dependency order (does not mutate P61/P62 ranking tables)."""
    vi = build_variant_intelligence(session, owner_user_id=owner_user_id)
    mp = build_market_prices(session, owner_user_id=owner_user_id)
    qty = build_quantity_recommendations(session, owner_user_id=owner_user_id)
    dec = build_variant_decisions(session, owner_user_id=owner_user_id)
    return {
        "variant_intelligence_snapshot_id": int(vi.id or 0),
        "market_price_snapshot_id": int(mp.id or 0),
        "quantity_snapshot_id": int(qty.id or 0),
        "variant_decision_snapshot_id": int(dec.id or 0),
    }


def get_integration_enrichment(
    session: Session,
    *,
    owner_user_id: int,
    external_catalog_issue_id: int | None,
    buy_queue_item_id: int | None,
) -> dict | None:
    snap = get_latest_variant_decision_snapshot(session, owner_user_id=owner_user_id)
    if snap is None:
        return None
    for row in list_variant_decision_items(session, snapshot_id=int(snap.id or 0), limit=200):
        if external_catalog_issue_id and row.external_catalog_issue_id == external_catalog_issue_id:
            return _enrichment_row(row)
        if buy_queue_item_id and row.buy_queue_item_id == buy_queue_item_id:
            return _enrichment_row(row)
    return None


def _enrichment_row(row: VariantDecisionItem) -> dict:
    return {
        "recommendation_summary": row.recommendation_summary,
        "cover_ranking": list(row.cover_ranking_json or []),
        "buy_plan": list(row.buy_plan_json or []),
        "skip_covers": list(row.skip_covers_json or []),
        "quantity_plan": dict(row.quantity_plan_json or {}),
    }


def count_buy_queue_snapshots(session: Session) -> int:
    from sqlmodel import func

    return int(session.exec(select(func.count()).select_from(BuyQueueSnapshot)).one())
