"""Centralized display-metadata resolution for inventory copies.

Retailer imports (Midtown saved HTML, etc.) only capture enough information to
*identify* a book: title, publisher, quantity, price, image, order date, order
status. ComicOS is responsible for resolving the rich display metadata (cover,
release date, FOC date, issue number, variant, release status) by matching that
to the catalog.

This module owns the source-priority chains so that the inventory list and
detail endpoints render consistent, never-broken data regardless of whether a
catalog match was found. Missing data must surface a "needs catalog review"
state rather than a blank/broken UI, and a failed/incomplete enrichment must
never block import.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from sqlmodel import Session, select

from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.services.cover_images import cover_fetch_path

CoverSource = Literal[
    "catalog_cover",
    "retailer_remote",
    "local_saved_html",
    "placeholder",
]

ReleaseStatusDisplay = Literal["released", "not_released_yet", "unknown"]

# Enrichment statuses that mean "the catalog could not confidently fill in the
# rich metadata for this copy". These drive the Needs-catalog-review badge.
_UNRESOLVED_ENRICHMENT_STATUSES = frozenset({"needs_review", "skipped", "pending", "error"})


@dataclass(frozen=True)
class InventoryDisplayMetadata:
    """Resolved, display-ready metadata for a single inventory copy."""

    cover_image_url: str | None
    cover_source: CoverSource
    release_date: date | None
    foc_date: date | None
    release_status: ReleaseStatusDisplay
    needs_catalog_review: bool
    catalog_match_id: int | None
    enrichment_status: str | None


def _is_remote_url(value: str | None) -> bool:
    if not value:
        return False
    lowered = value.strip().lower()
    return lowered.startswith("http://") or lowered.startswith("https://")


def classify_cover_source(
    *,
    has_catalog_cover: bool,
    source_image_url: str | None,
) -> CoverSource:
    """Classify where a copy's best available cover image comes from.

    Priority follows the retailer-import source chain: a resolved catalog cover
    wins, then a remote retailer image, then a locally saved HTML image, then a
    placeholder when nothing usable exists.
    """

    if has_catalog_cover:
        return "catalog_cover"
    if _is_remote_url(source_image_url):
        return "retailer_remote"
    if source_image_url:
        return "local_saved_html"
    return "placeholder"


def compute_release_status(
    *,
    release_date: date | None,
    today: date | None = None,
) -> ReleaseStatusDisplay:
    """Derive a display release status from the resolved release date."""

    if release_date is None:
        return "unknown"
    reference = today or date.today()
    if release_date <= reference:
        return "released"
    return "not_released_yet"


def _lookup_release_issue(
    session: Session,
    *,
    owner_user_id: int,
    catalog_match_id: int | None,
) -> ReleaseIssue | None:
    if catalog_match_id is None:
        return None
    return session.exec(
        select(ReleaseIssue).where(
            ReleaseIssue.id == catalog_match_id,
            ReleaseIssue.owner_user_id == owner_user_id,
        )
    ).first()


def resolve_inventory_display_metadata(
    *,
    catalog_cover_fetch_path: str | None,
    source_image_url: str | None,
    copy_release_date: date | None,
    copy_release_status: str | None,
    order_item_foc_date: date | None,
    catalog_match_id: int | None,
    enrichment_status: str | None,
    release_issue: ReleaseIssue | None = None,
    today: date | None = None,
) -> InventoryDisplayMetadata:
    """Resolve display metadata from pre-fetched inputs (pure / no DB access).

    Source priority chains (highest first):
      Cover:        catalog cover -> retailer remote image -> local saved HTML -> placeholder
      Release date: copy.release_date -> matched release_issue.release_date -> null
      FOC date:     order_item.foc_date -> matched release_issue.foc_date -> null
    """

    has_catalog_cover = bool(catalog_cover_fetch_path)
    cover_source = classify_cover_source(
        has_catalog_cover=has_catalog_cover,
        source_image_url=source_image_url,
    )
    if has_catalog_cover:
        cover_image_url: str | None = catalog_cover_fetch_path
    elif source_image_url:
        cover_image_url = source_image_url
    else:
        cover_image_url = None

    release_date = copy_release_date
    if release_date is None and release_issue is not None:
        release_date = release_issue.release_date

    foc_date = order_item_foc_date
    if foc_date is None and release_issue is not None:
        foc_date = release_issue.foc_date

    # Prefer a real computed status when we have a date; otherwise honour any
    # explicit non-"unknown" status already stored on the copy.
    release_status = compute_release_status(release_date=release_date, today=today)
    if release_status == "unknown" and copy_release_status in ("released", "not_released_yet"):
        release_status = copy_release_status  # type: ignore[assignment]

    needs_catalog_review = (
        catalog_match_id is None
        or release_date is None
        or (enrichment_status or "").lower() in _UNRESOLVED_ENRICHMENT_STATUSES
    )

    return InventoryDisplayMetadata(
        cover_image_url=cover_image_url,
        cover_source=cover_source,
        release_date=release_date,
        foc_date=foc_date,
        release_status=release_status,
        needs_catalog_review=needs_catalog_review,
        catalog_match_id=catalog_match_id,
        enrichment_status=enrichment_status,
    )


def resolve_inventory_display_metadata_for_copy(
    session: Session,
    *,
    owner_user_id: int,
    primary_cover_image_id: int | None,
    source_image_url: str | None,
    copy_release_date: date | None,
    copy_release_status: str | None,
    order_item_foc_date: date | None,
    catalog_match_id: int | None,
    enrichment_status: str | None,
    today: date | None = None,
) -> InventoryDisplayMetadata:
    """DB-aware convenience wrapper that resolves the catalog cover + release issue."""

    catalog_cover_fetch_path = (
        cover_fetch_path(primary_cover_image_id) if primary_cover_image_id else None
    )
    release_issue = _lookup_release_issue(
        session,
        owner_user_id=owner_user_id,
        catalog_match_id=catalog_match_id,
    )
    return resolve_inventory_display_metadata(
        catalog_cover_fetch_path=catalog_cover_fetch_path,
        source_image_url=source_image_url,
        copy_release_date=copy_release_date,
        copy_release_status=copy_release_status,
        order_item_foc_date=order_item_foc_date,
        catalog_match_id=catalog_match_id,
        enrichment_status=enrichment_status,
        release_issue=release_issue,
        today=today,
    )


__all__ = [
    "CoverSource",
    "ReleaseStatusDisplay",
    "InventoryDisplayMetadata",
    "classify_cover_source",
    "compute_release_status",
    "resolve_inventory_display_metadata",
    "resolve_inventory_display_metadata_for_copy",
]
