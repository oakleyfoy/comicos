"""On-demand LOCG calendar hydrate when import catalog resolution misses."""

from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Iterator

from sqlmodel import Session, select

from app.models.external_catalog import ExternalCatalogIssue
from app.services.external_catalog.league_of_comic_geeks import (
    LOCG_SOURCE_NAME,
    LocgHttpClient,
    LocgListIssueStub,
    fetch_release_date_page,
    parse_release_date_page,
    stub_to_detail_seed,
)
from app.services.external_catalog.locg_live_html import parse_release_date_live_page
from app.services.external_catalog.normalization import split_series_and_issue_title
from app.services.external_catalog.sync_service import SyncCounters, _process_detail_url
from app.services.import_catalog_resolution_service import (
    _issue_number_key,
    _title_tokens,
    _token_overlap_score,
    normalize_import_title,
)

logger = logging.getLogger(__name__)

DEFAULT_UPCOMING_WEEKS_WITHOUT_DATE = 3
UPCOMING_WEEKS_AFTER_PARSED = 4
PROCESS_CACHE_TTL_SECONDS = 300.0


def _hydrate_timeout_seconds() -> float:
    raw = os.environ.get("IMPORT_LOCG_HYDRATE_TIMEOUT", "45").strip()
    try:
        return max(5.0, float(raw))
    except ValueError:
        return 45.0


