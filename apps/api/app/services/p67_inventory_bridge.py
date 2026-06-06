"""Read-only inventory + P66 FMV context for P67 (no scoring mutations)."""

from __future__ import annotations

from sqlmodel import Session

from app.services.market_intelligence_inventory import InventoryIntelRow, load_owner_inventory_rows
from app.services.market_pricing_service import get_latest_market_price_snapshot, list_market_observations
from sqlmodel import select
from app.models.market_pricing_engine import P68InventoryComputedFmv, P68MarketPriceSnapshot


def load_p67_inventory_context(session: Session, *, owner_user_id: int) -> list[InventoryIntelRow]:
    return load_owner_inventory_rows(session, owner_user_id=owner_user_id)


def fmv_lookup_by_title(session: Session, *, owner_user_id: int) -> dict[str, float]:
    """Best-effort FMV map from latest P66 market price snapshot (stub provider)."""
    snap = get_latest_market_price_snapshot(session, owner_user_id=owner_user_id)
    if snap is None:
        return {}
    out: dict[str, float] = {}
    for obs in list_market_observations(session, snapshot_id=int(snap.id or 0), limit=500):
        prov = obs.provenance_json or {}
        key = str(prov.get("title") or prov.get("series") or "").strip().lower()
        if key:
            out[key] = float(obs.fmv or 0)
    return out


def p68_computed_fmv_for_copy(session: Session, *, owner_user_id: int, copy_id: int) -> tuple[float, str, float] | None:
    snap = session.exec(
        select(P68MarketPriceSnapshot)
        .where(P68MarketPriceSnapshot.owner_user_id == owner_user_id)
        .where(P68MarketPriceSnapshot.inventory_copy_id == copy_id)
        .order_by(P68MarketPriceSnapshot.generated_at.desc(), P68MarketPriceSnapshot.id.desc())
    ).first()
    if snap is not None:
        blended = float(snap.blended_fmv or snap.raw_fmv or snap.graded_fmv or 0)
        if blended > 0:
            return blended, str(snap.primary_provider or "P68_BLEND"), float(snap.confidence or 0)
    row = session.exec(
        select(P68InventoryComputedFmv)
        .where(P68InventoryComputedFmv.owner_user_id == owner_user_id)
        .where(P68InventoryComputedFmv.inventory_copy_id == copy_id)
        .order_by(P68InventoryComputedFmv.generated_at.desc(), P68InventoryComputedFmv.id.desc())
    ).first()
    if row is None:
        return None
    return float(row.computed_fmv), row.computed_fmv_source, float(row.confidence)


def enrich_row_value(
    row: InventoryIntelRow,
    fmv_by_title: dict[str, float],
    *,
    p68_computed: tuple[float, str, float] | None = None,
) -> float:
    if p68_computed and p68_computed[0] > 0:
        return p68_computed[0]
    if row.current_value > 0:
        return row.current_value
    alt = fmv_by_title.get(row.title.strip().lower(), 0.0)
    return alt
