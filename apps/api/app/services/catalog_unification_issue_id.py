"""Resolve master-catalog issue ids for grading and inventory scopes (unification B2)."""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlmodel import Session, select

from app.models import InventoryCopy, Variant


def resolve_catalog_issue_id_for_inventory_copy(session: Session, copy_id: int) -> int | None:
    copy = session.get(InventoryCopy, copy_id)
    if copy is None or copy.catalog_issue_id is None:
        return None
    return int(copy.catalog_issue_id)


def _catalog_issue_id_from_link_table(session: Session, comic_issue_id: int) -> int | None:
    bind = session.get_bind()
    if bind is None or not inspect(bind).has_table("catalog_issue_link"):
        return None
    row = session.execute(
        text(
            "SELECT catalog_issue_id FROM catalog_issue_link "
            "WHERE comic_issue_id = :comic_issue_id LIMIT 1"
        ),
        {"comic_issue_id": comic_issue_id},
    ).first()
    if row is None or row[0] is None:
        return None
    return int(row[0])


def effective_catalog_issue_id(
    session: Session,
    *,
    catalog_issue_id: int | None,
    canonical_comic_issue_id: int | None,
    inventory_copy_id: int | None,
) -> int | None:
    if catalog_issue_id is not None:
        return int(catalog_issue_id)
    if inventory_copy_id is not None:
        from_copy = resolve_catalog_issue_id_for_inventory_copy(session, inventory_copy_id)
        if from_copy is not None:
            return from_copy
    if canonical_comic_issue_id is not None:
        linked = _catalog_issue_id_from_link_table(session, int(canonical_comic_issue_id))
        if linked is not None:
            return linked
    return None


def resolve_legacy_comic_issue_id(
    session: Session,
    inventory: InventoryCopy,
    *,
    fallback_canonical_comic_issue_id: int | None = None,
) -> int | None:
    if inventory.variant_id is not None:
        variant = session.get(Variant, int(inventory.variant_id))
        if variant is not None and variant.comic_issue_id is not None:
            return int(variant.comic_issue_id)
    if fallback_canonical_comic_issue_id is not None:
        return int(fallback_canonical_comic_issue_id)
    return None
