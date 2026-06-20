"""P100-24 vision read API helpers."""

from __future__ import annotations

from app.models.photo_import_vision_read import PhotoImportVisionRead
from app.schemas.photo_import import PhotoImportVisionReadPayload


def vision_read_to_payload(row: PhotoImportVisionRead) -> PhotoImportVisionReadPayload:
    return PhotoImportVisionReadPayload(
        id=int(row.id or 0),
        session_id=int(row.session_id),
        image_id=int(row.image_id),
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
        created_at=row.created_at,
    )
