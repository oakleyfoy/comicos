"""Background identification worker for the async intake queue.

Each queued ``IntakeSessionItem`` is processed independently and asynchronously so the
phone scanner never blocks. Identification order favors instant/high-confidence sources:

    1. Learned barcode map (``comic_issue_barcodes``) — instant from prior accepts.
    2. Local catalog UPC table (``catalog_upc``).
    3. ComicVine on-demand lookup (needs review before inventory).

Every candidate is run through safe-match validation so we never auto-match the wrong book.
"""

from __future__ import annotations

import logging
import re
import threading
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from app.models.catalog_master import CatalogIssue, CatalogUpc
from app.models.intake_queue import (
    ComicIssueBarcode,
    ITEM_AUTO_MATCHED,
    ITEM_FAILED,
    ITEM_NEEDS_REVIEW,
    ITEM_PROCESSING,
    ITEM_READY_FOR_REVIEW,
    IntakeItemCandidate,
    IntakeSessionItem,
    MATCH_SOURCE_CATALOG_UPC,
    MATCH_SOURCE_COMICVINE,
    MATCH_SOURCE_LEARNED,
    utc_now,
)
from app.services.barcode_validation_service import (
    base_upc,
    supplement_extension,
    validate_barcode_catalog_match,
)
from app.services.catalog_ingestion_service import (
    comic_barcode_lookup_keys_for_search,
    direct_market_requires_supplement_key,
    normalize_upc,
)
from app.services.p100_barcode_extraction_service import extract_barcode_from_image
from app.services.p100_comicvine_barcode_lookup_service import lookup_comicvine_by_barcode
from app.services.photo_import_barcode_vision import normalize_comic_scan_barcode
from app.services.photo_import_storage_service import resolve_photo_import_storage_path
from app.services.recognition.catalog_matcher import load_catalog_issue_identity

logger = logging.getLogger(__name__)


def _year_from_cover_date(cover_date: str | None) -> str:
    match = re.search(r"(18|19|20)\d{2}", str(cover_date or ""))
    return match.group(0) if match else ""


def _clear_candidates(session: Session, item_id: int) -> None:
    rows = session.exec(
        select(IntakeItemCandidate).where(IntakeItemCandidate.item_id == item_id)
    ).all()
    for row in rows:
        session.delete(row)


def _add_candidate(session: Session, *, item_id: int, source: str, rank: int, data: dict[str, Any]) -> None:
    session.add(
        IntakeItemCandidate(
            item_id=item_id,
            catalog_issue_id=data.get("catalog_issue_id"),
            variant_id=data.get("variant_id"),
            publisher=(data.get("publisher") or None),
            series=(data.get("series") or None),
            issue_number=(data.get("issue_number") or None),
            cover_url=(data.get("cover_url") or None),
            score=float(data.get("score") or 0.0),
            source=source,
            rank=rank,
        )
    )


def _catalog_issue_year(session: Session, catalog_issue_id: int) -> str:
    issue = session.get(CatalogIssue, catalog_issue_id)
    if issue is not None and issue.cover_date is not None:
        return str(issue.cover_date.year)
    return ""


def _local_candidate(session: Session, *, source: str, catalog_issue_id: int, variant_id: int | None) -> dict[str, Any] | None:
    identity = load_catalog_issue_identity(session, catalog_issue_id)
    if identity is None:
        return None
    return {
        "source": source,
        "catalog_issue_id": catalog_issue_id,
        "variant_id": variant_id,
        "publisher": identity.publisher,
        "series": identity.series,
        "issue_number": identity.issue_number,
        "cover_url": identity.cover_image_url,
        "year": _catalog_issue_year(session, catalog_issue_id),
    }


def _resolve_candidate(session: Session, *, barcode: str) -> dict[str, Any] | None:
    """Find the best identification candidate for a normalized barcode (no validation yet)."""
    # 1. Learned barcode map — instant, from a prior user accept.
    learned = session.exec(
        select(ComicIssueBarcode).where(ComicIssueBarcode.normalized_barcode == barcode)
    ).first()
    if learned is not None:
        cand = _local_candidate(
            session,
            source=MATCH_SOURCE_LEARNED,
            catalog_issue_id=int(learned.catalog_issue_id),
            variant_id=learned.variant_id,
        )
        if cand is not None:
            cand["confidence"] = 0.99
            cand["learned_row"] = learned
            return cand

    # 2. Local catalog UPC table (longest key first; never base-only for direct market).
    for key in comic_barcode_lookup_keys_for_search(barcode):
        if len(key) < 17 and direct_market_requires_supplement_key(barcode):
            continue
        row = session.exec(select(CatalogUpc).where(CatalogUpc.normalized_upc == key)).first()
        if row is None or row.issue_id is None:
            continue
        cand = _local_candidate(
            session,
            source=MATCH_SOURCE_CATALOG_UPC,
            catalog_issue_id=int(row.issue_id),
            variant_id=int(row.variant_id) if row.variant_id is not None else None,
        )
        if cand is not None:
            cand["confidence"] = 0.97
            return cand

    # 3. ComicVine on-demand (needs review before inventory).
    cv = lookup_comicvine_by_barcode(barcode)
    if cv and cv.get("matched"):
        cover_date = str(cv.get("cover_date") or "")
        return {
            "source": MATCH_SOURCE_COMICVINE,
            "catalog_issue_id": None,
            "variant_id": None,
            "publisher": cv.get("publisher"),
            "series": cv.get("series"),
            "issue_number": cv.get("issue_number"),
            "cover_url": cv.get("image_url") or cv.get("cover_url"),
            "year": _year_from_cover_date(cover_date),
            "confidence": 0.8,
        }
    return None


