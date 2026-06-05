"""Inventory context helpers for P63."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlmodel import Session, select

from app.models.asset_ledger import InventoryCopy
from app.services.sell_candidate_engine import _split_identity_key


@dataclass(frozen=True)
class InventoryIntelRow:
    copy_id: int
    publisher: str
    title: str
    issue_number: str
    quantity: int
    cost_basis: float
    current_value: float
    unrealized_gain: float
    unrealized_gain_pct: float
    grade_status: str
    identity_key: str


def _money(value: Decimal | float | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def performance_tier(*, gain_pct: float, has_value: bool) -> str:
    from app.models.market_intelligence_platform import (
        PERF_DOWN,
        PERF_FLAT,
        PERF_MODEST_GAIN,
        PERF_STRONG_GAIN,
        PERF_UNKNOWN,
    )

    if not has_value:
        return PERF_UNKNOWN
    if gain_pct >= 25.0:
        return PERF_STRONG_GAIN
    if gain_pct >= 5.0:
        return PERF_MODEST_GAIN
    if gain_pct <= -5.0:
        return PERF_DOWN
    return PERF_FLAT


def load_owner_inventory_rows(session: Session, *, owner_user_id: int) -> list[InventoryIntelRow]:
    copies = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id)).all()
    grouped: dict[tuple[str, str, str], list[InventoryCopy]] = {}
    for copy in copies:
        pub, series, issue, _variant = _split_identity_key(copy.metadata_identity_key)
        title = series or (copy.metadata_identity_key or f"Copy {copy.id}")
        key = (pub.lower(), title.lower(), issue.lower())
        grouped.setdefault(key, []).append(copy)

    rows: list[InventoryIntelRow] = []
    for (_pub, _title, _issue), group in grouped.items():
        for copy in group:
            cost = _money(copy.acquisition_cost)
            fmv = _money(copy.current_fmv)
            has_value = copy.current_fmv is not None
            gain = fmv - cost if has_value else 0.0
            gain_pct = (gain / cost * 100.0) if cost > 0 and has_value else 0.0
            pub, series, issue, _ = _split_identity_key(copy.metadata_identity_key)
            rows.append(
                InventoryIntelRow(
                    copy_id=int(copy.id or 0),
                    publisher=pub,
                    title=series or (copy.metadata_identity_key or ""),
                    issue_number=issue,
                    quantity=1,
                    cost_basis=cost,
                    current_value=fmv if has_value else 0.0,
                    unrealized_gain=gain,
                    unrealized_gain_pct=round(gain_pct, 2),
                    grade_status=copy.grade_status or "raw",
                    identity_key=copy.metadata_identity_key or "",
                )
            )
    return rows


def count_identity_copies(session: Session, *, owner_user_id: int) -> dict[tuple[str, str, str], int]:
    counts: dict[tuple[str, str, str], int] = {}
    for row in load_owner_inventory_rows(session, owner_user_id=owner_user_id):
        key = (row.publisher.lower(), row.title.lower(), row.issue_number.lower())
        counts[key] = counts.get(key, 0) + 1
    return counts
