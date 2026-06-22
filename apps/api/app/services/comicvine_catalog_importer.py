from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models.catalog_master import CatalogImage, CatalogIssue, CatalogPublisher, CatalogSeries
from app.services.comicvine_api_limits import (
    COMICVINE_MIN_SECONDS_BETWEEN_REQUESTS,
    ComicVineHourlyBudget,
    comicvine_cache_key,
    comicvine_resource_name,
    read_comicvine_cache,
    write_comicvine_cache,
)
from app.services.comicvine_api_response import (
    ComicVineApiError,
    clamp_page_limit,
    comicvine_best_cover_url,
    comicvine_issue_dates_from_row,
    parse_comicvine_payload,
    payload_results,
)
from app.services.catalog_import_job_service import (
    comicvine_issue_import_scope,
    comicvine_volume_import_scope,
    complete_job,
    fail_job,
    latest_completed_cursor_for_scope,
    record_created,
    record_failed,
    record_skipped,
    record_updated,
    resume_scoped_job,
    start_job,
    update_cursor,
)
from app.services.catalog_import_quality_service import (
    detect_series_language_signals,
    score_import_candidate,
)
from app.services.catalog_publisher_registry import (
    is_international_publisher,
    is_international_license_publisher,
    is_primary_us_publisher,
)
from app.services.catalog_ingestion_service import (
    normalize_issue_number,
    normalize_series_name,
    upsert_image,
    upsert_issue,
    upsert_publisher,
    upsert_series,
    upsert_variant,
)

LOGGER = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://comicvine.gamespot.com/api"
VOLUME_JOB_TYPE = "volumes"
ISSUE_JOB_TYPE = "volume_issues"
COMICVINE_VOLUME_RESOURCE_PREFIX = "4050"
COMICVINE_THROTTLE_STATUS = 420
DEFAULT_HTTP_TIMEOUT_SECONDS = 30.0
MAX_ISSUE_IMPORT_PAGES = 1000


class ComicVineThrottleError(RuntimeError):
    """Raised when ComicVine responds with HTTP 420 (rate limited). Never retried inline."""

    def __init__(self, message: str = "ComicVine HTTP 420 throttle") -> None:
        super().__init__(message)


def publisher_name_matches(requested: str, actual: str, *, strict: bool) -> bool:
    if not strict or not (requested or "").strip():
        return True
    req = normalize_series_name(requested)
    act = normalize_series_name(actual or "")
    if not act:
        return False
    if req == act:
        return True
    if act.startswith(f"{req} "):
        return True
    if act.startswith(req) and len(act) > len(req):
        next_char = act[len(req)]
        return not next_char.isalnum()
    return False


@dataclass(frozen=True)
class ImportDecision:
    allowed: bool
    reason: str
    quality_score: int


def _empty_publisher_quality_summary() -> dict[str, int]:
    return {"PRIMARY": 0, "ACCEPTABLE": 0, "LOW_PRIORITY": 0, "REJECTED": 0}


def should_import_volume(
    *,
    publisher: str,
    series_name: str,
    volume_metadata: dict[str, Any] | None,
    allow_international_editions: bool,
    strict_english: bool,
) -> ImportDecision:
    quality = score_import_candidate(
        publisher=publisher,
        series_name=series_name,
        volume_metadata=volume_metadata,
    )
    series_language = detect_series_language_signals(series_name)
    if strict_english and series_language:
        return ImportDecision(False, "PROBABLE_NON_ENGLISH_EDITION", quality.quality_score)
    if is_primary_us_publisher(publisher):
        return ImportDecision(True, "PRIMARY_US_PUBLISHER", quality.quality_score)
    if allow_international_editions:
        if strict_english and series_language:
            return ImportDecision(False, "PROBABLE_NON_ENGLISH_EDITION", quality.quality_score)
        if is_international_publisher(publisher):
            return ImportDecision(True, "INTERNATIONAL_ALLOWED", quality.quality_score)
        if quality.quality_tier == "REJECT":
            return ImportDecision(False, "QUALITY_REJECT", quality.quality_score)
        return ImportDecision(True, "INTERNATIONAL_ALLOWED", quality.quality_score)
    if is_international_license_publisher(publisher):
        return ImportDecision(False, "INTERNATIONAL_LICENSE_EDITION", quality.quality_score)
    if is_international_publisher(publisher):
        return ImportDecision(False, "INTERNATIONAL_PUBLISHER_MATCH", quality.quality_score)
    if quality.quality_tier == "REJECT":
        return ImportDecision(False, "QUALITY_REJECT", quality.quality_score)
    return ImportDecision(True, quality.quality_tier, quality.quality_score)


def comicvine_volume_id_for_series(series: CatalogSeries) -> str | None:
    ext = (series.external_source_ids or {}).get("COMICVINE", {})
    if not isinstance(ext, dict) or not ext:
        return None
    key = next(iter(ext.keys()), None)
    return str(key) if key is not None else None


