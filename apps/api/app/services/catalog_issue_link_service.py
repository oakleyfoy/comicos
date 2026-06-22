"""Resolve a master-catalog issue id from identity fields or a barcode.

Part of the inventory catalog unification: copy-creating write paths use this to
link new ``inventory_copy`` rows to ``catalog_issue`` (the canonical catalog) when
a confident match exists. Matching order: barcode/UPC first (exact), then a scored
text match on series + issue number (+ publisher).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, select

from app.models.catalog_master import CatalogUpc
from app.services.catalog_ingestion_service import normalize_issue_number, normalize_upc
from app.services.recognition.recognition_catalog_candidate_service import search_catalog_candidates


@dataclass(frozen=True)
class CatalogLinkResult:
    catalog_issue_id: int | None
    catalog_variant_id: int | None
    method: str  # "upc" | "text" | "none"


_NONE = CatalogLinkResult(None, None, "none")


def resolve_catalog_issue_link(
    session: Session,
    *,
    series: str | None = None,
    issue_number: str | None = None,
    publisher: str | None = None,
    barcode: str | None = None,
) -> CatalogLinkResult:
    # 1) Exact barcode/UPC match.
    if barcode and barcode.strip():
        normalized = normalize_upc(barcode)
        if normalized:
            row = session.exec(
                select(CatalogUpc).where(CatalogUpc.normalized_upc == normalized)
            ).first()
            if row is not None and row.issue_id is not None:
                return CatalogLinkResult(int(row.issue_id), row.variant_id and int(row.variant_id), "upc")

    # 2) Scored text match on series (+ issue number + publisher).
    if series and series.strip():
        candidates = search_catalog_candidates(
            session,
            series=series,
            issue_number=issue_number,
            publisher=publisher,
            limit=3,
        )
        if candidates:
            top = candidates[0]
            # If an issue number was provided, require it to match the candidate.
            if issue_number and issue_number.strip():
                if normalize_issue_number(issue_number) != normalize_issue_number(top.issue_number or ""):
                    return _NONE
            return CatalogLinkResult(int(top.catalog_issue_id), None, "text")

    return _NONE
