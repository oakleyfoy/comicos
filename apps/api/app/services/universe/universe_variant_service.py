"""P98-10 variant expansion (UNKNOWN → concrete covers)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models.universe import (
    DEFAULT_VARIANT_TYPE,
    UNIVERSE_VARIANT_STATUS_CATALOGED,
    UNIVERSE_VARIANT_STATUS_DISCOVERED,
    UniverseVariant,
)

EXPANSION_MAP = {
    "Cover A": ("COVER_A", "Cover A"),
    "Cover B": ("COVER_B", "Cover B"),
    "Newsstand": ("NEWSSTAND", "Newsstand"),
    "Direct": ("DIRECT", "Direct Edition"),
    "Foil": ("FOIL", "Foil"),
    "1:25": ("RATIO", "1:25"),
    "Second Print": ("SECOND_PRINT", "Second Print"),
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def expand_variant_labels(
    session: Session,
    *,
    issue_id: int,
    labels: list[str],
    catalog_issue_id: int | None = None,
) -> list[UniverseVariant]:
    """Add variant shells without removing UNKNOWN/STANDARD rows."""
    created: list[UniverseVariant] = []
    for label in labels:
        key = label.strip()
        if not key:
            continue
        variant_type, variant_name = EXPANSION_MAP.get(key, ("UNKNOWN", key))
        existing = session.exec(
            select(UniverseVariant).where(
                UniverseVariant.issue_id == issue_id,
                UniverseVariant.variant_type == variant_type,
                UniverseVariant.variant_name == variant_name,
            )
        ).first()
        if existing is not None:
            if catalog_issue_id and existing.catalog_issue_id is None:
                existing.catalog_issue_id = catalog_issue_id
                existing.status = UNIVERSE_VARIANT_STATUS_CATALOGED
                existing.updated_at = _utc_now()
                session.add(existing)
            continue
        row = UniverseVariant(
            issue_id=issue_id,
            variant_type=variant_type,
            variant_name=variant_name,
            catalog_issue_id=catalog_issue_id,
            status=UNIVERSE_VARIANT_STATUS_CATALOGED if catalog_issue_id else UNIVERSE_VARIANT_STATUS_DISCOVERED,
        )
        session.add(row)
        session.flush()
        created.append(row)
    return created


def promote_unknown_when_catalog_linked(session: Session, *, issue_id: int) -> None:
    """If concrete variants exist, keep UNKNOWN row for legacy references."""
    unknown = session.exec(
        select(UniverseVariant).where(
            UniverseVariant.issue_id == issue_id,
            UniverseVariant.variant_type == DEFAULT_VARIANT_TYPE,
        )
    ).first()
    if unknown is None:
        return
    others = session.exec(
        select(UniverseVariant).where(
            UniverseVariant.issue_id == issue_id,
            UniverseVariant.id != unknown.id,
        )
    ).first()
    if others is not None and unknown.variant_name == "":
        unknown.variant_name = "Legacy unknown shell"
        unknown.updated_at = _utc_now()
        session.add(unknown)
