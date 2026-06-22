"""Canonical identity resolver for an inventory copy.

Part of the inventory catalog unification: a single place that answers
"what comic is this copy?" preferring the master catalog (``catalog_issue``),
then the legacy asset-ledger spine (``comic_issue`` via ``variant``), then the
copy's stored ``metadata_identity_key``. Read surfaces should consume this
instead of inner-joining ``comic_title``/``comic_issue``/``variant`` directly,
so every copy resolves regardless of which spine populated it.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, select

from app.models import ComicIssue, ComicTitle, InventoryCopy, Publisher, Variant
from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries
from app.services.legacy_spine_availability import legacy_variant_table_exists
from app.services.recognition.catalog_matcher import load_catalog_issue_identity

IdentitySource = str  # "catalog" | "legacy" | "metadata" | "unknown"


@dataclass(frozen=True)
class CanonicalInventoryIdentity:
    title: str
    publisher: str | None
    issue_number: str
    catalog_issue_id: int | None
    catalog_series_id: int | None
    cover_image_url: str | None
    source: IdentitySource


def _split_metadata_identity_key(metadata_identity_key: str) -> tuple[str, str, str, str]:
    parts = (metadata_identity_key or "").split("|")
    parts += [""] * (4 - len(parts))
    publisher, series_title, issue_number, variant = parts[:4]
    return publisher, series_title, issue_number, variant


def _from_catalog(session: Session, catalog_issue_id: int) -> CanonicalInventoryIdentity | None:
    identity = load_catalog_issue_identity(session, catalog_issue_id)
    if identity is None:
        return None
    issue = session.get(CatalogIssue, catalog_issue_id)
    return CanonicalInventoryIdentity(
        title=identity.series or "Unknown",
        publisher=identity.publisher,
        issue_number=identity.issue_number or "",
        catalog_issue_id=catalog_issue_id,
        catalog_series_id=int(issue.series_id) if issue is not None else None,
        cover_image_url=identity.cover_image_url,
        source="catalog",
    )


def _from_legacy(session: Session, variant_id: int) -> CanonicalInventoryIdentity | None:
    variant = session.get(Variant, variant_id)
    if variant is None:
        return None
    issue = session.get(ComicIssue, variant.comic_issue_id)
    if issue is None:
        return None
    title_row = session.get(ComicTitle, issue.comic_title_id)
    publisher_name: str | None = None
    title_name = "Unknown"
    if title_row is not None:
        title_name = title_row.name
        publisher_row = session.get(Publisher, title_row.publisher_id)
        if publisher_row is not None:
            publisher_name = publisher_row.name
    return CanonicalInventoryIdentity(
        title=title_name,
        publisher=publisher_name,
        issue_number=issue.issue_number or "",
        catalog_issue_id=None,
        catalog_series_id=None,
        cover_image_url=None,
        source="legacy",
    )


def _from_metadata_key(metadata_identity_key: str | None) -> CanonicalInventoryIdentity:
    publisher, series_title, issue_number, _variant = _split_metadata_identity_key(metadata_identity_key or "")
    return CanonicalInventoryIdentity(
        title=series_title or "Unknown",
        publisher=publisher or None,
        issue_number=issue_number or "",
        catalog_issue_id=None,
        catalog_series_id=None,
        cover_image_url=None,
        source="metadata" if (series_title or publisher or issue_number) else "unknown",
    )


def resolve_identity_for_copy(session: Session, copy: InventoryCopy) -> CanonicalInventoryIdentity:
    """Resolve a copy's canonical identity: catalog -> legacy -> metadata key."""
    if copy.catalog_issue_id is not None:
        resolved = _from_catalog(session, int(copy.catalog_issue_id))
        if resolved is not None:
            return resolved
    if copy.variant_id is not None and legacy_variant_table_exists(session):
        resolved = _from_legacy(session, int(copy.variant_id))
        if resolved is not None:
            return resolved
    return _from_metadata_key(copy.metadata_identity_key)


def resolve_identities_for_copies(
    session: Session, copies: list[InventoryCopy]
) -> dict[int, CanonicalInventoryIdentity]:
    """Batch helper keyed by inventory_copy id."""
    out: dict[int, CanonicalInventoryIdentity] = {}
    for copy in copies:
        if copy.id is None:
            continue
        out[int(copy.id)] = resolve_identity_for_copy(session, copy)
    return out


def resolve_identity_by_copy_id(
    session: Session, inventory_copy_id: int
) -> CanonicalInventoryIdentity | None:
    copy = session.get(InventoryCopy, inventory_copy_id)
    if copy is None:
        return None
    return resolve_identity_for_copy(session, copy)
