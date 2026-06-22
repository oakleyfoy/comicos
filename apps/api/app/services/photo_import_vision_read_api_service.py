"""P100-24 vision read API helpers."""

from __future__ import annotations

from app.models.photo_import_vision_read import PhotoImportVisionRead
from app.schemas.photo_import import (
    PhotoImportCatalogAlternate,
    PhotoImportVisionReadPayload,
)


def vision_read_to_payload(row: PhotoImportVisionRead) -> PhotoImportVisionReadPayload:
    raw = row.raw_response or {}
    identity = raw.get("catalog_identity") or {}
    alternates: list[PhotoImportCatalogAlternate] = []
    for entry in raw.get("catalog_alternates", []) or []:
        if not isinstance(entry, dict) or entry.get("catalog_issue_id") is None:
            continue
        alternates.append(
            PhotoImportCatalogAlternate(
                catalog_issue_id=int(entry["catalog_issue_id"]),
                series=entry.get("series"),
                issue_number=entry.get("issue_number"),
                publisher=entry.get("publisher"),
                cover_url=entry.get("cover_url"),
                confidence=entry.get("confidence"),
            )
        )
    return PhotoImportVisionReadPayload(
        id=int(row.id or 0),
        session_id=int(row.session_id),
        image_id=int(row.image_id),
        detection_index=int(getattr(row, "detection_index", 0) or 0),
        publisher=row.publisher,
        series=row.series,
        issue_number=row.issue_number,
        issue_title=row.issue_title,
        variant_description=row.variant_description,
        year=row.year,
        cover_date=row.cover_date,
        barcode=row.barcode,
        confidence=row.confidence,
        reasoning=row.reasoning,
        possible_alternates=row.possible_alternates,
        raw_response=row.raw_response,
        is_correct=row.is_correct,
        feedback_notes=row.feedback_notes,
        added_to_inventory=bool(getattr(row, "added_to_inventory", False)),
        catalog_issue_id=getattr(row, "catalog_issue_id", None),
        catalog_variant_id=getattr(row, "catalog_variant_id", None),
        catalog_cover_url=getattr(row, "catalog_cover_url", None),
        match_method=getattr(row, "match_method", None),
        match_confidence=getattr(row, "match_confidence", None),
        catalog_series=identity.get("series"),
        catalog_issue_number=identity.get("issue_number"),
        catalog_publisher=identity.get("publisher"),
        catalog_alternates=alternates,
        created_at=row.created_at,
    )
