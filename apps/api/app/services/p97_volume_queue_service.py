"""P97 ComicVine known-good volume queue — durable, no-duplicate acquisition queue.

The queue stores exact ComicVine volume ids to import. It is the replacement for
publisher-offset / series-search brute force crawling. Rows are imported exactly once
(status ``imported`` is terminal unless explicitly reprocessed).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.catalog_master import CatalogSeries
from app.models.catalog_p97 import P97ComicVineVolumeQueue

STATUS_PENDING = "pending"
STATUS_IMPORTING = "importing"
STATUS_IMPORTED = "imported"
STATUS_EXHAUSTED = "exhausted"
STATUS_FAILED = "failed"
STATUS_THROTTLED = "throttled"

QUEUE_STATUSES = (
    STATUS_PENDING,
    STATUS_IMPORTING,
    STATUS_IMPORTED,
    STATUS_EXHAUSTED,
    STATUS_FAILED,
    STATUS_THROTTLED,
)

SOURCE_EXISTING_CATALOG = "existing_catalog"
SOURCE_MANUAL_SEED = "manual_seed"
SOURCE_SUCCESSFUL_LOG = "successful_log"

# Recent known-good manual seeds (observed from successful import logs).
KNOWN_GOOD_MANUAL_SEEDS: tuple[dict[str, Any], ...] = (
    {"comicvine_volume_id": 87154, "series_name": "Amazing Spider-Man", "publisher": "Marvel"},
    {"comicvine_volume_id": 56505, "series_name": "Amazing Spider-Man", "publisher": "Marvel"},
    {"comicvine_volume_id": 152139, "series_name": "Amazing Spider-Man", "publisher": "Marvel"},
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class SeedResult:
    inserted: int = 0
    updated: int = 0
    already_exists: int = 0
    seeded_volume_ids: list[int] = field(default_factory=list)

    def merge(self, other: "SeedResult") -> None:
        self.inserted += other.inserted
        self.updated += other.updated
        self.already_exists += other.already_exists
        self.seeded_volume_ids.extend(other.seeded_volume_ids)

    def as_dict(self) -> dict[str, Any]:
        return {
            "inserted": self.inserted,
            "updated": self.updated,
            "already_exists": self.already_exists,
        }


def get_queue_row(session: Session, comicvine_volume_id: int) -> P97ComicVineVolumeQueue | None:
    return session.exec(
        select(P97ComicVineVolumeQueue).where(
            P97ComicVineVolumeQueue.comicvine_volume_id == int(comicvine_volume_id)
        )
    ).first()


def upsert_queue_volume(
    session: Session,
    *,
    comicvine_volume_id: int,
    publisher: str | None = None,
    series_name: str | None = None,
    source_query: str | None = None,
    source_type: str = SOURCE_EXISTING_CATALOG,
    priority: int = 100,
    estimated_issue_count: int | None = None,
    dry_run: bool = False,
) -> tuple[str, P97ComicVineVolumeQueue | None]:
    """Idempotently add or enrich a queue row.

    Returns one of ``inserted`` / ``updated`` / ``already_exists`` plus the row.
    Existing rows are NEVER duplicated and their status/counters are NEVER reset; only
    missing metadata fields are filled in.
    """
    volume_id = int(comicvine_volume_id)
    existing = get_queue_row(session, volume_id)
    if existing is None:
        if dry_run:
            return "inserted", None
        row = P97ComicVineVolumeQueue(
            comicvine_volume_id=volume_id,
            publisher=publisher,
            series_name=series_name,
            source_query=source_query,
            source_type=source_type,
            priority=priority,
            estimated_issue_count=estimated_issue_count,
            status=STATUS_PENDING,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return "inserted", row

    changed = False
    if not existing.publisher and publisher:
        existing.publisher = publisher
        changed = True
    if not existing.series_name and series_name:
        existing.series_name = series_name
        changed = True
    if not existing.source_query and source_query:
        existing.source_query = source_query
        changed = True
    if existing.estimated_issue_count is None and estimated_issue_count is not None:
        existing.estimated_issue_count = estimated_issue_count
        changed = True
    if not changed:
        return "already_exists", existing
    if dry_run:
        return "updated", existing
    existing.updated_at = _utc_now()
    session.add(existing)
    session.commit()
    session.refresh(existing)
    return "updated", existing


def _comicvine_volume_ids_for_series(series: CatalogSeries) -> list[int]:
    ext = (series.external_source_ids or {}).get("COMICVINE")
    if not isinstance(ext, dict):
        return []
    out: list[int] = []
    for key in ext.keys():
        try:
            out.append(int(key))
        except (TypeError, ValueError):
            continue
    return out


def seed_from_existing_catalog(session: Session, *, dry_run: bool = False) -> SeedResult:
    result = SeedResult()
    series_rows = session.exec(select(CatalogSeries)).all()
    for series in series_rows:
        volume_ids = _comicvine_volume_ids_for_series(series)
        for volume_id in volume_ids:
            outcome, _ = upsert_queue_volume(
                session,
                comicvine_volume_id=volume_id,
                series_name=series.name,
                source_type=SOURCE_EXISTING_CATALOG,
                dry_run=dry_run,
            )
            _tally(result, outcome, volume_id)
    return result


def seed_known_good_manual(session: Session, *, dry_run: bool = False) -> SeedResult:
    result = SeedResult()
    for seed in KNOWN_GOOD_MANUAL_SEEDS:
        outcome, _ = upsert_queue_volume(
            session,
            comicvine_volume_id=int(seed["comicvine_volume_id"]),
            publisher=seed.get("publisher"),
            series_name=seed.get("series_name"),
            source_type=SOURCE_MANUAL_SEED,
            priority=int(seed.get("priority", 50)),
            dry_run=dry_run,
        )
        _tally(result, outcome, int(seed["comicvine_volume_id"]))
    return result


def _tally(result: SeedResult, outcome: str, volume_id: int) -> None:
    if outcome == "inserted":
        result.inserted += 1
        result.seeded_volume_ids.append(volume_id)
    elif outcome == "updated":
        result.updated += 1
    else:
        result.already_exists += 1


def seed_known_good_volumes(session: Session, *, dry_run: bool = False) -> dict[str, Any]:
    result = SeedResult()
    result.merge(seed_from_existing_catalog(session, dry_run=dry_run))
    result.merge(seed_known_good_manual(session, dry_run=dry_run))
    counts = queue_counts(session)
    return {
        "inserted": result.inserted,
        "updated": result.updated,
        "already_exists": result.already_exists,
        "total_queue_pending": counts.get(STATUS_PENDING, 0),
        "total_queue_imported": counts.get(STATUS_IMPORTED, 0),
        "dry_run": dry_run,
    }


def queue_counts(session: Session) -> dict[str, int]:
    rows = session.exec(
        select(P97ComicVineVolumeQueue.status, func.count()).group_by(P97ComicVineVolumeQueue.status)
    ).all()
    counts = {status: 0 for status in QUEUE_STATUSES}
    for status, count in rows:
        counts[str(status)] = int(count)
    return counts


def select_next_pending(session: Session) -> P97ComicVineVolumeQueue | None:
    return session.exec(
        select(P97ComicVineVolumeQueue)
        .where(P97ComicVineVolumeQueue.status == STATUS_PENDING)
        .order_by(P97ComicVineVolumeQueue.priority.asc(), P97ComicVineVolumeQueue.id.asc())
    ).first()


def mark_importing(session: Session, row: P97ComicVineVolumeQueue) -> P97ComicVineVolumeQueue:
    row.status = STATUS_IMPORTING
    row.last_attempted_at = _utc_now()
    row.updated_at = _utc_now()
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def apply_import_result(
    session: Session,
    row: P97ComicVineVolumeQueue,
    *,
    issues_created: int = 0,
    issues_updated: int = 0,
    images_created: int = 0,
    api_requests_used: int = 0,
    throttled: bool = False,
    failed: bool = False,
    last_error: str | None = None,
) -> P97ComicVineVolumeQueue:
    row.issues_created = int(row.issues_created or 0) + int(issues_created)
    row.issues_updated = int(row.issues_updated or 0) + int(issues_updated)
    row.images_created = int(row.images_created or 0) + int(images_created)
    row.api_requests_used = int(row.api_requests_used or 0) + int(api_requests_used)
    now = _utc_now()
    row.last_attempted_at = now
    if throttled:
        row.status = STATUS_THROTTLED
        row.last_error = last_error or "HTTP_420_THROTTLED"
    elif failed:
        row.status = STATUS_FAILED
        row.last_error = last_error or "import_failed"
    else:
        row.status = STATUS_IMPORTED
        row.last_imported_at = now
        row.last_error = None
    row.updated_at = now
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def reset_throttled_to_pending(session: Session) -> int:
    """Re-queue throttled rows (used after a 420 pause window elapses)."""
    rows = session.exec(
        select(P97ComicVineVolumeQueue).where(P97ComicVineVolumeQueue.status == STATUS_THROTTLED)
    ).all()
    for row in rows:
        row.status = STATUS_PENDING
        row.updated_at = _utc_now()
        session.add(row)
    if rows:
        session.commit()
    return len(rows)


def issues_per_api_request(issues_created: int, api_requests_used: int) -> float:
    if api_requests_used <= 0:
        return 0.0
    return round(float(issues_created) / float(api_requests_used), 3)
