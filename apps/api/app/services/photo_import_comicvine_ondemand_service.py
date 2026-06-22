"""Catalog-on-demand: when a photo read has no catalog match, fetch the ComicVine
volume, import it (+issues/covers), and re-run catalog matching.

Runs in the background worker and (once) when loading the review session list.
Costs ~2–3 ComicVine API calls per book. No-op without COMICVINE_API_KEY.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Literal

from sqlmodel import Session

from app.models.photo_import_vision_read import PhotoImportVisionRead
from app.services.catalog_ingestion_service import normalize_issue_number, normalize_series_name
from app.services.catalog_publisher_registry import is_international_publisher

logger = logging.getLogger(__name__)

OnDemandOutcome = Literal["imported", "no_volume", "unavailable", "failed"]

_MAX_YEAR_GAP = 4


def _parse_year(value: str | None) -> int | None:
    if not (value or "").strip():
        return None
    m = re.search(r"(19|20)\d{2}", value)
    return int(m.group(0)) if m else None


def _candidate_publisher(row: dict[str, Any]) -> str:
    pub = row.get("publisher")
    if isinstance(pub, dict):
        return str(pub.get("name") or "")
    return ""


def _score_volume(row: dict[str, Any], *, series: str, issue_number: str | None, year: int | None) -> float | None:
    name = str(row.get("name") or "")
    if not name:
        return None

    norm_target = normalize_series_name(series)
    norm_cand = normalize_series_name(name)
    if not norm_target or not norm_cand:
        return None

    if norm_cand == norm_target:
        score = 1000.0
    elif norm_cand.startswith(norm_target) or norm_target.startswith(norm_cand):
        score = 600.0
    else:
        return None

    publisher = _candidate_publisher(row)
    if is_international_publisher(publisher):
        score -= 300.0

    start_year = row.get("start_year")
    try:
        start_year_int = int(start_year) if start_year is not None else None
    except (TypeError, ValueError):
        start_year_int = None

    if year is not None and start_year_int is not None:
        gap = abs(start_year_int - year)
        if gap > _MAX_YEAR_GAP:
            return None
        score += 400.0 - gap * 80.0
    elif year is not None and start_year_int is None:
        score -= 50.0

    norm_issue = normalize_issue_number(issue_number or "")
    if norm_issue.isdigit():
        try:
            count = int(row.get("count_of_issues") or 0)
        except (TypeError, ValueError):
            count = 0
        if count and count < int(norm_issue):
            score -= 200.0

    return score


def select_comicvine_volume_id(
    candidates: list[dict[str, Any]],
    *,
    series: str,
    issue_number: str | None,
    year: int | None,
) -> int | None:
    best_id: int | None = None
    best_score = float("-inf")
    for row in candidates:
        score = _score_volume(row, series=series, issue_number=issue_number, year=year)
        if score is None:
            continue
        if score > best_score:
            best_score = score
            vid = row.get("id")
            try:
                best_id = int(vid) if vid is not None else None
            except (TypeError, ValueError):
                best_id = None
    return best_id


def _mark_ondemand_attempt(read: PhotoImportVisionRead, result: str) -> None:
    raw = dict(read.raw_response or {})
    raw["comicvine_ondemand_attempted"] = True
    raw["comicvine_ondemand_result"] = result
    read.raw_response = raw


def _ondemand_already_finalized(read: PhotoImportVisionRead) -> bool:
    return bool((read.raw_response or {}).get("comicvine_ondemand_attempted"))


def _find_comicvine_volume_id(
    importer: Any,
    read: PhotoImportVisionRead,
) -> int | None:
    series = (read.series or "").strip()
    issue_number = (read.issue_number or "").strip()
    year = _parse_year(read.year)
    publisher = (read.publisher or "").strip()

    queries: list[str] = []
    if series:
        queries.append(series)
        if ":" in series:
            head = series.split(":", 1)[0].strip()
            if head and head != series:
                queries.append(head)
        if publisher:
            queries.append(f"{series} {publisher}")

    seen: set[str] = set()
    for query in queries:
        key = query.strip().casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        try:
            candidates = importer.search_volumes(query, limit=30)
        except Exception:
            logger.exception("photo_import.ondemand.search_failed read_id=%s query=%r", read.id, query)
            continue
        volume_id = select_comicvine_volume_id(
            candidates,
            series=series,
            issue_number=issue_number,
            year=year,
        )
        if volume_id is not None:
            return volume_id
    return None


def run_comicvine_ondemand_import(session: Session, read: PhotoImportVisionRead) -> OnDemandOutcome:
    """Search ComicVine and import one volume for this read. Does not rematch."""
    series = (read.series or "").strip()
    issue_number = (read.issue_number or "").strip()
    if not series or not issue_number:
        return "unavailable"

    from app.services.comicvine_catalog_importer import ComicVineCatalogImporter

    importer = ComicVineCatalogImporter()
    if importer.initialize_or_explain():
        return "unavailable"

    try:
        volume_id = _find_comicvine_volume_id(importer, read)
    except Exception:
        logger.exception("photo_import.ondemand.search_failed read_id=%s series=%r", read.id, series)
        return "failed"

    if volume_id is None:
        logger.info(
            "photo_import.ondemand.no_volume read_id=%s series=%r issue=%s year=%s candidates=%d",
            read.id,
            series,
            issue_number,
            read.year,
            0,
        )
        return "no_volume"

    try:
        stats = importer.import_single_volume(session, comicvine_volume_id=volume_id, import_issues=True)
    except Exception:
        logger.exception("photo_import.ondemand.import_failed read_id=%s volume_id=%s", read.id, volume_id)
        return "failed"

    if stats.throttled or (stats.failures and stats.created_issues == 0 and stats.updated_issues == 0):
        return "failed"

    logger.info(
        "photo_import.ondemand.imported read_id=%s volume_id=%s series_created=%s issues_created=%s",
        read.id,
        volume_id,
        stats.series_created,
        stats.created_issues,
    )
    return "imported"


def try_comicvine_ondemand_for_read(session: Session, read: PhotoImportVisionRead) -> bool:
    """One attempt per read: import from CV if needed, then rematch. True if catalog linked."""
    if read.catalog_issue_id is not None:
        return True
    if _ondemand_already_finalized(read):
        return False

    outcome = run_comicvine_ondemand_import(session, read)
    if outcome == "imported":
        from app.services.photo_import_catalog_match_service import match_and_apply

        match_and_apply(session, read)
        _mark_ondemand_attempt(read, "imported")
        session.add(read)
        return read.catalog_issue_id is not None
    if outcome == "no_volume":
        _mark_ondemand_attempt(read, "no_volume")
        session.add(read)
        return False
    if outcome in ("unavailable", "failed"):
        _mark_ondemand_attempt(read, outcome)
        session.add(read)
    # leave unmarked only for unexpected paths
    return False


def backfill_comicvine_ondemand_for_reads(session: Session, reads: list[PhotoImportVisionRead]) -> None:
    for read in reads:
        try_comicvine_ondemand_for_read(session, read)
    session.commit()