def process_intake_item(session: Session, *, item_id: int) -> str:
    """Identify a single queued intake item. Returns the resulting status."""
    item = session.get(IntakeSessionItem, item_id)
    if item is None:
        return "missing"

    item.status = ITEM_PROCESSING
    session.add(item)
    session.commit()

    try:
        abs_path = resolve_photo_import_storage_path(item.storage_path, image_id=item_id)
        if not abs_path.is_file():
            return _fail(session, item, "Captured image is missing from storage.")
        image_bytes = abs_path.read_bytes()

        extraction = extract_barcode_from_image(
            image_bytes,
            allow_gpt_fallback=True,
            log_context=f"intake item_id={item_id}",
        )
        barcode = extraction.get("barcode") or item.raw_barcode
        if not barcode:
            return _finish(
                session,
                item,
                status=ITEM_FAILED,
                reason="Could not read a barcode from this photo.",
            )

        normalized = normalize_comic_scan_barcode(str(barcode)) or normalize_upc(str(barcode))
        item.raw_barcode = str(barcode)[:64]
        item.normalized_barcode = normalized[:64]
        item.base_upc = base_upc(normalized)[:16]
        item.extension = (supplement_extension(normalized) or None)
        logger.info(
            "intake.item.detected item_id=%s raw=%s normalized=%s base=%s ext=%s",
            item_id,
            barcode,
            normalized,
            item.base_upc,
            item.extension or "(none)",
        )

        # Modern direct-market UPC without the 5-digit supplement is ambiguous.
        if direct_market_requires_supplement_key(normalized):
            return _finish(
                session,
                item,
                status=ITEM_NEEDS_REVIEW,
                reason=f"Read base UPC {item.base_upc} but not the 5-digit supplement (ambiguous).",
            )

        candidate = _resolve_candidate(session, barcode=normalized)
        if candidate is None:
            return _finish(
                session,
                item,
                status=ITEM_NEEDS_REVIEW,
                reason=f"No catalog or ComicVine match for {normalized}.",
            )

        validation = validate_barcode_catalog_match(
            normalized,
            publisher=candidate.get("publisher"),
            issue_number=candidate.get("issue_number"),
            year=candidate.get("year"),
        )
        if validation.status != "exact_match":
            logger.warning(
                "intake.item.rejected item_id=%s barcode=%s reason=%s",
                item_id,
                normalized,
                validation.reason,
            )
            return _finish(
                session,
                item,
                status=ITEM_NEEDS_REVIEW,
                reason=f"Match failed validation: {validation.reason}",
            )

        # Store the validated candidate + apply it to the item.
        _clear_candidates(session, item_id)
        _add_candidate(
            session,
            item_id=item_id,
            source=str(candidate["source"]),
            rank=0,
            data={**candidate, "score": candidate.get("confidence", 0.0)},
        )
        item.match_source = str(candidate["source"])
        item.confidence = float(candidate.get("confidence") or 0.0)
        item.selected_catalog_issue_id = candidate.get("catalog_issue_id")
        item.selected_variant_id = candidate.get("variant_id")
        item.matched_publisher = (candidate.get("publisher") or None)
        item.matched_series = (candidate.get("series") or None)
        item.matched_issue_number = (candidate.get("issue_number") or None)
        item.matched_year = (candidate.get("year") or None)
        item.cover_url = (candidate.get("cover_url") or None)

        learned_row = candidate.get("learned_row")
        if isinstance(learned_row, ComicIssueBarcode):
            learned_row.times_seen += 1
            learned_row.updated_at = utc_now()
            session.add(learned_row)

        # Local high-confidence match -> auto matched. ComicVine -> needs human confirm.
        final_status = (
            ITEM_AUTO_MATCHED
            if candidate["source"] in {MATCH_SOURCE_LEARNED, MATCH_SOURCE_CATALOG_UPC}
            else ITEM_READY_FOR_REVIEW
        )
        return _finish(session, item, status=final_status, reason=None)
    except Exception as exc:  # noqa: BLE001
        logger.exception("intake.item.failed item_id=%s", item_id)
        return _fail(session, item, f"Processing error: {exc}")


def _finish(session: Session, item: IntakeSessionItem, *, status: str, reason: str | None) -> str:
    item.status = status
    item.reason = reason
    item.processed_at = utc_now()
    session.add(item)
    session.commit()
    logger.info("intake.item.done item_id=%s status=%s", item.id, status)
    return status


def _fail(session: Session, item: IntakeSessionItem, message: str) -> str:
    item.status = ITEM_FAILED
    item.error = message
    item.processed_at = utc_now()
    session.add(item)
    session.commit()
    return ITEM_FAILED


def run_intake_item_async(item_id: int) -> None:
    """Spawn a daemon thread that processes one item in its own DB session."""

    def _runner() -> None:
        from app.db.session import get_engine

        try:
            with Session(get_engine()) as bg_session:
                process_intake_item(bg_session, item_id=item_id)
        except Exception:
            logger.exception("intake.worker thread failed item_id=%s", item_id)

    thread = threading.Thread(target=_runner, name=f"intake-item-{item_id}", daemon=True)
    thread.start()
