"""P100-28 ComicVine issue lookup by normalized UPC/barcode."""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import get_settings
from app.services.catalog_ingestion_service import normalize_upc, upc_check_digit_valid
from app.services.comicvine_api_response import (
    comicvine_best_cover_url,
    payload_results,
)
from app.services.comicvine_catalog_importer import ComicVineCatalogImporter

logger = logging.getLogger(__name__)


def _empty_lookup(*, raw: dict[str, Any] | None = None) -> dict[str, Any]:
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
        "raw": raw,
    }


def _row_matches_barcode(row: dict[str, Any], normalized: str) -> bool:
    from app.services.comicvine_api_response import comicvine_barcodes_from_issue_row

    for candidate in comicvine_barcodes_from_issue_row(row):
        if normalize_upc(candidate) == normalized:
            return True
    return False


def _issue_from_row(row: dict[str, Any]) -> dict[str, Any]:
    volume = row.get("volume") if isinstance(row.get("volume"), dict) else {}
    publisher = volume.get("publisher") if isinstance(volume.get("publisher"), dict) else {}
    issue_id = row.get("id")
    cv_id = str(issue_id).split("-")[-1] if issue_id is not None else None
    return {
        "matched": True,
        "source": "comicvine",
        "comicvine_issue_id": cv_id,
        "series": (volume.get("name") or "").strip() or None,
        "issue_number": str(row.get("issue_number") or "").strip() or None,
        "publisher": (publisher.get("name") or "").strip() or None,
        "cover_date": str(row.get("cover_date") or "").strip() or None,
        "name": str(row.get("name") or "").strip() or None,
        "image_url": comicvine_best_cover_url(row.get("image")),
        "raw": row,
    }


def _search_issues_text(importer: ComicVineCatalogImporter, normalized: str) -> list[dict[str, Any]]:
    try:
        payload = importer._get(  # noqa: SLF001 — shared importer HTTP + rate limits
            "search/",
            params={
                "query": normalized,
                "resources": "issue",
                "limit": 10,
                "field_list": "id,issue_number,name,volume,cover_date,store_date,barcode,image",
            },
        )
    except Exception:
        logger.exception("p100.comicvine_barcode_lookup.text_search_failed barcode=%s", normalized)
        return []
    return payload_results(payload)


def lookup_comicvine_by_barcode(barcode: str) -> dict[str, Any]:
    normalized = normalize_upc(barcode)
    if not normalized or not upc_check_digit_valid(normalized):
        logger.info("p100.comicvine_barcode_lookup.skip invalid_barcode=%r", barcode)
        return _empty_lookup()

    settings = get_settings()
    if not (settings.comicvine_api_key or "").strip():
        logger.info("p100.comicvine_barcode_lookup.skip reason=no_api_key")
        return _empty_lookup()

    logger.info("p100.comicvine_barcode_lookup.started barcode=%s", normalized)
    importer = ComicVineCatalogImporter()

    rows: list[dict[str, Any]] = []
    try:
        rows = importer.search_issues_by_barcode(normalized, limit=5)
    except Exception:
        logger.exception("p100.comicvine_barcode_lookup.filter_search_failed barcode=%s", normalized)

    if not rows:
        logger.info("p100.comicvine_barcode_lookup.filter_empty trying_text_search")
        rows = _search_issues_text(importer, normalized)
        rows = [row for row in rows if _row_matches_barcode(row, normalized)]

    if not rows:
        logger.info("p100.comicvine_barcode_lookup.not_found barcode=%s", normalized)
        return _empty_lookup()

    result = _issue_from_row(rows[0])
    logger.info(
        "p100.comicvine_barcode_lookup.success barcode=%s comicvine_issue_id=%s",
        normalized,
        result.get("comicvine_issue_id"),
    )
    return result
