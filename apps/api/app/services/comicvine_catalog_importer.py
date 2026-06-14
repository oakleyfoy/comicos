from __future__ import annotations

import logging
import os
import time
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
        self._hourly_budget = ComicVineHourlyBudget(max_per_hour=settings.comicvine_max_requests_per_resource_hour)
        self._http_cache_enabled = settings.comicvine_http_cache_enabled
        cache_root = Path(settings.catalog_storage_root) / "comicvine_http_cache"
        self._http_cache_dir = cache_root

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
        self._hourly_budget.wait_if_needed(resource)

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
            try:
                response = httpx.get(
                    f"{self.base_url}/{path.lstrip('/')}",
                    params=query,
                    headers=headers,
                    timeout=30.0,
                )
                self._hourly_budget.record(resource)
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
            except ComicVineApiError:
                raise
            except httpx.HTTPStatusError:
                raise
            except Exception as exc:
                last_exc = exc
                backoff = min(backoff * 2, 30.0)
                time.sleep(backoff)
        raise RuntimeError(str(last_exc or "comicvine_request_failed"))

    def _volume_api_path(self, *, series_name: str | None) -> str:
        return "search/" if series_name else "volumes/"

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
    ) -> None:
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
            "field_list": "id,issue_number,name,cover_date,store_date,description,image",
        }
        try:
            payload = self._get("issues/", params=params)
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
                issue = upsert_issue(
                    session,
                    series_id=int(series.id or 0),
                    publisher_id=series.publisher_id,
                    issue_number=issue_number,
                    source="COMICVINE",
                    external_id=row.get("id"),
                    title=row.get("name"),
                    description=row.get("description"),
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
                issue_stats = self._run_issue_import_phase(
                    session,
                    series_ids=list(stats.imported_series_ids),
                    publisher_filter=publisher_filter,
                    series_name=series_name,
                    strict_publisher=strict_publisher,
                    parent_volume_job_id=int(volume_job.id or 0),
                )
                stats.issue_import_ran = issue_stats.issue_import_ran
                stats.issue_job_id = issue_stats.issue_job_id
                stats.issue_import_volumes_attempted = issue_stats.issue_import_volumes_attempted
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
