"""Catalog-on-demand: when a photo read has no catalog match, fetch the ComicVine
volume, import it (+issues/covers), and re-run catalog matching.

Runs in the background worker and (once) when loading the review session list.
Costs ~2–3 ComicVine API calls per book. No-op without COMICVINE_API_KEY.
"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass
from typing import Any, Literal

from sqlmodel import Session, select

from app.models.photo_import_vision_read import PhotoImportVisionRead
from app.services.catalog_ingestion_service import (
    catalog_series_id_for_comicvine_volume,
    normalize_issue_number,
    normalize_series_name,
    normalize_upc,
    series_names_compatible,
)
from app.services.catalog_publisher_registry import is_international_publisher

logger = logging.getLogger(__name__)

OnDemandOutcome = Literal["imported", "no_volume", "unavailable", "failed"]

_MAX_YEAR_GAP = 4


@dataclass(frozen=True)
class ComicvineOndemandImportResult:
    outcome: OnDemandOutcome
    catalog_series_id: int | None = None
    comicvine_volume_id: int | None = None

# Background backfill: cap ComicVine work per pass and avoid duplicate threads per session.
_MAX_ONDEMAND_PER_PASS = 8
_inflight_sessions: set[int] = set()
_inflight_lock = threading.Lock()


def _parse_year(value: str | None) -> int | None:
    if not (value or "").strip():
        return None
    m = re.search(r"(19|20)\d{2}", value)
    return int(m.group(0)) if m else None


def _effective_year_for_volume_search(read: PhotoImportVisionRead) -> int | None:
    """Best-effort year for ComicVine volume pick when GPT left year blank."""
    year = _parse_year(read.year)
    if year is not None:
        return year
    year = _parse_year(read.cover_date)
    if year is not None:
        return year
    blob = " ".join(
        [
            (read.series or ""),
            (read.issue_title or ""),
            (read.publisher or ""),
        ]
    ).casefold()
    if "rebirth" in blob or "reborn" in blob:
        return 2017
    return None


def _volume_start_year(row: dict[str, Any]) -> int | None:
    start_year = row.get("start_year")
    try:
        return int(start_year) if start_year is not None else None
    except (TypeError, ValueError):
        return None


def _prefer_volume_tiebreak(
    candidate: dict[str, Any],
    incumbent: dict[str, Any] | None,
    *,
    year: int | None,
) -> bool:
    """True if candidate should replace incumbent when scores are equal."""
    if incumbent is None:
        return True
    cand_sy = _volume_start_year(candidate)
    inc_sy = _volume_start_year(incumbent)
    if year is not None and cand_sy is not None and inc_sy is not None:
        cand_gap = abs(cand_sy - year)
        inc_gap = abs(inc_sy - year)
        if cand_gap != inc_gap:
            return cand_gap < inc_gap
    if cand_sy is not None and inc_sy is not None and cand_sy != inc_sy:
        return cand_sy > inc_sy
    return False


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
    elif series_names_compatible(norm_target, norm_cand):
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
    elif year is None and start_year_int is not None:
        # No GPT year: slightly favor modern volumes (Rebirth-era imports).
        score += min(max(start_year_int - 1980, 0), 40) * 0.5

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
    best_row: dict[str, Any] | None = None
    for row in candidates:
        score = _score_volume(row, series=series, issue_number=issue_number, year=year)
        if score is None:
            continue
        if score > best_score or (
            score == best_score and _prefer_volume_tiebreak(row, best_row, year=year)
        ):
            best_score = score
            best_row = row
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


def _find_comicvine_volume_id_via_barcode(
    importer: Any,
    read: PhotoImportVisionRead,
) -> int | None:
    normalized = normalize_upc(read.barcode or "")
    if len(normalized) < 11:
        return None
    try:
        rows = importer.search_issues_by_barcode(read.barcode or "")
    except Exception:
        logger.exception("photo_import.ondemand.barcode_search_failed read_id=%s", read.id)
        return None
    for row in rows:
        volume_id = importer.volume_id_from_issue_api_row(row)
        if volume_id is None:
            continue
        logger.info(
            "photo_import.ondemand.barcode_hit read_id=%s barcode=%s comicvine_issue_id=%s volume_id=%s",
            read.id,
            normalized,
            row.get("id"),
            volume_id,
        )
        return volume_id
    return None


def _find_comicvine_volume_id(
    importer: Any,
    read: PhotoImportVisionRead,
) -> int | None:
    volume_id = _find_comicvine_volume_id_via_barcode(importer, read)
    if volume_id is not None:
        return volume_id
    series = (read.series or "").strip()
    issue_number = (read.issue_number or "").strip()
    year = _effective_year_for_volume_search(read)
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


def run_comicvine_ondemand_import(session: Session, read: PhotoImportVisionRead) -> ComicvineOndemandImportResult:
    """Search ComicVine and import one volume for this read. Does not rematch."""
    series = (read.series or "").strip()
    issue_number = (read.issue_number or "").strip()
    has_barcode = len(normalize_upc(read.barcode or "")) >= 11
    if (not series or not issue_number) and not has_barcode:
        return ComicvineOndemandImportResult("unavailable")

    from app.services.comicvine_catalog_importer import ComicVineCatalogImporter

    importer = ComicVineCatalogImporter()
    if importer.initialize_or_explain():
        return ComicvineOndemandImportResult("unavailable")

    try:
        volume_id = _find_comicvine_volume_id(importer, read)
    except Exception:
        logger.exception("photo_import.ondemand.search_failed read_id=%s series=%r", read.id, series)
        return ComicvineOndemandImportResult("failed")

    if volume_id is None:
        logger.info(
            "photo_import.ondemand.no_volume read_id=%s series=%r issue=%s year=%s candidates=%d",
            read.id,
            series,
            issue_number,
            read.year,
            0,
        )
        return ComicvineOndemandImportResult("no_volume")

    try:
        stats = importer.import_single_volume(session, comicvine_volume_id=volume_id, import_issues=True)
    except Exception:
        logger.exception("photo_import.ondemand.import_failed read_id=%s volume_id=%s", read.id, volume_id)
        return ComicvineOndemandImportResult("failed")

    if stats.throttled or (stats.failures and stats.created_issues == 0 and stats.updated_issues == 0):
        return ComicvineOndemandImportResult("failed")

    prefer_year = _effective_year_for_volume_search(read)
    from app.models.catalog_master import CatalogPublisher

    publisher_id: int | None = None
    pub_name = (read.publisher or "").strip()
    if pub_name:
        pub_row = session.exec(
            select(CatalogPublisher).where(
                CatalogPublisher.normalized_name == normalize_series_name(pub_name)
            )
        ).first()
        if pub_row is not None and pub_row.id is not None:
            publisher_id = int(pub_row.id)

    catalog_series_id = catalog_series_id_for_comicvine_volume(
        session,
        volume_id=volume_id,
        publisher_id=publisher_id,
        prefer_start_year=prefer_year,
    )
    if catalog_series_id is None and stats.imported_series_ids:
        catalog_series_id = int(stats.imported_series_ids[0])
    logger.info(
        "photo_import.ondemand.imported read_id=%s volume_id=%s series_id=%s issues_created=%s",
        read.id,
        volume_id,
        catalog_series_id,
        stats.created_issues,
    )
    return ComicvineOndemandImportResult(
        "imported",
        catalog_series_id=catalog_series_id,
        comicvine_volume_id=volume_id,
    )


def try_comicvine_ondemand_for_read(session: Session, read: PhotoImportVisionRead) -> bool:
    """One attempt per read: import from CV if needed, then rematch. True if catalog linked."""
    if read.catalog_issue_id is not None:
        return True
    if _ondemand_already_finalized(read):
        return False

    result = run_comicvine_ondemand_import(session, read)
    if result.outcome == "imported":
        from app.services.photo_import_catalog_match_service import (
            match_and_apply,
            normalized_read_barcode,
            rematch_after_comicvine_import,
        )

        if normalized_read_barcode(read):
            match_and_apply(session, read)
            if read.catalog_issue_id is None:
                rematch_after_comicvine_import(session, read, catalog_series_id=result.catalog_series_id)
        else:
            rematch_after_comicvine_import(session, read, catalog_series_id=result.catalog_series_id)
        _mark_ondemand_attempt(read, "imported")
        session.add(read)
        return read.catalog_issue_id is not None
    if result.outcome == "no_volume":
        _mark_ondemand_attempt(read, "no_volume")
        session.add(read)
        return False
    if result.outcome in ("unavailable", "failed"):
        _mark_ondemand_attempt(read, result.outcome)
        session.add(read)
    # leave unmarked only for unexpected paths
    return False


def backfill_comicvine_ondemand_for_reads(session: Session, reads: list[PhotoImportVisionRead]) -> None:
    for read in reads:
        try_comicvine_ondemand_for_read(session, read)
    session.commit()


def _run_session_backfill_thread(session_id: int) -> None:
    """Background worker: pull ComicVine for unmatched reads in a session, bounded per pass."""
    from app.db.session import get_engine

    try:
        from app.services.comicvine_catalog_importer import ComicVineCatalogImporter

        if ComicVineCatalogImporter().initialize_or_explain():
            return  # No COMICVINE_API_KEY configured — nothing to do.

        with Session(get_engine()) as session:
            reads = session.exec(
                select(PhotoImportVisionRead).where(
                    PhotoImportVisionRead.session_id == session_id
                )
            ).all()
            processed = 0
            for read in reads:
                if processed >= _MAX_ONDEMAND_PER_PASS:
                    break
                if read.catalog_issue_id is not None or _ondemand_already_finalized(read):
                    continue
                processed += 1
                try:
                    try_comicvine_ondemand_for_read(session, read)
                    session.commit()
                except Exception:
                    logger.warning(
                        "photo_import.ondemand.backfill_failed read_id=%s", read.id, exc_info=True
                    )
                    session.rollback()
    except Exception:
        logger.exception("photo_import.ondemand.backfill_thread_failed session_id=%s", session_id)
    finally:
        with _inflight_lock:
            _inflight_sessions.discard(session_id)


def kick_comicvine_ondemand_backfill(*, session_id: int) -> bool:
    """Start a background ComicVine pull for a session's unmatched reads (no-op if already running)."""
    with _inflight_lock:
        if session_id in _inflight_sessions:
            return False
        _inflight_sessions.add(session_id)
    thread = threading.Thread(
        target=_run_session_backfill_thread,
        args=(session_id,),
        name=f"cv-ondemand-{session_id}",
        daemon=True,
    )
    thread.start()
    return True
