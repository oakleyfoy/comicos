"""Read-only sell context from P67/P68 inventory (no upstream mutation)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, select

from app.models.market_pricing_engine import P68MarketPriceSnapshot
from app.services.collection_analytics_service import get_latest_collection_analytics_snapshot
from app.services.p67_inventory_bridge import enrich_row_value, fmv_lookup_by_title, load_p67_inventory_context, p68_computed_fmv_for_copy
from app.services.recommendation_performance_service import get_latest_recommendation_performance_snapshot


@dataclass(frozen=True)
class SellIntelCopyContext:
    copy_id: int
    title: str
    publisher: str
    issue_number: str
    quantity: int
    cost_basis: float
    estimated_fmv: float
    fmv_confidence: float
    liquidity_score: float
    sales_count: int
    price_trend: str
    unrealized_gain: float
    unrealized_gain_pct: float
    grade_status: str
    portfolio_share_pct: float
    recommendation_hit_rate: float


def _p68_by_copy(session: Session, *, owner_user_id: int) -> dict[int, P68MarketPriceSnapshot]:
    snaps = list(
        session.exec(
            select(P68MarketPriceSnapshot)
            .where(P68MarketPriceSnapshot.owner_user_id == owner_user_id)
            .order_by(P68MarketPriceSnapshot.generated_at.desc(), P68MarketPriceSnapshot.id.desc())
            .limit(500)
        ).all()
    )
    out: dict[int, P68MarketPriceSnapshot] = {}
    for s in snaps:
        cid = s.inventory_copy_id
        if cid and cid not in out:
            out[int(cid)] = s
    return out


def load_sell_intel_contexts(session: Session, *, owner_user_id: int) -> list[SellIntelCopyContext]:
    rows = load_p67_inventory_context(session, owner_user_id=owner_user_id)
    fmv_map = fmv_lookup_by_title(session, owner_user_id=owner_user_id)
    p68_map = _p68_by_copy(session, owner_user_id=owner_user_id)
    coll = get_latest_collection_analytics_snapshot(session, owner_user_id=owner_user_id)
    concentration = float(coll.concentration_score or 0) if coll else 0.0
    rec = get_latest_recommendation_performance_snapshot(session, owner_user_id=owner_user_id)
    hit_rate = float(rec.hit_rate_pct or 0) if rec else 0.0

    total_value = 0.0
    enriched: list[tuple] = []
    for row in rows:
        p68_row = p68_computed_fmv_for_copy(session, owner_user_id=owner_user_id, copy_id=row.copy_id)
        est = enrich_row_value(row, fmv_map, p68_computed=p68_row)
        total_value += est
        enriched.append((row, est, p68_row))

    contexts: list[SellIntelCopyContext] = []
    for row, est, p68_row in enriched:
        snap = p68_map.get(row.copy_id)
        conf = float(p68_row[2]) if p68_row else 0.45
        liq = float(snap.liquidity_score or 0) if snap else 20.0
        sales = int(snap.sales_count or 0) if snap else 0
        trend = (snap.price_trend_30d or "STABLE") if snap else "STABLE"
        if snap and snap.confidence:
            conf = max(conf, float(snap.confidence))
        cost = row.cost_basis
        gain = est - cost if est > 0 else 0.0
        gain_pct = (gain / cost * 100.0) if cost > 0 and est > 0 else 0.0
        share = (est / total_value * 100.0) if total_value > 0 and est > 0 else 0.0
        contexts.append(
            SellIntelCopyContext(
                copy_id=row.copy_id,
                title=row.title,
                publisher=row.publisher,
                issue_number=row.issue_number,
                quantity=row.quantity,
                cost_basis=cost,
                estimated_fmv=est,
                fmv_confidence=conf,
                liquidity_score=liq,
                sales_count=sales,
                price_trend=trend,
                unrealized_gain=gain,
                unrealized_gain_pct=gain_pct,
                grade_status=row.grade_status or "raw",
                portfolio_share_pct=share,
                recommendation_hit_rate=hit_rate,
            )
        )
    _ = concentration  # informs dashboard; per-copy share used for trim signals
    return contexts
