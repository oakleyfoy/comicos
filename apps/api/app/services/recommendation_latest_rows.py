"""Bounded scans for latest recommendation rows (avoids loading full append-only history)."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from sqlmodel import Session, SQLModel, select

T = TypeVar("T", bound=SQLModel)


def latest_by_key_bounded_scan(
    session: Session,
    *,
    model: type[T],
    owner_user_id: int,
    owner_field: str,
    key_fn: Callable[[T], tuple],
    scan_limit: int = 8000,
) -> dict[tuple, T]:
    """Return newest row per key by scanning recent ids only (descending)."""
    id_col = model.id  # type: ignore[attr-defined]
    owner_col = getattr(model, owner_field)
    max_id_row = session.exec(
        select(id_col).where(owner_col == owner_user_id).order_by(id_col.desc()).limit(1)
    ).one_or_none()
    if max_id_row is None:
        return {}
    max_id = int(getattr(max_id_row, "id", max_id_row) or 0)
    if max_id <= 0:
        return {}
    rows = session.exec(
        select(model)
        .where(owner_col == owner_user_id, id_col <= max_id)
        .order_by(id_col.desc())
        .limit(max(1, int(scan_limit)))
    ).all()
    latest: dict[tuple, T] = {}
    for row in rows:
        key = key_fn(row)
        if key not in latest:
            latest[key] = row
    return latest