def dedupe_catalog_series_ids_for_issue_import(
    session: Session,
    series_ids: list[int],
) -> tuple[list[int], int]:
    """At most one catalog series per ComicVine volume id (preserves first occurrence order)."""
    unique: list[int] = []
    seen_volume_ids: set[str] = set()
    duplicates_removed = 0
    for catalog_series_id in series_ids:
        series = session.get(CatalogSeries, catalog_series_id)
        if series is None:
            unique.append(catalog_series_id)
            continue
        volume_id = comicvine_volume_id_for_series(series)
        if not volume_id:
            unique.append(catalog_series_id)
            continue
        if volume_id in seen_volume_ids:
            duplicates_removed += 1
            continue
        seen_volume_ids.add(volume_id)
        unique.append(catalog_series_id)
    return unique, duplicates_removed


def comicvine_accepted_volume_metrics(volume_ids: list[str]) -> tuple[int, int, int]:
    raw = len(volume_ids)
    unique = len(set(volume_ids))
    return raw, unique, raw - unique


def publisher_distribution_for_series(session: Session, series_ids: list[int]) -> dict[str, int]:
    dist: dict[str, int] = {}
    for sid in series_ids:
        series = session.get(CatalogSeries, sid)
        if series is None:
            continue
        pub = session.get(CatalogPublisher, series.publisher_id) if series.publisher_id else None
        name = (pub.name if pub else "Unknown") or "Unknown"
        dist[name] = dist.get(name, 0) + 1
    return dict(sorted(dist.items(), key=lambda item: (-item[1], item[0])))


@dataclass
class ComicVineImportStats:
    processed: int = 0
    created_issues: int = 0
    updated_issues: int = 0
    skipped_non_matching_publisher: int = 0
    imported_series: int = 0
    imported_series_ids: list[int] = field(default_factory=list)
    publisher_distribution: dict[str, int] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    volume_job_id: int | None = None
    issue_job_id: int | None = None
    issue_import_ran: bool = False
    issue_import_volumes_attempted: int = 0
    cover_images_created: int = 0
    cover_images_skipped: int = 0
    cover_images_skipped_no_url: int = 0
    publisher_quality_summary: dict[str, int] = field(default_factory=_empty_publisher_quality_summary)
    skipped_quality_gate: int = 0
    api_pages_fetched: int = 0
    total_candidates_seen: int = 0
    accepted_volumes: int = 0
    final_offset: int = 0
    accepted_comicvine_volume_ids: list[str] = field(default_factory=list)
    accepted_volumes_raw: int = 0
    accepted_volumes_unique: int = 0
    duplicate_volumes_removed: int = 0
    issue_imports_started: int = 0
    issue_imports_completed: int = 0
    volume_id: int | None = None
    series_created: int = 0
    series_updated: int = 0
    api_requests_used: int = 0
    throttled: bool = False


