"""Serialize P68 snapshots with provider breakdown for API consumers."""

from __future__ import annotations

from datetime import date

from app.models.market_pricing_engine import P68MarketPriceSnapshot
from app.schemas.market_pricing_engine import P68SnapshotRead


def p68_snapshot_to_read(snapshot: P68MarketPriceSnapshot) -> P68SnapshotRead:
    metadata = dict(snapshot.metadata_json or {})
    breakdown_raw = metadata.get("provider_breakdown")
    breakdown: dict[str, int] = {}
    if isinstance(breakdown_raw, dict):
        breakdown = {str(k): int(v) for k, v in breakdown_raw.items() if v is not None}
    last_comp_raw = metadata.get("last_comp_date")
    last_comp: date | None = None
    if isinstance(last_comp_raw, str) and last_comp_raw:
        try:
            last_comp = date.fromisoformat(last_comp_raw)
        except ValueError:
            last_comp = None
    base = P68SnapshotRead.model_validate(snapshot, from_attributes=True)
    return base.model_copy(update={"provider_breakdown": breakdown, "last_comp_date": last_comp})
