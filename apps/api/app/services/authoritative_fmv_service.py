"""P70-06 authoritative FMV resolution from P68 (read-only; no inventory overwrite)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlmodel import Session, select

from app.models.market_pricing_engine import P68InventoryComputedFmv, P68MarketPriceObservation, P68MarketPriceSnapshot


@dataclass(frozen=True)
class AuthoritativeFmvView:
    inventory_copy_id: int
    authoritative_fmv: float
    raw_fmv: float | None
    blended_fmv: float | None
    confidence: float
    liquidity_score: float
    sales_count: int
    primary_provider: str
    provider_breakdown: dict[str, int]
    last_comp_date: date | None
    price_trend_30d: str
    price_trend_90d: str
    generated_at: datetime | None
    source: str = "P68_MARKET_PRICE_SNAPSHOT"


def _confidence_bucket(confidence: float) -> str:
    if confidence >= 0.8:
        return "very_high"
    if confidence >= 0.65:
        return "high"
    if confidence >= 0.45:
        return "medium"
    if confidence >= 0.25:
        return "low"
    return "very_low"


def _liquidity_bucket(score: float) -> str:
    if score >= 75:
        return "very_high"
    if score >= 55:
        return "high"
    if score >= 30:
        return "medium"
    if score >= 15:
        return "low"
    return "very_low"


def latest_p68_snapshot_for_copy(
    session: Session,
    *,
    owner_user_id: int,
    inventory_copy_id: int,
) -> P68MarketPriceSnapshot | None:
    return session.exec(
        select(P68MarketPriceSnapshot)
        .where(P68MarketPriceSnapshot.owner_user_id == owner_user_id)
        .where(P68MarketPriceSnapshot.inventory_copy_id == inventory_copy_id)
        .order_by(P68MarketPriceSnapshot.generated_at.desc(), P68MarketPriceSnapshot.id.desc())
    ).first()


def _provider_breakdown_from_snapshot(
    session: Session,
    *,
    owner_user_id: int,
    snapshot: P68MarketPriceSnapshot,
) -> dict[str, int]:
    metadata = dict(snapshot.metadata_json or {})
    raw = metadata.get("provider_breakdown")
    if isinstance(raw, dict) and raw:
        return {str(k): int(v) for k, v in raw.items() if v is not None}
    obs_ids = metadata.get("matched_observation_ids") or []
    if not obs_ids:
        return {}
    counts: dict[str, int] = {}
    for obs in session.exec(
        select(P68MarketPriceObservation)
        .where(P68MarketPriceObservation.owner_user_id == owner_user_id)
        .where(P68MarketPriceObservation.id.in_(obs_ids))
    ).all():
        key = obs.provider or "UNKNOWN"
        if key == "EBAY":
            key = "EBAY_SOLD"
        counts[key] = counts.get(key, 0) + 1
    return counts


def get_authoritative_fmv(
    session: Session,
    *,
    owner_user_id: int,
    inventory_copy_id: int,
) -> AuthoritativeFmvView | None:
    snap = latest_p68_snapshot_for_copy(
        session,
        owner_user_id=owner_user_id,
        inventory_copy_id=inventory_copy_id,
    )
    if snap is None:
        computed = session.exec(
            select(P68InventoryComputedFmv)
            .where(P68InventoryComputedFmv.owner_user_id == owner_user_id)
            .where(P68InventoryComputedFmv.inventory_copy_id == inventory_copy_id)
            .order_by(P68InventoryComputedFmv.generated_at.desc(), P68InventoryComputedFmv.id.desc())
        ).first()
        if computed is None or float(computed.computed_fmv or 0) <= 0:
            return None
        blend = dict(computed.provider_blend_json or {})
        breakdown = blend.get("provider_breakdown") if isinstance(blend.get("provider_breakdown"), dict) else {}
        if not breakdown and isinstance(blend.get("providers"), list):
            breakdown = {str(p): 1 for p in blend["providers"]}
        return AuthoritativeFmvView(
            inventory_copy_id=inventory_copy_id,
            authoritative_fmv=float(computed.computed_fmv),
            raw_fmv=None,
            blended_fmv=float(computed.computed_fmv),
            confidence=float(computed.confidence or 0),
            liquidity_score=0.0,
            sales_count=0,
            primary_provider=str(computed.computed_fmv_source or ""),
            provider_breakdown={str(k): int(v) for k, v in breakdown.items()},
            last_comp_date=None,
            price_trend_30d="STABLE",
            price_trend_90d="STABLE",
            generated_at=computed.generated_at,
            source="P68_INVENTORY_COMPUTED_FMV",
        )

    metadata = dict(snap.metadata_json or {})
    blended = float(snap.blended_fmv or snap.raw_fmv or snap.graded_fmv or 0)
    if blended <= 0:
        return None
    last_comp = metadata.get("last_comp_date")
    last_comp_date: date | None = None
    if isinstance(last_comp, str) and last_comp:
        try:
            last_comp_date = date.fromisoformat(last_comp)
        except ValueError:
            last_comp_date = None
    return AuthoritativeFmvView(
        inventory_copy_id=inventory_copy_id,
        authoritative_fmv=blended,
        raw_fmv=float(snap.raw_fmv) if snap.raw_fmv is not None else None,
        blended_fmv=float(snap.blended_fmv) if snap.blended_fmv is not None else None,
        confidence=float(snap.confidence or 0),
        liquidity_score=float(snap.liquidity_score or 0),
        sales_count=int(snap.sales_count or 0),
        primary_provider=str(snap.primary_provider or ""),
        provider_breakdown=_provider_breakdown_from_snapshot(session, owner_user_id=owner_user_id, snapshot=snap),
        last_comp_date=last_comp_date,
        price_trend_30d=str(snap.price_trend_30d or "STABLE"),
        price_trend_90d=str(snap.price_trend_90d or "STABLE"),
        generated_at=snap.generated_at,
    )


def authoritative_fmv_to_evidence(view: AuthoritativeFmvView) -> dict:
    return {
        "p68_authoritative_fmv": view.authoritative_fmv,
        "p68_raw_fmv": view.raw_fmv,
        "p68_blended_fmv": view.blended_fmv,
        "p68_confidence": view.confidence,
        "p68_confidence_bucket": _confidence_bucket(view.confidence),
        "p68_liquidity_score": view.liquidity_score,
        "p68_liquidity_bucket": _liquidity_bucket(view.liquidity_score),
        "p68_sales_count": view.sales_count,
        "p68_primary_provider": view.primary_provider,
        "p68_provider_breakdown": view.provider_breakdown,
        "p68_last_comp_date": view.last_comp_date.isoformat() if view.last_comp_date else None,
        "p68_price_trend_30d": view.price_trend_30d,
        "p68_price_trend_90d": view.price_trend_90d,
        "p68_generated_at": view.generated_at.isoformat() if view.generated_at else None,
        "p68_source": view.source,
    }
