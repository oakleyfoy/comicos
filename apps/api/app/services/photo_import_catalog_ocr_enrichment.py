"""E3: enrich photo-import text guesses from catalog OCR metadata."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlmodel import Session, select

from app.models.catalog_master import CatalogImage, CatalogOcrMetadata

if TYPE_CHECKING:
    from app.services.photo_import_candidate_service import PhotoImportMatchInput


def enrich_match_input_from_catalog_ocr(
    session: Session,
    *,
    catalog_issue_id: int,
    inp: PhotoImportMatchInput,
) -> PhotoImportMatchInput:
    from app.services.photo_import_candidate_service import PhotoImportMatchInput as MatchInput
    """Fill missing series/issue/publisher on match input from stored catalog OCR."""
    if inp.series_guess and inp.issue_number_guess and inp.publisher_guess:
        return inp
    row = session.exec(
        select(CatalogOcrMetadata)
        .join(CatalogImage, CatalogOcrMetadata.image_id == CatalogImage.id)
        .where(CatalogImage.issue_id == catalog_issue_id)
        .order_by(CatalogOcrMetadata.id.desc())
    ).first()
    if row is None:
        return inp
    series = inp.series_guess or (row.extracted_series or "").strip() or None
    issue = inp.issue_number_guess or (row.extracted_issue_number or "").strip() or None
    publisher = inp.publisher_guess or (row.extracted_publisher or "").strip() or None
    if series == inp.series_guess and issue == inp.issue_number_guess and publisher == inp.publisher_guess:
        return inp
    return MatchInput(
        publisher_guess=publisher or inp.publisher_guess,
        series_guess=series or inp.series_guess,
        issue_number_guess=issue or inp.issue_number_guess,
        visible_title_text=inp.visible_title_text,
        visible_character_text=inp.visible_character_text,
        subtitle_guess=inp.subtitle_guess,
        alternate_titles=inp.alternate_titles,
    )