def import_locg_hydrate_enabled() -> bool:
    raw = os.environ.get("IMPORT_LOCG_HYDRATE", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


@dataclass
class ImportLocgHydrateResult:
    attempted: bool = False
    hydrated: bool = False
    external_issue_id: int | None = None
    searched_dates: list[str] = field(default_factory=list)
    matched_stub_title: str | None = None
    no_match_reason: str | None = None
    cached: bool = False
    error: str | None = None


@dataclass
class ImportLocgHydrateRequestCache:
    _line_attempts: set[str] = field(default_factory=set)
    calendar_fetch_count: int = 0
    detail_fetch_count: int = 0

    def line_key(
        self,
        *,
        title: str,
        issue_number: str,
        parsed_release_date: date | None,
    ) -> str:
        date_part = parsed_release_date.isoformat() if parsed_release_date else "none"
        return f"{normalize_import_title(title)}|{_issue_number_key(issue_number)}|{date_part}"

    def mark_line_attempted(self, key: str) -> None:
        self._line_attempts.add(key)

    def line_was_attempted(self, key: str) -> bool:
        return key in self._line_attempts


_hydrate_request_cache: ContextVar[ImportLocgHydrateRequestCache | None] = ContextVar(
    "import_locg_hydrate_request_cache",
    default=None,
)

_process_hydrate_cache: dict[str, tuple[float, ImportLocgHydrateResult]] = {}


def get_import_locg_hydrate_request_cache() -> ImportLocgHydrateRequestCache:
    cache = _hydrate_request_cache.get()
    if cache is None:
        cache = ImportLocgHydrateRequestCache()
        _hydrate_request_cache.set(cache)
    return cache


@contextmanager
def import_locg_hydrate_request_scope() -> Iterator[ImportLocgHydrateRequestCache]:
    cache = ImportLocgHydrateRequestCache()
    token = _hydrate_request_cache.set(cache)
    try:
        yield cache
    finally:
        _hydrate_request_cache.reset(token)


def _align_to_wednesday(day: date) -> date:
    cursor = day
    while cursor.weekday() != 2:
        cursor += timedelta(days=1)
    return cursor


def _dedupe_dates_ordered(dates: list[date]) -> list[date]:
    seen: set[date] = set()
    out: list[date] = []
    for day in dates:
        if day in seen:
            continue
        seen.add(day)
        out.append(day)
    return out


def release_week_candidates(
    *,
    parsed_release_date: date | None,
    today: date | None = None,
) -> list[date]:
    """Bounded LOCG calendar weeks: parsed Wednesday, prior week, then up to 4 future Wednesdays."""
    today = today or date.today()
    weeks: list[date] = []
    if parsed_release_date is not None:
        anchor = _align_to_wednesday(parsed_release_date)
        weeks.append(anchor)
        weeks.append(anchor - timedelta(days=7))
        for offset in range(1, UPCOMING_WEEKS_AFTER_PARSED + 1):
            weeks.append(anchor + timedelta(days=7 * offset))
    else:
        anchor = _align_to_wednesday(today)
        for offset in range(DEFAULT_UPCOMING_WEEKS_WITHOUT_DATE):
            weeks.append(anchor + timedelta(days=7 * offset))
    return _dedupe_dates_ordered(weeks)


def _stub_matches_import(
    stub: LocgListIssueStub,
    *,
    title: str | None,
    issue_number: str | None,
) -> bool:
    if not title:
        return False
    want_issue = _issue_number_key(issue_number)
    series, stub_issue, _ = split_series_and_issue_title(stub.title, publisher=stub.publisher)
    if want_issue and _issue_number_key(stub_issue) != want_issue:
        return False
    import_norm = normalize_import_title(title)
    stub_norm = normalize_import_title(series or stub.title)
    if import_norm and import_norm == stub_norm:
        return True
    overlap, reason = _token_overlap_score(_title_tokens(title), _title_tokens(series or stub.title))
    return overlap >= 22 and reason in (
        "title_exact",
        "title_overlap_strong",
        "title_overlap_good",
    )


def _lookup_external_issue_id(session: Session, source_url: str) -> int | None:
    from app.services.external_catalog.league_of_comic_geeks import _abs_url

    urls = {source_url}
    if source_url:
        urls.add(_abs_url(source_url))
    for url in urls:
        row = session.exec(
            select(ExternalCatalogIssue).where(
                ExternalCatalogIssue.source_name == LOCG_SOURCE_NAME,
                ExternalCatalogIssue.source_url == url,
            )
        ).first()
        if row is not None and row.id is not None:
            return row.id
    return None


def _process_cache_get(key: str) -> ImportLocgHydrateResult | None:
    entry = _process_hydrate_cache.get(key)
    if entry is None:
        return None
    expires_at, result = entry
    if time.monotonic() > expires_at:
        _process_hydrate_cache.pop(key, None)
        return None
    return result


def _process_cache_set(key: str, result: ImportLocgHydrateResult) -> None:
    _process_hydrate_cache[key] = (time.monotonic() + PROCESS_CACHE_TTL_SECONDS, result)


def hydrate_import_item_from_locg_calendar(
    session: Session,
    *,
    title: str | None,
    issue_number: str | None,
    parsed_release_date: date | None = None,
    today: date | None = None,
) -> ImportLocgHydrateResult:
    if not import_locg_hydrate_enabled():
        return ImportLocgHydrateResult(attempted=False, no_match_reason="hydrate_disabled")
    if not title or not issue_number:
        return ImportLocgHydrateResult(attempted=False, no_match_reason="missing_title_or_issue")

    request_cache = get_import_locg_hydrate_request_cache()
    line_key = request_cache.line_key(
        title=title,
        issue_number=issue_number,
        parsed_release_date=parsed_release_date,
    )
    if request_cache.line_was_attempted(line_key):
        cached = _process_cache_get(line_key)
        if cached is not None:
            return ImportLocgHydrateResult(
                attempted=cached.attempted,
                hydrated=cached.hydrated,
                external_issue_id=cached.external_issue_id,
                searched_dates=list(cached.searched_dates),
                matched_stub_title=cached.matched_stub_title,
                no_match_reason=cached.no_match_reason,
                cached=True,
            )
        return ImportLocgHydrateResult(
            attempted=True,
            hydrated=False,
            no_match_reason="duplicate_line_in_request",
            cached=True,
        )

    request_cache.mark_line_attempted(line_key)
    process_cached = _process_cache_get(line_key)
    if process_cached is not None:
        return ImportLocgHydrateResult(
            attempted=process_cached.attempted,
            hydrated=process_cached.hydrated,
            external_issue_id=process_cached.external_issue_id,
            searched_dates=list(process_cached.searched_dates),
            matched_stub_title=process_cached.matched_stub_title,
            no_match_reason=process_cached.no_match_reason,
            cached=True,
        )

    weeks = release_week_candidates(parsed_release_date=parsed_release_date, today=today)
    searched = [day.isoformat() for day in weeks]
    deadline = time.monotonic() + _hydrate_timeout_seconds()
    client = LocgHttpClient()
    counters = SyncCounters()
    result = ImportLocgHydrateResult(attempted=True, searched_dates=searched)

    try:
        for page_date in weeks:
            if time.monotonic() > deadline:
                result.no_match_reason = "hydrate_timeout"
                logger.warning(
                    "import_locg_hydrate_timeout title=%r issue=%r searched=%s",
                    title,
                    issue_number,
                    searched,
                )
                break
            try:
                request_cache.calendar_fetch_count += 1
                html = fetch_release_date_page(page_date, client=client)
            except Exception as exc:
                logger.warning(
                    "import_locg_hydrate_calendar_fetch_failed date=%s error=%s",
                    page_date.isoformat(),
                    exc,
                )
                continue
            try:
                stubs = parse_release_date_live_page(html, page_date=page_date)
                if not stubs:
                    stubs = parse_release_date_page(html, page_date=page_date)
            except Exception as exc:
                logger.warning(
                    "import_locg_hydrate_calendar_parse_failed date=%s error=%s",
                    page_date.isoformat(),
                    exc,
                )
                continue

            for stub in stubs:
                if not _stub_matches_import(stub, title=title, issue_number=issue_number):
                    continue
                result.matched_stub_title = stub.title
                seed = stub_to_detail_seed(stub)
                try:
                    request_cache.detail_fetch_count += 1
                    _process_detail_url(
                        session,
                        seed=seed,
                        client=client,
                        counters=counters,
                        dry_run=False,
                        refresh_existing=False,
                    )
                except Exception as exc:
                    logger.warning(
                        "import_locg_hydrate_detail_failed title=%r stub=%r error=%s",
                        title,
                        stub.title,
                        exc,
                    )
                    result.error = str(exc)
                    result.no_match_reason = "detail_fetch_failed"
                    _process_cache_set(line_key, result)
                    return result

                source_url = str(seed.get("source_url") or "")
                if source_url and not source_url.startswith("http"):
                    from app.services.external_catalog.league_of_comic_geeks import _abs_url

                    source_url = _abs_url(source_url)
                result.external_issue_id = _lookup_external_issue_id(session, source_url)
                result.hydrated = True
                result.no_match_reason = None
                logger.info(
                    "import_locg_hydrate_success title=%r issue=%r stub=%r external_issue_id=%s searched=%s",
                    title,
                    issue_number,
                    stub.title,
                    result.external_issue_id,
                    searched,
                )
                _process_cache_set(line_key, result)
                return result

        if result.no_match_reason is None:
            result.no_match_reason = "no_matching_stub"
            logger.info(
                "import_locg_hydrate_no_match title=%r issue=%r searched=%s",
                title,
                issue_number,
                searched,
            )
        _process_cache_set(line_key, result)
        return result
    except Exception as exc:
        logger.warning(
            "import_locg_hydrate_unexpected_failure title=%r issue=%r error=%s",
            title,
            issue_number,
            exc,
            exc_info=True,
        )
        result.error = str(exc)
        result.no_match_reason = "unexpected_error"
        _process_cache_set(line_key, result)
        return result
    finally:
        client.close()


def hydrate_result_to_diagnostics(result: ImportLocgHydrateResult) -> dict[str, Any]:
    return {
        "locg_hydrate_attempted": result.attempted,
        "locg_hydrated": result.hydrated,
        "locg_hydrate_cached": result.cached,
        "locg_hydrate_searched_dates": result.searched_dates,
        "locg_hydrate_matched_stub": result.matched_stub_title,
        "locg_hydrate_external_issue_id": result.external_issue_id,
        "locg_hydrate_no_match_reason": result.no_match_reason,
        "locg_hydrate_error": result.error,
    }