class ComicVineCatalogImporter:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        rate_limit_seconds: float | None = None,
        max_retries: int | None = None,
        user_agent: str | None = None,
        dry_run: bool = False,
        allow_international_editions: bool = False,
        strict_english: bool = True,
        http_timeout: float | None = None,
    ) -> None:
        settings = get_settings()
        if api_key is not None:
            self.api_key = api_key
        else:
            self.api_key = settings.comicvine_api_key or os.getenv("COMICVINE_API_KEY", "")
        self.base_url = (base_url or settings.comicvine_api_base_url or os.getenv("COMICVINE_API_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.rate_limit_seconds = max(
            float(rate_limit_seconds if rate_limit_seconds is not None else settings.catalog_import_sleep_seconds),
            COMICVINE_MIN_SECONDS_BETWEEN_REQUESTS,
        )
        self.max_retries = max_retries if max_retries is not None else settings.catalog_import_max_retries
        self.user_agent = user_agent or settings.catalog_import_user_agent
        self.dry_run = dry_run
        self.allow_international_editions = allow_international_editions
        self.strict_english = strict_english
        self._last_request_monotonic: float | None = None
        self.api_requests_made = 0
        self._hourly_budget = ComicVineHourlyBudget(max_per_hour=settings.comicvine_max_requests_per_resource_hour)
        self._http_cache_enabled = settings.comicvine_http_cache_enabled
        cache_root = Path(settings.catalog_storage_root) / "comicvine_http_cache"
        self._http_cache_dir = cache_root
        self.http_timeout = float(
            http_timeout if http_timeout is not None else DEFAULT_HTTP_TIMEOUT_SECONDS
        )
        self.request_trace: Callable[[str, str, dict[str, Any]], None] | None = None

    def _trace_request(self, phase: str, path: str, **meta: Any) -> None:
        if self.request_trace is not None:
            self.request_trace(phase, path, meta)

    def _wait_before_request(self) -> None:
        gap = self.rate_limit_seconds
        if self._last_request_monotonic is not None:
            elapsed = time.monotonic() - self._last_request_monotonic
            remaining = gap - elapsed
            if remaining > 0:
                time.sleep(remaining)
        self._last_request_monotonic = time.monotonic()

    def initialize_or_explain(self) -> str | None:
        if not self.api_key:
            return "COMICVINE_API_KEY is not configured; ComicVine bulk import is unavailable."
        return None

    def _get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("COMICVINE_API_KEY is required")
        cache_key = comicvine_cache_key(path, params)
        if self._http_cache_enabled:
            cached = read_comicvine_cache(self._http_cache_dir, cache_key)
            if cached is not None:
                LOGGER.debug("ComicVine cache hit for %s", path)
                return cached

        resource = comicvine_resource_name(path)
        hourly_log: Callable[[str], None] | None = None
        if self.request_trace is not None:

            def hourly_log(message: str) -> None:
                self._trace_request("hourly_budget", path, message=message, resource=resource)

        self._hourly_budget.wait_if_needed(resource, log_fn=hourly_log)

        query = {"api_key": self.api_key, "format": "json"}
        if params:
            safe_params = dict(params)
            if "limit" in safe_params:
                safe_params["limit"] = clamp_page_limit(int(safe_params["limit"]), path=path)
            query.update(safe_params)
        headers = {"User-Agent": self.user_agent}
        backoff = self.rate_limit_seconds
        last_exc: Exception | None = None
        for attempt in range(max(1, self.max_retries)):
            self._wait_before_request()
            self._trace_request("http_start", path, attempt=attempt + 1, params=query)
            try:
                response = httpx.get(
                    f"{self.base_url}/{path.lstrip('/')}",
                    params=query,
                    headers=headers,
                    timeout=self.http_timeout,
                )
                self._trace_request(
                    "http_end",
                    path,
                    attempt=attempt + 1,
                    status_code=response.status_code,
                )
                self._hourly_budget.record(resource)
                self.api_requests_made += 1
                if response.status_code == COMICVINE_THROTTLE_STATUS:
                    LOGGER.warning("ComicVine HTTP 420 throttle on %s; aborting without retry", path)
                    raise ComicVineThrottleError(f"ComicVine HTTP 420 on {path}")
                if response.status_code == 429:
                    backoff = min(max(backoff * 2, COMICVINE_MIN_SECONDS_BETWEEN_REQUESTS * 5), 60.0)
                    self.rate_limit_seconds = max(self.rate_limit_seconds, backoff)
                    LOGGER.warning("ComicVine 429/throttle; backing off to %.1fs between requests", self.rate_limit_seconds)
                    continue
                if response.status_code in (500, 502, 503, 504):
                    backoff = min(backoff * 2, 30.0)
                    time.sleep(backoff)
                    continue
                response.raise_for_status()
                payload = parse_comicvine_payload(response.json())
                if self._http_cache_enabled:
                    write_comicvine_cache(self._http_cache_dir, cache_key, payload)
                return payload
            except ComicVineThrottleError:
                self._trace_request("http_end", path, attempt=attempt + 1, error="throttle")
                raise
            except ComicVineApiError:
                self._trace_request("http_end", path, attempt=attempt + 1, error="api_error")
                raise
            except httpx.HTTPStatusError:
                self._trace_request("http_end", path, attempt=attempt + 1, error="http_status")
                raise
            except Exception as exc:
                self._trace_request("http_end", path, attempt=attempt + 1, error=str(exc))
                last_exc = exc
                backoff = min(backoff * 2, 30.0)
                time.sleep(backoff)
        raise RuntimeError(str(last_exc or "comicvine_request_failed"))

    def _volume_api_path(self, *, series_name: str | None) -> str:
        return "search/" if series_name else "volumes/"

    def search_volumes(self, query: str, *, limit: int = 30) -> list[dict[str, Any]]:
        """Search ComicVine volumes by name; returns lightweight rows (id/name/year/publisher/count)."""
        if not (query or "").strip():
            return []
        payload = self._get(
            "search/",
            params={
                "query": query.strip(),
                "resources": "volume",
                "limit": limit,
                "field_list": "id,name,start_year,publisher,count_of_issues,resource_type",
            },
        )
        rows = payload_results(payload)
        return [row for row in rows if row.get("resource_type") in (None, "volume")]

    def _fetch_volume_page(
        self,
        *,
        offset: int,
        page_limit: int,
        publisher_filter: str | None,
        series_name: str | None,
    ) -> dict[str, Any]:
        api_path = self._volume_api_path(series_name=series_name)
        fetch_limit = clamp_page_limit(page_limit, path=api_path)
        if series_name:
            return self._get(
                "search/",
                params={
                    "query": series_name,
                    "resources": "volume",
                    "offset": offset,
                    "limit": fetch_limit,
                    "field_list": "id,name,start_year,publisher,resource_type",
                },
            )
        params: dict[str, Any] = {
            "offset": offset,
            "limit": fetch_limit,
            "field_list": "id,name,start_year,publisher",
        }
        if publisher_filter:
            params["filter"] = f"publisher:{publisher_filter}"
        return self._get("volumes/", params=params)

    def _volume_rows_from_payload(self, payload: dict[str, Any], *, series_name: str | None) -> list[dict[str, Any]]:
        rows = payload_results(payload)
        if not series_name:
            return rows
        return [row for row in rows if row.get("resource_type") in (None, "volume")]

    def _process_volume_row(
        self,
        session: Session,
        stats: ComicVineImportStats,
        row: dict[str, Any],
        *,
        publisher_filter: str | None,
        strict_publisher: bool,
        job,
        min_start_year: int | None = None,
    ) -> None:
        if min_start_year is not None:
            start_year_raw = row.get("start_year")
            try:
                start_year_int = int(start_year_raw) if start_year_raw is not None else None
            except (TypeError, ValueError):
                start_year_int = None
            if start_year_int is None or start_year_int < min_start_year:
                stats.skipped_quality_gate += 1
                if job is not None:
                    record_skipped(session, job)
                return
        publisher_name = (row.get("publisher") or {}).get("name") if isinstance(row.get("publisher"), dict) else "Unknown"
        publisher_name = publisher_name or "Unknown"
        series_title = str(row.get("name") or "")
        if not publisher_name_matches(publisher_filter or "", publisher_name, strict=strict_publisher):
            stats.skipped_non_matching_publisher += 1
            if job is not None:
                record_skipped(session, job)
            LOGGER.info(
                "comicvine skip volume_id=%s series=%r publisher=%r reason=STRICT_PUBLISHER_MISMATCH",
                row.get("id"),
                row.get("name"),
                publisher_name,
            )
            return
        decision = should_import_volume(
            publisher=publisher_name,
            series_name=series_title,
            volume_metadata=row,
            allow_international_editions=self.allow_international_editions,
            strict_english=self.strict_english,
        )
        if not decision.allowed:
            stats.skipped_quality_gate += 1
            stats.publisher_quality_summary["REJECTED"] += 1
            if job is not None:
                record_skipped(session, job)
            LOGGER.info(
                "comicvine skip volume_id=%s publisher=%r reason=%s",
                row.get("id"),
                publisher_name,
                decision.reason,
            )
            return
        tier = score_import_candidate(
            publisher=publisher_name,
            series_name=series_title,
            volume_metadata=row,
        ).quality_tier
        stats.publisher_quality_summary[tier] = stats.publisher_quality_summary.get(tier, 0) + 1
        stats.accepted_volumes += 1
        comicvine_id = row.get("id")
        if comicvine_id is not None:
            stats.accepted_comicvine_volume_ids.append(str(comicvine_id))
        if self.dry_run:
            if job is not None:
                record_updated(session, job)
            return
        publisher = upsert_publisher(session, name=publisher_name, source="COMICVINE", external_id=row.get("id"))
        series = upsert_series(
            session,
            name=str(row.get("name") or "Unknown"),
            publisher_id=int(publisher.id or 0),
            source="COMICVINE",
            external_id=row.get("id"),
            start_year=row.get("start_year"),
        )
        if series.id:
            stats.imported_series_ids.append(int(series.id))
        if job is not None:
            record_created(session, job)

    def import_volumes(
        self,
        session: Session,
        *,
        offset: int = 0,
        limit: int = 20,
        publisher_filter: str | None = None,
        series_name: str | None = None,
        strict_publisher: bool = False,
        job=None,
        cursor_scope: dict[str, Any] | None = None,
        min_start_year: int | None = None,
    ) -> ComicVineImportStats:
        stats = ComicVineImportStats()
        stats.publisher_quality_summary = _empty_publisher_quality_summary()
        start_offset = int(offset)
        current_offset = start_offset
        stats.final_offset = start_offset
        cursor_extra = dict(cursor_scope or {})
        requested_limit = max(0, int(limit))
        api_path = self._volume_api_path(series_name=series_name)
        page_cap = 100 if api_path == "volumes/" else clamp_page_limit(100, path=api_path)

        while stats.total_candidates_seen < requested_limit:
            remaining = requested_limit - stats.total_candidates_seen
            page_limit = min(page_cap, remaining)
            try:
                payload = self._fetch_volume_page(
                    offset=current_offset,
                    page_limit=page_limit,
                    publisher_filter=publisher_filter,
                    series_name=series_name,
                )
            except Exception as exc:
                stats.failures.append(str(exc))
                if job is not None:
                    record_failed(
                        session,
                        job,
                        source="COMICVINE",
                        external_id=None,
                        record_type="volume",
                        error_type="http",
                        error_message=str(exc),
                    )
                break
            page_rows = self._volume_rows_from_payload(payload, series_name=series_name)
            if not page_rows:
                break
            stats.api_pages_fetched += 1
            fetch_limit = clamp_page_limit(page_limit, path=api_path)
            for row in page_rows:
                try:
                    stats.total_candidates_seen += 1
                    self._process_volume_row(
                        session,
                        stats,
                        row,
                        publisher_filter=publisher_filter,
                        strict_publisher=strict_publisher,
                        job=job,
                        min_start_year=min_start_year,
                    )
                except Exception as exc:
                    msg = f"volume:{row.get('id')}: {exc}"
                    stats.failures.append(msg)
                    if job is not None:
                        record_failed(
                            session,
                            job,
                            source="COMICVINE",
                            external_id=str(row.get("id")),
                            record_type="volume",
                            error_type="import",
                            error_message=msg,
                            raw_payload=row,
                        )
            current_offset += len(page_rows)
            stats.final_offset = current_offset
            if job is not None:
                update_cursor(session, job, {"offset": current_offset, **cursor_extra})
            if not self.dry_run:
                session.commit()
            if len(page_rows) < fetch_limit:
                break

        stats.processed = stats.total_candidates_seen
        stats.imported_series = len(stats.imported_series_ids)
        stats.publisher_distribution = publisher_distribution_for_series(session, stats.imported_series_ids)
        return stats

    def import_issues_for_volume(
        self,
        session: Session,
        *,
        volume_id: str,
        catalog_series_id: int,
        offset: int = 0,
        limit: int = 50,
        job=None,
    ) -> ComicVineImportStats:
        stats = ComicVineImportStats()
        page_limit = clamp_page_limit(limit, path="issues/")
        params = {
            "offset": offset,
            "limit": page_limit,
            "filter": f"volume:{volume_id}",
            "field_list": "id,issue_number,name,cover_date,store_date,date_added,description,image",
        }
        try:
            payload = self._get("issues/", params=params)
        except ComicVineThrottleError:
            raise
        except Exception as exc:
            stats.failures.append(str(exc))
            if job is not None:
                record_failed(
                    session,
                    job,
                    source="COMICVINE",
                    external_id=volume_id,
                    record_type="issue",
                    error_type="http",
                    error_message=str(exc),
                )
            return stats
        series = session.get(CatalogSeries, catalog_series_id)
        if series is None:
            stats.failures.append(f"missing_series:{catalog_series_id}")
            return stats
        rows = payload_results(payload)
        stats.processed = len(rows)
        for row in rows:
            try:
                if self.dry_run:
                    continue
                issue_number = str(row.get("issue_number") or "?")
                normalized = normalize_issue_number(issue_number)
                existing_issue = session.exec(
                    select(CatalogIssue)
                    .where(CatalogIssue.series_id == int(series.id or 0))
                    .where(CatalogIssue.normalized_issue_number == normalized)
                ).first()
                cover_date, store_date, release_date = comicvine_issue_dates_from_row(row)
                issue = upsert_issue(
                    session,
                    series_id=int(series.id or 0),
                    publisher_id=series.publisher_id,
                    issue_number=issue_number,
                    source="COMICVINE",
                    external_id=row.get("id"),
                    title=row.get("name"),
                    description=row.get("description"),
                    cover_date=cover_date,
                    store_date=store_date,
                    release_date=release_date,
                    source_confidence=Decimal("0.70"),
                )
                if existing_issue is None:
                    stats.created_issues += 1
                    if job is not None:
                        record_created(session, job)
                else:
                    stats.updated_issues += 1
                    if job is not None:
                        record_updated(session, job)
                variant = upsert_variant(session, issue_id=int(issue.id or 0), source="COMICVINE", variant_name="Standard")
                cover_url = comicvine_best_cover_url(row.get("image"))
                if not cover_url:
                    stats.cover_images_skipped_no_url += 1
                    continue
                existing_image = session.exec(
                    select(CatalogImage)
                    .where(CatalogImage.issue_id == int(issue.id or 0))
                    .where(CatalogImage.source_url == cover_url)
                ).first()
                if existing_image is not None:
                    stats.cover_images_skipped += 1
                    continue
                upsert_image(
                    session,
                    issue_id=int(issue.id or 0),
                    variant_id=int(variant.id or 0),
                    source_url=cover_url,
                    source="COMICVINE",
                    external_image_id=str(row.get("id")),
                )
                stats.cover_images_created += 1
                if job is not None:
                    record_created(session, job)
            except Exception as exc:
                msg = f"issue:{row.get('id')}: {exc}"
                stats.failures.append(msg)
                if job is not None:
                    record_failed(
                        session,
                        job,
                        source="COMICVINE",
                        external_id=str(row.get("id")),
                        record_type="issue",
                        error_type="import",
                        error_message=msg,
                        raw_payload=row,
                    )
        if not self.dry_run:
            session.commit()
        return stats

    def _run_issue_import_phase(
        self,
        session: Session,
        *,
        series_ids: list[int],
        publisher_filter: str | None,
        series_name: str | None,
        strict_publisher: bool,
        parent_volume_job_id: int,
        issues_per_volume_limit: int = 100,
    ) -> ComicVineImportStats:
        issue_scope = comicvine_issue_import_scope(
            publisher_filter=publisher_filter,
            series_name=series_name,
            strict_publisher=strict_publisher,
            allow_international_editions=self.allow_international_editions,
        )
        issue_config = {**issue_scope, "parent_volume_job_id": parent_volume_job_id}
        issue_job = start_job(
            session,
            source="COMICVINE",
            job_type=ISSUE_JOB_TYPE,
            dry_run=self.dry_run,
            config=issue_config,
            cursor={"series_ids": series_ids, **issue_scope},
        )
        session.commit()
        aggregate = ComicVineImportStats(issue_import_ran=True, issue_job_id=int(issue_job.id or 0))
        processed_volume_ids: set[str] = set()
        for catalog_series_id in series_ids:
            series = session.get(CatalogSeries, catalog_series_id)
            if series is None:
                continue
            volume_id = comicvine_volume_id_for_series(series)
            if not volume_id:
                msg = f"missing_comicvine_volume_id:series={catalog_series_id}"
                aggregate.failures.append(msg)
                record_failed(
                    session,
                    issue_job,
                    source="COMICVINE",
                    external_id=str(catalog_series_id),
                    record_type="issue",
                    error_type="missing_volume_id",
                    error_message=msg,
                )
                continue
            if volume_id in processed_volume_ids:
                LOGGER.error(
                    "comicvine duplicate volume_id=%s catalog_series_id=%s in volume_issues job_id=%s; skipping",
                    volume_id,
                    catalog_series_id,
                    issue_job.id,
                )
                continue
            processed_volume_ids.add(volume_id)
            aggregate.issue_imports_started += 1
            aggregate.issue_import_volumes_attempted += 1
            LOGGER.info(
                "comicvine issue import volume_id=%s catalog_series_id=%s job_id=%s",
                volume_id,
                catalog_series_id,
                issue_job.id,
            )
            chunk = self.import_issues_for_volume(
                session,
                volume_id=volume_id,
                catalog_series_id=int(series.id or 0),
                limit=issues_per_volume_limit,
                job=issue_job,
            )
            aggregate.issue_imports_completed += 1
            aggregate.processed += chunk.processed
            aggregate.created_issues += chunk.created_issues
            aggregate.updated_issues += chunk.updated_issues
            aggregate.cover_images_created += chunk.cover_images_created
            aggregate.cover_images_skipped += chunk.cover_images_skipped
            aggregate.cover_images_skipped_no_url += chunk.cover_images_skipped_no_url
            aggregate.failures.extend(chunk.failures)
        if aggregate.failures and aggregate.issue_import_volumes_attempted == 0:
            fail_job(session, issue_job, aggregate.failures[0])
        else:
            complete_job(session, issue_job)
        session.commit()
        return aggregate

    def _fetch_volume_detail(self, volume_id: int) -> dict[str, Any] | None:
        path = f"volume/{COMICVINE_VOLUME_RESOURCE_PREFIX}-{int(volume_id)}/"
        payload = self._get(
            path,
            params={"field_list": "id,name,start_year,publisher,count_of_issues"},
        )
        results = payload.get("results")
        if isinstance(results, dict):
            return results
        if isinstance(results, list):
            for row in results:
                if isinstance(row, dict):
                    return row
        return None

    def import_single_volume(
        self,
        session: Session,
        *,
        comicvine_volume_id: int,
        import_issues: bool = False,
        issues_per_volume_limit: int = 100,
    ) -> ComicVineImportStats:
        """Exact-volume acquisition: look up one ComicVine volume by id and (optionally) import its issues.

        This path never performs publisher offset search, series search, or adjacent-volume scanning.
        """
        missing = self.initialize_or_explain()
        if missing:
            raise RuntimeError(missing)

        volume_id = int(comicvine_volume_id)
        stats = ComicVineImportStats(volume_id=volume_id)
        stats.publisher_quality_summary = _empty_publisher_quality_summary()
        requests_before = self.api_requests_made

        try:
            detail = self._fetch_volume_detail(volume_id)
        except ComicVineThrottleError as exc:
            stats.throttled = True
            stats.failures.append(str(exc))
            stats.api_requests_used = self.api_requests_made - requests_before
            return stats
        except Exception as exc:  # noqa: BLE001
            stats.failures.append(f"volume_lookup:{volume_id}: {exc}")
            stats.api_requests_used = self.api_requests_made - requests_before
            return stats

        if not detail:
            stats.failures.append(f"volume_not_found:{volume_id}")
            stats.api_requests_used = self.api_requests_made - requests_before
            return stats

        publisher_obj = detail.get("publisher")
        publisher_name = (
            publisher_obj.get("name") if isinstance(publisher_obj, dict) else None
        ) or "Unknown"
        series_title = str(detail.get("name") or "Unknown")
        stats.processed = 1
        stats.total_candidates_seen = 1
        stats.accepted_volumes = 1
        stats.accepted_comicvine_volume_ids.append(str(volume_id))
        count_of_issues = detail.get("count_of_issues")
        if count_of_issues is not None:
            try:
                stats.estimated_issue_count = int(count_of_issues)  # type: ignore[attr-defined]
            except (TypeError, ValueError):
                pass

        if self.dry_run:
            stats.imported_series = 0
            stats.api_requests_used = self.api_requests_made - requests_before
            stats.issue_import_ran = bool(import_issues)
            return stats

        publisher = upsert_publisher(session, name=publisher_name, source="COMICVINE", external_id=None)
        existing_series = session.exec(
            select(CatalogSeries).where(CatalogSeries.normalized_name == normalize_series_name(series_title))
        ).first()
        series = upsert_series(
            session,
            name=series_title,
            publisher_id=int(publisher.id or 0),
            source="COMICVINE",
            external_id=volume_id,
            start_year=detail.get("start_year"),
        )
        if existing_series is None:
            stats.series_created = 1
        else:
            stats.series_updated = 1
        session.commit()
        if series.id:
            stats.imported_series_ids.append(int(series.id))
        stats.imported_series = len(stats.imported_series_ids)

        if import_issues and series.id:
            issue_job = start_job(
                session,
                source="COMICVINE",
                job_type=ISSUE_JOB_TYPE,
                dry_run=self.dry_run,
                config={"volume_id": volume_id, "mode": "exact_volume"},
                cursor={"volume_id": volume_id, "catalog_series_id": int(series.id)},
            )
            session.commit()
            stats.issue_job_id = int(issue_job.id or 0)
            stats.issue_import_ran = True
            stats.issue_imports_started += 1
            stats.issue_import_volumes_attempted += 1
            offset = 0
            issue_page = 0
            try:
                while True:
                    issue_page += 1
                    if issue_page > MAX_ISSUE_IMPORT_PAGES:
                        stats.failures.append(
                            f"issue_import_page_cap:{MAX_ISSUE_IMPORT_PAGES}:volume:{volume_id}"
                        )
                        break
                    self._trace_request(
                        "issue_page_start",
                        f"issues/volume:{volume_id}",
                        offset=offset,
                        page=issue_page,
                        limit=issues_per_volume_limit,
                    )
                    chunk = self.import_issues_for_volume(
                        session,
                        volume_id=str(volume_id),
                        catalog_series_id=int(series.id),
                        offset=offset,
                        limit=issues_per_volume_limit,
                        job=issue_job,
                    )
                    self._trace_request(
                        "issue_page_end",
                        f"issues/volume:{volume_id}",
                        offset=offset,
                        page=issue_page,
                        processed=chunk.processed,
                    )
                    stats.processed += chunk.processed
                    stats.created_issues += chunk.created_issues
                    stats.updated_issues += chunk.updated_issues
                    stats.cover_images_created += chunk.cover_images_created
                    stats.cover_images_skipped += chunk.cover_images_skipped
                    stats.cover_images_skipped_no_url += chunk.cover_images_skipped_no_url
                    stats.failures.extend(chunk.failures)
                    if chunk.processed < issues_per_volume_limit:
                        break
                    offset += chunk.processed
                stats.issue_imports_completed += 1
                complete_job(session, issue_job)
            except ComicVineThrottleError as exc:
                stats.throttled = True
                stats.failures.append(str(exc))
                fail_job(session, issue_job, str(exc))
            session.commit()

        stats.api_requests_used = self.api_requests_made - requests_before
        stats.publisher_distribution = publisher_distribution_for_series(session, stats.imported_series_ids)
        return stats

    def run_bulk_import(
        self,
        session: Session,
        *,
        limit: int = 20,
        offset: int = 0,
        resume: bool = False,
        publisher_filter: str | None = None,
        series_name: str | None = None,
        strict_publisher: bool = False,
        import_issues: bool = False,
        min_start_year: int | None = None,
    ) -> ComicVineImportStats:
        missing = self.initialize_or_explain()
        if missing:
            raise RuntimeError(missing)

        scope = comicvine_volume_import_scope(
            publisher_filter=publisher_filter,
            series_name=series_name,
            strict_publisher=strict_publisher,
            import_issues=import_issues,
            allow_international_editions=self.allow_international_editions,
        )
        if min_start_year is not None:
            # Keep modern runs on their own resume cursor, separate from full pulls.
            scope = {**scope, "min_start_year": int(min_start_year)}
        volume_job = resume_scoped_job(session, source="COMICVINE", job_type=VOLUME_JOB_TYPE, scope=scope) if resume else None
        cursor_offset = offset
        if volume_job is None:
            if resume:
                prior = latest_completed_cursor_for_scope(
                    session, source="COMICVINE", job_type=VOLUME_JOB_TYPE, scope=scope
                )
                if prior is not None:
                    cursor_offset = int(prior.get("offset", offset))
            volume_job = start_job(
                session,
                source="COMICVINE",
                job_type=VOLUME_JOB_TYPE,
                dry_run=self.dry_run,
                config={**scope, "dry_run": self.dry_run},
                cursor={"offset": cursor_offset, **scope},
            )
            session.commit()
        else:
            cursor_offset = int((volume_job.cursor or {}).get("offset", offset))
            LOGGER.info("Resuming scoped ComicVine volume job_id=%s scope=%s cursor_offset=%s", volume_job.id, scope, cursor_offset)

        stats = self.import_volumes(
            session,
            offset=cursor_offset,
            limit=limit,
            publisher_filter=publisher_filter,
            series_name=series_name,
            strict_publisher=strict_publisher,
            job=volume_job,
            cursor_scope=scope,
            min_start_year=min_start_year,
        )
        stats.volume_job_id = int(volume_job.id or 0)
        stats.imported_series = len(stats.imported_series_ids)
        update_cursor(session, volume_job, {"offset": stats.final_offset, **scope})
        if stats.failures and stats.processed == 0:
            fail_job(session, volume_job, stats.failures[0])
        else:
            complete_job(session, volume_job)
        session.commit()

        if import_issues:
            if self.dry_run:
                stats.issue_import_ran = True
                LOGGER.info("dry_run: skipping ComicVine issue import phase (volume metadata only)")
            elif stats.imported_series_ids:
                series_ids_raw = list(stats.imported_series_ids)
                vol_raw, vol_unique, vol_dupes = comicvine_accepted_volume_metrics(stats.accepted_comicvine_volume_ids)
                if vol_raw:
                    stats.accepted_volumes_raw = vol_raw
                    stats.accepted_volumes_unique = vol_unique
                    stats.duplicate_volumes_removed = vol_dupes
                else:
                    stats.accepted_volumes_raw = len(series_ids_raw)
                    stats.accepted_volumes_unique = len(series_ids_raw)
                    stats.duplicate_volumes_removed = 0
                deduped_series_ids, series_dupes = dedupe_catalog_series_ids_for_issue_import(session, series_ids_raw)
                if not vol_raw and series_dupes:
                    stats.duplicate_volumes_removed = series_dupes
                    stats.accepted_volumes_unique = len(deduped_series_ids)
                LOGGER.info(
                    "comicvine issue import plan accepted_volumes_raw=%s accepted_volumes_unique=%s "
                    "duplicate_volumes_removed=%s series_ids_raw=%s series_ids_for_import=%s",
                    stats.accepted_volumes_raw,
                    stats.accepted_volumes_unique,
                    stats.duplicate_volumes_removed,
                    len(series_ids_raw),
                    len(deduped_series_ids),
                )
                issue_stats = self._run_issue_import_phase(
                    session,
                    series_ids=deduped_series_ids,
                    publisher_filter=publisher_filter,
                    series_name=series_name,
                    strict_publisher=strict_publisher,
                    parent_volume_job_id=int(volume_job.id or 0),
                )
                stats.issue_import_ran = issue_stats.issue_import_ran
                stats.issue_job_id = issue_stats.issue_job_id
                stats.issue_import_volumes_attempted = issue_stats.issue_import_volumes_attempted
                stats.issue_imports_started = issue_stats.issue_imports_started
                stats.issue_imports_completed = issue_stats.issue_imports_completed
                stats.created_issues = issue_stats.created_issues
                stats.updated_issues = issue_stats.updated_issues
                stats.cover_images_created = issue_stats.cover_images_created
                stats.cover_images_skipped = issue_stats.cover_images_skipped
                stats.cover_images_skipped_no_url = issue_stats.cover_images_skipped_no_url
                stats.failures.extend(issue_stats.failures)
            else:
                stats.issue_import_ran = False
                LOGGER.warning("import_issues requested but no series imported in volume phase")

        stats.publisher_distribution = publisher_distribution_for_series(session, stats.imported_series_ids)
        return stats
