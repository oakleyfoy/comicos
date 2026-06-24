"""Orchestrate GPT Comic Read + barcode extraction + catalog / ComicVine verification."""

from __future__ import annotations

import logging
from typing import Any, Literal

from sqlmodel import Session

from app.services.gpt_comic_read_service import GptComicReadResult, read_comic_with_gpt
from app.services.p100_barcode_extraction_service import extract_barcode_from_image
from app.services.p100_comicvine_barcode_lookup_service import lookup_comicvine_by_barcode
from app.services.p100_gpt_catalog_match_service import match_gpt_read_to_catalog

logger = logging.getLogger(__name__)

FinalMatchSource = Literal["comicvine_barcode", "catalog", "gpt_only"]


def _gpt_read_dict(gpt: GptComicReadResult) -> dict[str, Any]:
    return {
        "publisher": gpt.publisher,
        "series": gpt.series,
        "issue_number": gpt.issue_number,
        "issue_title": gpt.issue_title,
        "year": gpt.year,
        "cover_date": gpt.cover_date,
        "variant_description": gpt.variant_description,
        "barcode": gpt.barcode,
        "confidence": gpt.confidence,
        "reasoning": gpt.reasoning,
        "possible_alternates": gpt.possible_alternates,
        "raw_response": gpt.raw_response,
        "model": gpt.model,
        "image_width": gpt.image_width,
        "image_height": gpt.image_height,
    }


def resolve_final_match_source(
    *,
    comicvine_barcode_match: dict[str, Any],
    catalog_match: dict[str, Any],
) -> FinalMatchSource:
    if comicvine_barcode_match.get("matched"):
        return "comicvine_barcode"
    if catalog_match.get("matched"):
        return "catalog"
    return "gpt_only"


def run_gpt_comic_read_enriched(
    session: Session,
    image_bytes: bytes,
    *,
    filename: str | None = None,
) -> dict[str, Any]:
    gpt = read_comic_with_gpt(image_bytes, filename=filename)
    barcode_read = extract_barcode_from_image(
        image_bytes,
        log_context=f"p100_gpt_comic_read filename={filename}",
    )
    extracted = barcode_read.get("barcode")

    catalog = match_gpt_read_to_catalog(session, gpt, extracted_barcode=extracted)
    catalog_match = catalog.as_dict()

    comicvine_barcode_match = _empty_comicvine()
    if extracted:
        comicvine_barcode_match = lookup_comicvine_by_barcode(str(extracted))

    final_match_source = resolve_final_match_source(
        comicvine_barcode_match=comicvine_barcode_match,
        catalog_match=catalog_match,
    )
    logger.info("p100.gpt_comic_read.final_match_source=%s", final_match_source)

    return {
        "gpt_read": _gpt_read_dict(gpt),
        "catalog_match": catalog_match,
        "barcode_read": barcode_read,
        "comicvine_barcode_match": comicvine_barcode_match,
        "final_match_source": final_match_source,
    }


def _empty_comicvine() -> dict[str, Any]:
    return {
        "matched": False,
        "source": "comicvine",
        "comicvine_issue_id": None,
        "series": None,
        "issue_number": None,
        "publisher": None,
        "cover_date": None,
        "name": None,
        "image_url": None,
        "raw": None,
    }
