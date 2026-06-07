"""P90-02 portfolio-level FMV V2 aggregation."""

from __future__ import annotations

from collections import Counter

from sqlmodel import Session, select

from app.models.asset_ledger import InventoryCopy
from app.services.fmv_v2_service import lookup_fmv_v2_for_copy
from app.services.p89_market_pricing_service import _identity_from_metadata


def build_portfolio_fmv_v2(session: Session, *, owner_user_id: int) -> dict:
    copies = list(
        session.exec(
            select(InventoryCopy)
            .where(InventoryCopy.user_id == owner_user_id)
            .where(InventoryCopy.hold_status != "sold")
        ).all()
    )
    quick_total = 0.0
    market_total = 0.0
    premium_total = 0.0
    conf_counter: Counter[str] = Counter()
    trend_scores: list[float] = []
    valued_copies = 0
    for copy in copies:
        display = lookup_fmv_v2_for_copy(session, owner_user_id=owner_user_id, copy=copy)
        if display is None:
            continue
        valued_copies += 1
        quick_total += display.quick_sale_value
        market_total += display.market_value
        premium_total += display.premium_value
        conf_counter[display.valuation_confidence] += 1
        trend_scores.append(display.trend_score)
    portfolio_trend = "FLAT"
    if trend_scores:
        avg_trend = sum(trend_scores) / len(trend_scores)
        if avg_trend >= 8:
            portfolio_trend = "UP"
        elif avg_trend <= -8:
            portfolio_trend = "DOWN"
    return {
        "copy_count": len(copies),
        "valued_copy_count": valued_copies,
        "quick_liquidation_total": round(quick_total, 2),
        "market_portfolio_value": round(market_total, 2),
        "premium_portfolio_value": round(premium_total, 2),
        "confidence_high": int(conf_counter.get("HIGH", 0)),
        "confidence_medium": int(conf_counter.get("MEDIUM", 0)),
        "confidence_low": int(conf_counter.get("LOW", 0)),
        "portfolio_trend": portfolio_trend,
        "average_trend_score": round(sum(trend_scores) / len(trend_scores), 1) if trend_scores else 0.0,
    }


def build_fmv_v2_briefing_summary(session: Session, *, owner_user_id: int) -> dict:
    from app.services.fmv_v2_service import latest_snapshots_for_owner

    portfolio = build_portfolio_fmv_v2(session, owner_user_id=owner_user_id)
    snaps = latest_snapshots_for_owner(session, owner_user_id=owner_user_id, limit=500)
    uptrend = max(snaps, key=lambda s: s.trend_score) if snaps else None
    downtrend = min(snaps, key=lambda s: s.trend_score) if snaps else None
    highest = max(snaps, key=lambda s: s.market_value) if snaps else None

    def _title(s) -> str | None:
        if s is None:
            return None
        if s.issue_number:
            return f"{s.series} #{s.issue_number}"
        return s.series or None

    return {
        "largest_uptrend": _title(uptrend),
        "largest_downtrend": _title(downtrend),
        "highest_value_book": _title(highest),
        "portfolio_market_value": portfolio["market_portfolio_value"],
        "portfolio_trend": portfolio["portfolio_trend"],
    }
