"""Read-only inventory + P66 FMV context for P67 (no scoring mutations)."""

from __future__ import annotations

from sqlmodel import Session

from app.services.market_intelligence_inventory import InventoryIntelRow, load_owner_inventory_rows
from app.services.market_pricing_service import get_latest_market_price_snapshot, list_market_observations


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


def enrich_row_value(row: InventoryIntelRow, fmv_by_title: dict[str, float]) -> float:
    if row.current_value > 0:
        return row.current_value
    alt = fmv_by_title.get(row.title.strip().lower(), 0.0)
    return alt
