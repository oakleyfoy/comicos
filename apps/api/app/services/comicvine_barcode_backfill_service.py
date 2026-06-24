"""Backfill ``catalog_upc`` from ComicVine so barcode scans match locally.

Every local catalog issue is ComicVine-linked, but ``catalog_upc`` is empty, so today
every scan falls through to a live ComicVine lookup. This service fetches ComicVine issue
barcodes (one request per volume covers all of a series' issues), validates each barcode
against the local record with :mod:`app.services.barcode_validation_service`, and reports
exactly what it *would* insert. It only writes when ``write=True`` and never overwrites a
conflicting barcode mapping.

Dry-run first: prove coverage and conflict rate before writing to production.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.models.catalog_master import (
    CatalogIssue,
    CatalogPublisher,
    CatalogSeries,
    CatalogUpc,
    CatalogVariant,
)
from app.services.barcode_validation_service import validate_barcode_catalog_match
from app.services.catalog_ingestion_service import (
    normalize_issue_number,
    normalize_upc,
    upsert_upc,
)
from app.services.comicvine_api_response import (
    clamp_page_limit,
    comicvine_barcodes_from_issue_row,
    payload_results,
)
from app.services.comicvine_catalog_importer import (
    ComicVineThrottleError,
    comicvine_volume_id_for_series,
)

logger = logging.getLogger(__name__)

FULL_BARCODE_MIN_LEN = 17  # 12-digit UPC + 5-digit supplement
ISSUE_FIELD_LIST = "id,issue_number,name,cover_date,store_date,date_added,barcode"
MAX_SAMPLES = 40
SAVE_EVERY = 25  # flush resume progress every N volumes


def _year_from_dates(*values: str | None) -> int | None:
    for value in values:
        text = str(value or "").strip()
        if len(text) >= 4 and text[:4].isdigit():
            year = int(text[:4])
            if 1900 <= year <= 2100:
                return year
    return None


@dataclass
class _Bucket:
    issues_checked: int = 0
    with_barcode: int = 0
    usable_full: int = 0
    base_only: int = 0
    rejected: int = 0
    conflicts: int = 0
    projected_inserts: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "issues_checked": self.issues_checked,
            "with_barcode": self.with_barcode,
            "usable_full": self.usable_full,
            "base_only": self.base_only,
            "rejected": self.rejected,
            "conflicts": self.conflicts,
            "projected_inserts": self.projected_inserts,
        }


@dataclass
class BackfillStats:
    volumes_checked: int = 0
    issues_checked: int = 0
    cv_issues_with_barcode: int = 0
    usable_full: int = 0
    base_only: int = 0
    rejected_validation: int = 0
    duplicate_conflicts: int = 0
    projected_inserts: int = 0
    written: int = 0
    requests_made: int = 0
    by_publisher: dict[str, _Bucket] = field(default_factory=lambda: defaultdict(_Bucket))
    by_year: dict[str, _Bucket] = field(default_factory=lambda: defaultdict(_Bucket))
    samples: list[dict[str, Any]] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "volumes_checked": self.volumes_checked,
            "issues_checked": self.issues_checked,
            "cv_issues_with_barcode": self.cv_issues_with_barcode,
            "usable_full": self.usable_full,
            "base_only": self.base_only,
            "rejected_validation": self.rejected_validation,
            "duplicate_conflicts": self.duplicate_conflicts,
            "projected_inserts": self.projected_inserts,
            "written": self.written,
            "requests_made": self.requests_made,
            "by_publisher": {k: v.as_dict() for k, v in self.by_publisher.items()},
            "by_year": {k: v.as_dict() for k, v in self.by_year.items()},
            "samples": self.samples,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "BackfillStats":
        stats = cls(
            volumes_checked=data.get("volumes_checked", 0),
            issues_checked=data.get("issues_checked", 0),
            cv_issues_with_barcode=data.get("cv_issues_with_barcode", 0),
            usable_full=data.get("usable_full", 0),
            base_only=data.get("base_only", 0),
            rejected_validation=data.get("rejected_validation", 0),
            duplicate_conflicts=data.get("duplicate_conflicts", 0),
            projected_inserts=data.get("projected_inserts", 0),
            written=data.get("written", 0),
            requests_made=data.get("requests_made", 0),
            samples=list(data.get("samples", [])),
        )
        for key, bucket in (data.get("by_publisher") or {}).items():
            stats.by_publisher[key] = _Bucket(**bucket)
        for key, bucket in (data.get("by_year") or {}).items():
            stats.by_year[key] = _Bucket(**bucket)
        return stats


@dataclass
class _ResumeState:
    processed_series_ids: set[int]
    stats: BackfillStats

    @classmethod
    def load(cls, path: Path | None) -> "_ResumeState":
        if path is not None and path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return cls(
                    processed_series_ids=set(int(x) for x in data.get("processed_series_ids", [])),
                    stats=BackfillStats.from_json(data.get("stats", {})),
                )
            except Exception:
                logger.warning("backfill resume file unreadable, starting fresh: %s", path, exc_info=True)
        return cls(processed_series_ids=set(), stats=BackfillStats())

    def save(self, path: Path | None) -> None:
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "processed_series_ids": sorted(self.processed_series_ids),
            "stats": self.stats.to_json(),
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _publisher_names(session: Session) -> dict[int, str]:
    rows = session.exec(select(CatalogPublisher.id, CatalogPublisher.name)).all()
    return {int(pid): name for pid, name in rows if pid is not None}


def _cv_issue_id(issue: CatalogIssue) -> str | None:
    bucket = (issue.external_source_ids or {}).get("COMICVINE") or {}
    if isinstance(bucket, dict):
        for key in bucket:
            return str(key)
    return None


def _record(bucket_map: dict[str, _Bucket], key: str, attr: str, amount: int = 1) -> None:
    setattr(bucket_map[key], attr, getattr(bucket_map[key], attr) + amount)


def _fetch_volume_issues(importer: Any, volume_id: str, stats: BackfillStats) -> list[dict[str, Any]]:
    """One+ ComicVine requests: all issues for a volume with their barcode field."""
    page_limit = clamp_page_limit(100, path="issues/")
    offset = 0
    out: list[dict[str, Any]] = []
    while True:
        params = {
            "offset": offset,
            "limit": page_limit,
            "filter": f"volume:{volume_id}",
            "field_list": ISSUE_FIELD_LIST,
        }
        payload = importer._get("issues/", params=params)
        stats.requests_made += 1
        rows = payload_results(payload)
        out.extend(rows)
        if len(rows) < page_limit:
            break
        offset += page_limit
    return out


def _local_issue_index(
    session: Session, series_id: int
) -> tuple[dict[str, CatalogIssue], dict[str, CatalogIssue]]:
    issues = session.exec(select(CatalogIssue).where(CatalogIssue.series_id == series_id)).all()
    by_cv: dict[str, CatalogIssue] = {}
    by_number: dict[str, CatalogIssue] = {}
    for issue in issues:
        cv_id = _cv_issue_id(issue)
        if cv_id is not None:
            by_cv[cv_id] = issue
        by_number.setdefault(issue.normalized_issue_number, issue)
    return by_cv, by_number


def _process_volume(
    session: Session,
    importer: Any,
    *,
    series: CatalogSeries,
    publisher_name: str,
    stats: BackfillStats,
    write: bool,
) -> None:
    volume_id = comicvine_volume_id_for_series(series)
    if volume_id is None:
        return
    rows = _fetch_volume_issues(importer, volume_id, stats)
    by_cv, by_number = _local_issue_index(session, int(series.id or 0))
    year_fallback = series.start_year

    for row in rows:
        stats.issues_checked += 1
        barcodes = [b for b in comicvine_barcodes_from_issue_row(row) if normalize_upc(b)]
        if not barcodes:
            continue
        stats.cv_issues_with_barcode += 1

        cv_issue_id = str(row.get("id")) if row.get("id") is not None else None
        local = by_cv.get(cv_issue_id or "")
        if local is None:
            local = by_number.get(normalize_issue_number(str(row.get("issue_number") or "")))

        year = _year_from_dates(row.get("cover_date"), row.get("store_date"), row.get("date_added"))
        if year is None and local is not None and local.cover_date is not None:
            year = local.cover_date.year
        if year is None:
            year = year_fallback
        year_key = str(year) if year is not None else "unknown"
        issue_number = local.issue_number if local is not None else str(row.get("issue_number") or "")

        _record(stats.by_publisher, publisher_name, "with_barcode")
        _record(stats.by_year, year_key, "with_barcode")

        for raw in barcodes:
            normalized = normalize_upc(raw)
            is_full = len(normalized) >= FULL_BARCODE_MIN_LEN

            if local is None:
                stats.rejected_validation += 1
                _record(stats.by_publisher, publisher_name, "rejected")
                _record(stats.by_year, year_key, "rejected")
                _add_sample(stats, normalized, None, cv_issue_id, publisher_name, series.name, issue_number, year, "no_local_issue")
                continue

            validation = validate_barcode_catalog_match(
                normalized,
                publisher=publisher_name,
                issue_number=issue_number,
                year=str(year) if year is not None else None,
            )
            if validation.status != "exact_match":
                stats.rejected_validation += 1
                _record(stats.by_publisher, publisher_name, "rejected")
                _record(stats.by_year, year_key, "rejected")
                _add_sample(stats, normalized, int(local.id or 0), cv_issue_id, publisher_name, series.name, issue_number, year, validation.status)
                continue

            if is_full:
                stats.usable_full += 1
                _record(stats.by_publisher, publisher_name, "usable_full")
                _record(stats.by_year, year_key, "usable_full")
            else:
                stats.base_only += 1
                _record(stats.by_publisher, publisher_name, "base_only")
                _record(stats.by_year, year_key, "base_only")

            existing = session.exec(
                select(CatalogUpc).where(CatalogUpc.normalized_upc == normalized)
            ).first()
            if existing is not None and existing.issue_id is not None and int(existing.issue_id) != int(local.id or 0):
                stats.duplicate_conflicts += 1
                _record(stats.by_publisher, publisher_name, "conflicts")
                _record(stats.by_year, year_key, "conflicts")
                _add_sample(stats, normalized, int(local.id or 0), cv_issue_id, publisher_name, series.name, issue_number, year, "duplicate_conflict")
                continue
            if existing is not None:
                continue  # already mapped to this issue

            stats.projected_inserts += 1
            _record(stats.by_publisher, publisher_name, "projected_inserts")
            _record(stats.by_year, year_key, "projected_inserts")
            _add_sample(stats, normalized, int(local.id or 0), cv_issue_id, publisher_name, series.name, issue_number, year, "exact_match")

            if write:
                variant = session.exec(
                    select(CatalogVariant).where(CatalogVariant.issue_id == int(local.id or 0))
                ).first()
                upsert_upc(
                    session,
                    raw_upc=raw,
                    issue_id=int(local.id or 0),
                    variant_id=int(variant.id) if variant is not None and variant.id is not None else None,
                    source="COMICVINE_BACKFILL",
                    barcode_type="upc",
                )
                stats.written += 1


def _add_sample(
    stats: BackfillStats,
    barcode: str,
    local_issue_id: int | None,
    cv_issue_id: str | None,
    publisher: str,
    series: str,
    issue_number: str,
    year: int | None,
    status: str,
) -> None:
    if len(stats.samples) >= MAX_SAMPLES:
        return
    stats.samples.append(
        {
            "barcode": barcode,
            "local_issue_id": local_issue_id,
            "comicvine_issue_id": cv_issue_id,
            "publisher": publisher,
            "series": series,
            "issue_number": issue_number,
            "year": year,
            "validation_status": status,
        }
    )


def run_backfill(
    session: Session,
    importer: Any,
    *,
    write: bool = False,
    limit_volumes: int | None = None,
    max_requests: int | None = None,
    resume_path: Path | None = None,
) -> BackfillStats:
    """Walk ComicVine-linked series, validate barcodes, and report/insert ``catalog_upc`` rows."""
    state = _ResumeState.load(resume_path)
    stats = state.stats
    publishers = _publisher_names(session)

    series_rows = session.exec(
        select(CatalogSeries).order_by(CatalogSeries.id.asc())
    ).all()

    processed_this_run = 0
    for series in series_rows:
        sid = int(series.id or 0)
        if sid in state.processed_series_ids:
            continue
        if limit_volumes is not None and processed_this_run >= limit_volumes:
            break
        if max_requests is not None and stats.requests_made >= max_requests:
            logger.info("backfill hit max_requests=%s; stopping", max_requests)
            break

        publisher_name = publishers.get(int(series.publisher_id), "Unknown") if series.publisher_id else "Unknown"
        try:
            _process_volume(
                session, importer, series=series, publisher_name=publisher_name, stats=stats, write=write
            )
        except ComicVineThrottleError:
            logger.warning("ComicVine throttle (HTTP 420); stopping run cleanly so it can resume later")
            break
        except Exception:
            logger.exception("backfill failed for series_id=%s", sid)
            # Skip this series but keep going.

        state.processed_series_ids.add(sid)
        stats.volumes_checked += 1
        processed_this_run += 1

        if write:
            session.commit()
        if processed_this_run % SAVE_EVERY == 0:
            state.save(resume_path)
            logger.info(
                "backfill progress: volumes=%s issues=%s inserts(projected)=%s conflicts=%s requests=%s",
                stats.volumes_checked,
                stats.issues_checked,
                stats.projected_inserts,
                stats.duplicate_conflicts,
                stats.requests_made,
            )

    state.save(resume_path)
    return stats
