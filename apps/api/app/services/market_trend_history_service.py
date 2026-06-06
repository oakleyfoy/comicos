"""P70-06 historical FMV trend points (foundation; no charts)."""

from __future__ import annotations

from datetime import date, timedelta

from sqlmodel import Session, select

from app.models.market_pricing_engine import P68MarketPriceSnapshot
from app.models.p70_market_refresh import P70MarketFmvTrendPoint, utc_now


def _trend_label(current: float | None, prior: float | None, *, threshold_pct: float = 5.0) -> str:
    if current is None or prior is None or prior <= 0:
        return "STABLE"
    delta_pct = (current - prior) / prior * 100.0
    if delta_pct >= threshold_pct:
        return "RISING"
    if delta_pct <= -threshold_pct:
        return "FALLING"
    return "STABLE"


def _prior_point(
    session: Session,
    *,
    owner_user_id: int,
    inventory_copy_id: int,
    as_of: date,
) -> P70MarketFmvTrendPoint | None:
    return session.exec(
        select(P70MarketFmvTrendPoint)
        .where(P70MarketFmvTrendPoint.owner_user_id == owner_user_id)
        .where(P70MarketFmvTrendPoint.inventory_copy_id == inventory_copy_id)
        .where(P70MarketFmvTrendPoint.recorded_on <= as_of)
        .order_by(P70MarketFmvTrendPoint.recorded_on.desc(), P70MarketFmvTrendPoint.id.desc())
    ).first()


def record_trend_points_from_snapshots(
    session: Session,
    *,
    owner_user_id: int,
    snapshots: list[P68MarketPriceSnapshot],
    recorded_on: date | None = None,
) -> int:
    today = recorded_on or date.today()
    created = 0
    for snap in snapshots:
        copy_id = snap.inventory_copy_id
        if not copy_id:
            continue
        blended = float(snap.blended_fmv or snap.raw_fmv or snap.graded_fmv or 0)
        if blended <= 0:
            continue
        metadata = dict(snap.metadata_json or {})
        breakdown = metadata.get("provider_breakdown") if isinstance(metadata.get("provider_breakdown"), dict) else {}
        prior_7 = _prior_point(session, owner_user_id=owner_user_id, inventory_copy_id=int(copy_id), as_of=today - timedelta(days=7))
        prior_30 = _prior_point(session, owner_user_id=owner_user_id, inventory_copy_id=int(copy_id), as_of=today - timedelta(days=30))
        prior_90 = _prior_point(session, owner_user_id=owner_user_id, inventory_copy_id=int(copy_id), as_of=today - timedelta(days=90))
        p7 = float(prior_7.blended_fmv) if prior_7 and prior_7.blended_fmv is not None else None
        p30 = float(prior_30.blended_fmv) if prior_30 and prior_30.blended_fmv is not None else None
        p90 = float(prior_90.blended_fmv) if prior_90 and prior_90.blended_fmv is not None else None
        session.add(
            P70MarketFmvTrendPoint(
                owner_user_id=owner_user_id,
                inventory_copy_id=int(copy_id),
                snapshot_id=int(snap.id or 0) or None,
                recorded_on=today,
                recorded_at=utc_now(),
                blended_fmv=blended,
                raw_fmv=float(snap.raw_fmv) if snap.raw_fmv is not None else None,
                confidence=float(snap.confidence or 0),
                liquidity_score=float(snap.liquidity_score or 0),
                sales_count=int(snap.sales_count or 0),
                price_trend_7d=_trend_label(blended, p7),
                price_trend_30d=_trend_label(blended, p30),
                price_trend_90d=_trend_label(blended, p90),
                provider_breakdown_json={str(k): int(v) for k, v in breakdown.items() if v is not None},
                metadata_json={"primary_provider": snap.primary_provider},
            )
        )
        created += 1
    return created


def list_trend_points_for_copy(
    session: Session,
    *,
    owner_user_id: int,
    inventory_copy_id: int,
    limit: int = 90,
) -> list[P70MarketFmvTrendPoint]:
    return list(
        session.exec(
            select(P70MarketFmvTrendPoint)
            .where(P70MarketFmvTrendPoint.owner_user_id == owner_user_id)
            .where(P70MarketFmvTrendPoint.inventory_copy_id == inventory_copy_id)
            .order_by(P70MarketFmvTrendPoint.recorded_on.desc(), P70MarketFmvTrendPoint.id.desc())
            .limit(min(max(limit, 1), 365))
        ).all()
    )
