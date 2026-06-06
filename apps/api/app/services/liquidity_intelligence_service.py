"""P71-03 Liquidity intelligence."""

from __future__ import annotations

from datetime import date

from sqlmodel import Session, select

from app.models.sell_intelligence_platform import P71LiquidityItem, P71LiquiditySnapshot, utc_now
from app.services.p71_sell_context import load_sell_intel_contexts
from app.services.p71_sell_scoring import score_liquidity


def get_latest_liquidity_snapshot(session: Session, *, owner_user_id: int) -> P71LiquiditySnapshot | None:
    return session.exec(
        select(P71LiquiditySnapshot)
        .where(P71LiquiditySnapshot.owner_user_id == owner_user_id)
        .order_by(P71LiquiditySnapshot.generated_at.desc(), P71LiquiditySnapshot.id.desc())
    ).first()


def list_liquidity_items(session: Session, *, snapshot_id: int, limit: int = 200) -> list[P71LiquidityItem]:
    return list(
        session.exec(
            select(P71LiquidityItem)
            .where(P71LiquidityItem.snapshot_id == snapshot_id)
            .order_by(P71LiquidityItem.liquidity_score.desc(), P71LiquidityItem.id.asc())
            .limit(min(max(limit, 1), 500))
        ).all()
    )


def build_liquidity_snapshot(session: Session, *, owner_user_id: int) -> P71LiquiditySnapshot:
    today = date.today()
    contexts = load_sell_intel_contexts(session, owner_user_id=owner_user_id)
    snap = P71LiquiditySnapshot(
        owner_user_id=owner_user_id,
        snapshot_date=today,
        generated_at=utc_now(),
        metadata_json={
            "avg_market_confidence": round(sum(c.fmv_confidence for c in contexts) / max(1, len(contexts)), 3),
            "avg_market_liquidity": round(sum(c.market_liquidity_score for c in contexts) / max(1, len(contexts)), 2),
            "avg_market_sales_velocity": round(sum(c.market_sales_velocity for c in contexts) / max(1, len(contexts)), 3),
        },
    )
    session.add(snap)
    session.flush()

    count = 0
    for ctx in contexts:
        band, score, velocity, obs, demand, conf, days, factors = score_liquidity(ctx)
        session.add(
            P71LiquidityItem(
                snapshot_id=int(snap.id or 0),
                owner_user_id=owner_user_id,
                inventory_copy_id=ctx.copy_id,
                title=ctx.title,
                liquidity_band=band,
                liquidity_score=score,
                sales_velocity=velocity,
                observation_count=obs,
                demand_strength=demand,
                market_confidence=conf,
                days_to_sell_estimate=days,
                factors_json=factors,
            )
        )
        count += 1
    snap.total_items = count
    session.add(snap)
    session.flush()
    return snap
