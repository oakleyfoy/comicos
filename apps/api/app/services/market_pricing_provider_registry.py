"""P68-01 Market pricing provider registry."""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.market_pricing_engine import PROVIDER_TYPES, P68MarketPricingProvider, utc_now


def ensure_provider_registry(session: Session, *, owner_user_id: int) -> list[P68MarketPricingProvider]:
    existing = {
        r.provider_type: r
        for r in session.exec(
            select(P68MarketPricingProvider).where(P68MarketPricingProvider.owner_user_id == owner_user_id)
        ).all()
    }
    out: list[P68MarketPricingProvider] = []
    for pt in PROVIDER_TYPES:
        row = existing.get(pt)
        if row is None:
            row = P68MarketPricingProvider(
                owner_user_id=owner_user_id,
                provider_type=pt,
                enabled=pt in ("INTERNAL_SALE", "MANUAL", "STUB"),
                health_status="OK",
                metadata_json={},
            )
            session.add(row)
        out.append(row)
    session.flush()
    return out


def mark_provider_ingest(session: Session, *, provider: P68MarketPricingProvider) -> None:
    provider.last_ingest_at = utc_now()
    session.add(provider)
