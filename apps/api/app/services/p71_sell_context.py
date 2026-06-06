"""Read-only sell context from P67/P68 inventory (no upstream mutation)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlmodel import Session, select

from app.models.market_pricing_engine import P68MarketPriceSnapshot
from app.models.sell_intelligence_platform import LIQ_HIGH, LIQ_LOW, LIQ_MEDIUM
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
    market_average_sale: float = 0.0
    market_median_sale: float = 0.0
    market_weighted_median_sale: float = 0.0
    market_recent_median_30d: float = 0.0
    market_recent_median_90d: float = 0.0
    market_sales_velocity: float = 0.0
    market_liquidity_band: str = LIQ_LOW
    market_liquidity_score: float = 0.0
    market_confidence_band: str = "LOW"
    market_provider_breakdown_json: dict[str, int] = field(default_factory=dict)
    market_primary_provider: str = ""
    market_timing_signal: str = "HOLD"
    market_timing_reason: str = ""
    market_explanation: str = ""


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


def _score_to_liquidity_band(score: float) -> str:
    if score >= 75.0:
        return "VERY_HIGH"
    if score >= 55.0:
        return LIQ_HIGH
    if score >= 30.0:
        return LIQ_MEDIUM
    return LIQ_LOW


def _confidence_band(confidence: float) -> str:
    if confidence >= 0.7:
        return "HIGH"
    if confidence >= 0.45:
        return "MEDIUM"
    return "LOW"


def _derive_market_timing(*, liquidity_score: float, confidence: float, sales_velocity: float, trend: str, weighted_median: float, average_sale: float) -> tuple[str, str]:
    if weighted_median <= 0 and average_sale <= 0:
        return "HOLD", "No market pricing data yet."
    if liquidity_score >= 72.0 and confidence >= 0.7 and sales_velocity >= 2.0 and trend == "RISING":
        return "SELL_NOW", "High liquidity and strong recent sales support an immediate exit."
    if liquidity_score >= 55.0 and confidence >= 0.55 and (trend in {"RISING", "STABLE"} or sales_velocity >= 1.2):
        return "SELL_SOON", "Market depth is healthy, but there is still room to capture a stronger sale."
    if liquidity_score <= 28.0 or trend == "FALLING":
        if confidence >= 0.7 and weighted_median < average_sale * 0.95:
            return "ACCUMULATE", "Market is soft, but the comp set suggests underpricing relative to recent strength."
        return "HOLD", "Market is thin or weakening; waiting is safer than forcing a sale."
    if confidence >= 0.6 and sales_velocity < 1.0 and trend == "STABLE":
        return "ACCUMULATE", "Stable market with limited velocity suggests adding or holding for a better entry."
    return "HOLD", "Current market conditions do not justify an aggressive sale."


def _snapshot_market_summary(snapshot: P68MarketPriceSnapshot | None) -> dict[str, Any]:
    if snapshot is None:
        return {}
    metadata = dict(snapshot.metadata_json or {})
    weighted_median = float(metadata.get("weighted_median_sale") or snapshot.median_sale or snapshot.blended_fmv or 0.0)
    average_sale = float(metadata.get("average_sale") or snapshot.average_sale or snapshot.blended_fmv or 0.0)
    recent_30 = float(metadata.get("recent_median_30d") or weighted_median)
    recent_90 = float(metadata.get("recent_median_90d") or weighted_median)
    sales_velocity = float(metadata.get("sales_velocity") or 0.0)
    if sales_velocity <= 0 and snapshot.sales_count > 0:
        sales_velocity = round(min(10.0, float(snapshot.sales_count) / 3.0), 2)
    liquidity_score = float(metadata.get("liquidity_score") or snapshot.liquidity_score or 0.0)
    confidence = float(metadata.get("market_confidence") or snapshot.confidence or 0.0)
    provider_breakdown = metadata.get("provider_breakdown") if isinstance(metadata.get("provider_breakdown"), dict) else {}
    primary_provider = str(metadata.get("primary_provider") or snapshot.primary_provider or "")
    liquidity_band = str(metadata.get("liquidity_band") or _score_to_liquidity_band(liquidity_score))
    timing_signal, timing_reason = _derive_market_timing(
        liquidity_score=liquidity_score,
        confidence=confidence,
        sales_velocity=sales_velocity,
        trend=snapshot.price_trend_30d,
        weighted_median=weighted_median,
        average_sale=average_sale,
    )
    return {
        "market_average_sale": round(average_sale, 2),
        "market_median_sale": round(float(snapshot.median_sale or weighted_median), 2),
        "market_weighted_median_sale": round(weighted_median, 2),
        "market_recent_median_30d": round(recent_30, 2),
        "market_recent_median_90d": round(recent_90, 2),
        "market_sales_velocity": round(sales_velocity, 3),
        "market_liquidity_band": liquidity_band,
        "market_liquidity_score": round(liquidity_score, 2),
        "market_confidence_band": _confidence_band(confidence),
        "market_provider_breakdown_json": {str(k): int(v) for k, v in provider_breakdown.items() if v is not None},
        "market_primary_provider": primary_provider,
        "market_timing_signal": timing_signal,
        "market_timing_reason": timing_reason,
        "market_explanation": f"{timing_reason} FMV {weighted_median:.2f}, liquidity {liquidity_band.lower()}, confidence {_confidence_band(confidence).lower()}.",
    }


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
        market_summary = _snapshot_market_summary(snap)
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
                **market_summary,
            )
        )
    _ = concentration  # informs dashboard; per-copy share used for trim signals
    return contexts
