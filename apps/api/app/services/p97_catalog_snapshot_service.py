"""P97 catalog-only snapshot export/import for production sync.

Exports/imports catalog_publisher, catalog_series, catalog_issue, and catalog_image
rows linked to ComicVine (or an explicit volume id filter). No user, inventory, or order data.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Iterator

from sqlalchemy import text
from sqlmodel import Session, select

from app.models.catalog_master import CatalogImage, CatalogIssue, CatalogPublisher, CatalogSeries
from app.services.catalog_ingestion_service import (
    normalize_issue_number,
    normalize_series_name,
    upsert_image,
    upsert_issue,
    upsert_publisher,
    upsert_series,
)
from app.services.comicvine_catalog_importer import comicvine_volume_id_for_series

SCHEMA_VERSION = 1
SOURCE = "COMICVINE"


def comicvine_external_ids(external_source_ids: dict | None) -> list[str]:
    bucket = (external_source_ids or {}).get("COMICVINE")
    if not isinstance(bucket, dict):
        return []
    return [str(key) for key in bucket.keys()]


def primary_comicvine_id(external_source_ids: dict | None) -> str | None:
    ids = comicvine_external_ids(external_source_ids)
    return ids[0] if ids else None


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _parse_decimal(value: str | None) -> Decimal | None:
    if value is None or value == "":
        return None
    return Decimal(str(value))


@dataclass
class CatalogSnapshotExportStats:
    publishers: int = 0
    series: int = 0
    issues: int = 0
    images: int = 0
    volume_ids: list[int] = field(default_factory=list)


@dataclass
class CatalogSnapshotIndexPhaseStats:
    phase: str
    query: str
    rows_loaded: int
    elapsed_seconds: float
    mode: str


@dataclass
class CatalogSnapshotImportStats:
    dry_run: bool = False
    publishers_created: int = 0
    publishers_updated: int = 0
    series_created: int = 0
    series_updated: int = 0
    issues_created: int = 0
    issues_updated: int = 0
    images_created: int = 0
    images_updated: int = 0
    skipped: int = 0
    index_phases: list[CatalogSnapshotIndexPhaseStats] = field(default_factory=list)


INDEX_PROGRESS_INTERVAL = 25_000
SCOPED_COMICVINE_LOOKUP_MAX = 2_000
SMALL_SNAPSHOT_ISSUE_ROWS = 5_000


class _ImportProgress:
    def __init__(self, *, verbose: bool, emit: Callable[[str], None] | None = None) -> None:
        self.verbose = verbose
        self.phases: list[CatalogSnapshotIndexPhaseStats] = []
        self._emit = emit or (lambda message: print(f"[p97-catalog-import] {message}", flush=True))

    def log(self, message: str) -> None:
        self._emit(message)

    def phase_start(self, phase: str, query: str, *, mode: str) -> None:
        self.log(f"{phase}: starting ({mode}) — {query}")

    def phase_progress(self, phase: str, rows_loaded: int, elapsed_seconds: float) -> None:
        if self.verbose:
            self.log(f"{phase}: {rows_loaded} rows loaded ({elapsed_seconds:.1f}s elapsed)")

    def phase_done(self, phase: str, query: str, rows_loaded: int, elapsed_seconds: float, *, mode: str) -> None:
        self.phases.append(
            CatalogSnapshotIndexPhaseStats(
                phase=phase,
                query=query,
                rows_loaded=rows_loaded,
                elapsed_seconds=elapsed_seconds,
                mode=mode,
            )
        )
        self.log(f"{phase}: loaded {rows_loaded} rows in {elapsed_seconds:.2f}s ({mode})")


def _series_ids_for_volumes(session: Session, volume_ids: list[int]) -> set[int]:
    wanted = {str(int(v)) for v in volume_ids}
    matched: set[int] = set()
    for row in session.exec(select(CatalogSeries)).all():
        volume_key = comicvine_volume_id_for_series(row)
        if volume_key is not None and volume_key in wanted:
            matched.add(int(row.id or 0))
    return matched


def _collect_export_scope(
    session: Session,
    *,
    volume_ids: list[int] | None,
    full_catalog: bool,
) -> tuple[set[int], set[int], set[int], set[int]]:
    """Return publisher, series, issue, image id sets to export."""
    if full_catalog:
        series_ids = {int(row.id or 0) for row in session.exec(select(CatalogSeries)).all()}
    elif volume_ids:
        series_ids = _series_ids_for_volumes(session, volume_ids)
    else:
        series_ids = set()
        for row in session.exec(select(CatalogSeries)).all():
            if comicvine_volume_id_for_series(row) is not None:
                series_ids.add(int(row.id or 0))
        for row in session.exec(select(CatalogIssue)).all():
            if primary_comicvine_id(row.external_source_ids) is not None:
                series_ids.add(int(row.series_id))

    issue_ids: set[int] = set()
    if series_ids:
        for row in session.exec(
            select(CatalogIssue).where(CatalogIssue.series_id.in_(list(series_ids)))  # type: ignore[attr-defined]
        ).all():
            issue_ids.add(int(row.id or 0))

    publisher_ids: set[int] = set()
    for sid in series_ids:
        series = session.get(CatalogSeries, sid)
        if series is None:
            continue
        if series.publisher_id is not None:
            publisher_ids.add(int(series.publisher_id))
    for iid in issue_ids:
        issue = session.get(CatalogIssue, iid)
        if issue is not None and issue.publisher_id is not None:
            publisher_ids.add(int(issue.publisher_id))

    image_ids: set[int] = set()
    if issue_ids:
        for row in session.exec(
            select(CatalogImage).where(CatalogImage.issue_id.in_(list(issue_ids)))  # type: ignore[attr-defined]
        ).all():
            image_ids.add(int(row.id or 0))

    return publisher_ids, series_ids, issue_ids, image_ids


def _publisher_snapshot_key(row: CatalogPublisher) -> str:
    cv = primary_comicvine_id(row.external_source_ids)
    if cv:
        return f"publisher:COMICVINE:{cv}"
    return f"publisher:normalized:{row.normalized_name}"


def _series_snapshot_key(row: CatalogSeries) -> str:
    cv = comicvine_volume_id_for_series(row)
    if cv:
        return f"series:COMICVINE:{cv}"
    return f"series:normalized:{row.normalized_name}"


def _issue_snapshot_key(row: CatalogIssue) -> str:
    cv = primary_comicvine_id(row.external_source_ids)
    if cv:
        return f"issue:COMICVINE:{cv}"
    return f"issue:series:{row.series_id}:number:{row.normalized_issue_number}"


def _image_snapshot_key(row: CatalogImage, issue_key: str | None) -> str:
    if row.external_image_id:
        return f"image:external:{row.external_image_id}"
    if row.source_url:
        return f"image:url:{row.source_url}"
    return f"image:issue:{issue_key or row.issue_id}:{row.image_type}"


def export_catalog_snapshot(
    session: Session,
    output_path: Path,
    *,
    volume_ids: list[int] | None = None,
    full_catalog: bool = False,
) -> CatalogSnapshotExportStats:
    publisher_ids, series_ids, issue_ids, image_ids = _collect_export_scope(
        session,
        volume_ids=volume_ids,
        full_catalog=full_catalog,
    )
    stats = CatalogSnapshotExportStats(volume_ids=list(volume_ids or []))

    issue_key_by_id: dict[int, str] = {}
    series_key_by_id: dict[int, str] = {}
    publisher_key_by_id: dict[int, str] = {}

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        meta = {
            "record_type": "_meta",
            "schema_version": SCHEMA_VERSION,
            "exported_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "volume_ids": stats.volume_ids,
            "full_catalog": full_catalog,
        }
        handle.write(json.dumps(meta, ensure_ascii=False) + "\n")

        for pid in sorted(publisher_ids):
            row = session.get(CatalogPublisher, pid)
            if row is None:
                continue
            key = _publisher_snapshot_key(row)
            publisher_key_by_id[pid] = key
            payload = {
                "record_type": "publisher",
                "snapshot_key": key,
                "payload": _json_safe(
                    {
                        "name": row.name,
                        "normalized_name": row.normalized_name,
                        "external_source_ids": row.external_source_ids,
                        "aliases": row.aliases,
                    }
                ),
            }
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
            stats.publishers += 1

        for sid in sorted(series_ids):
            row = session.get(CatalogSeries, sid)
            if row is None:
                continue
            key = _series_snapshot_key(row)
            series_key_by_id[sid] = key
            pub_key = publisher_key_by_id.get(int(row.publisher_id or 0)) if row.publisher_id else None
            payload = {
                "record_type": "series",
                "snapshot_key": key,
                "publisher_snapshot_key": pub_key,
                "comicvine_volume_id": comicvine_volume_id_for_series(row),
                "payload": _json_safe(
                    {
                        "name": row.name,
                        "normalized_name": row.normalized_name,
                        "volume_number": row.volume_number,
                        "start_year": row.start_year,
                        "end_year": row.end_year,
                        "external_source_ids": row.external_source_ids,
                        "aliases": row.aliases,
                    }
                ),
            }
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
            stats.series += 1

        for iid in sorted(issue_ids):
            row = session.get(CatalogIssue, iid)
            if row is None:
                continue
            key = _issue_snapshot_key(row)
            issue_key_by_id[iid] = key
            series_key = series_key_by_id.get(int(row.series_id))
            pub_key = publisher_key_by_id.get(int(row.publisher_id or 0)) if row.publisher_id else None
            payload = {
                "record_type": "issue",
                "snapshot_key": key,
                "series_snapshot_key": series_key,
                "publisher_snapshot_key": pub_key,
                "comicvine_issue_id": primary_comicvine_id(row.external_source_ids),
                "payload": _json_safe(
                    {
                        "issue_number": row.issue_number,
                        "normalized_issue_number": row.normalized_issue_number,
                        "title": row.title,
                        "description": row.description,
                        "cover_date": row.cover_date,
                        "store_date": row.store_date,
                        "release_date": row.release_date,
                        "page_count": row.page_count,
                        "cover_price": row.cover_price,
                        "external_source_ids": row.external_source_ids,
                        "source_confidence": row.source_confidence,
                    }
                ),
            }
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
            stats.issues += 1

        for img_id in sorted(image_ids):
            row = session.get(CatalogImage, img_id)
            if row is None:
                continue
            issue_key = issue_key_by_id.get(int(row.issue_id or 0)) if row.issue_id else None
            payload = {
                "record_type": "image",
                "snapshot_key": _image_snapshot_key(row, issue_key),
                "issue_snapshot_key": issue_key,
                "payload": _json_safe(
                    {
                        "image_type": row.image_type,
                        "source_url": row.source_url,
                        "external_image_id": row.external_image_id,
                        "source": row.source,
                        "checksum": row.checksum,
                        "width": row.width,
                        "height": row.height,
                    }
                ),
            }
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
            stats.images += 1

    return stats


def _load_snapshot_records(input_path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with input_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def _snapshot_comicvine_ids(records: list[dict[str, Any]]) -> tuple[set[str], set[str], set[str]]:
    publisher_cv_ids: set[str] = set()
    volume_ids: set[str] = set()
    issue_cv_ids: set[str] = set()
    for record in records:
        record_type = record.get("record_type")
        if record_type == "publisher":
            payload = record.get("payload") or {}
            publisher_cv_ids.update(comicvine_external_ids(payload.get("external_source_ids")))
        elif record_type == "series":
            volume_id = record.get("comicvine_volume_id")
            if volume_id is not None:
                volume_ids.add(str(volume_id))
            payload = record.get("payload") or {}
            bucket = (payload.get("external_source_ids") or {}).get("COMICVINE")
            if isinstance(bucket, dict):
                for key in bucket.keys():
                    volume_ids.add(str(key))
        elif record_type == "issue":
            cv_issue = record.get("comicvine_issue_id")
            if cv_issue is not None:
                issue_cv_ids.add(str(cv_issue))
            payload = record.get("payload") or {}
            primary = primary_comicvine_id(payload.get("external_source_ids"))
            if primary:
                issue_cv_ids.add(str(primary))
    return publisher_cv_ids, volume_ids, issue_cv_ids


def _session_dialect_name(session: Session) -> str:
    bind = session.get_bind()
    return str(getattr(getattr(bind, "dialect", None), "name", "") or "")


def _stream_catalog_rows(
    session: Session,
    model: type[Any],
    *,
    progress: _ImportProgress,
    phase: str,
    query: str,
) -> Iterator[Any]:
    started = time.perf_counter()
    progress.phase_start(phase, query, mode="full_table_scan")
    count = 0
    for row in session.exec(select(model)).yield_per(500):
        count += 1
        if count % INDEX_PROGRESS_INTERVAL == 0:
            progress.phase_progress(phase, count, time.perf_counter() - started)
        yield row
    progress.phase_done(phase, query, count, time.perf_counter() - started, mode="full_table_scan")


def _select_issue_id_by_comicvine_postgres(session: Session, cv_id: str) -> int | None:
    row = session.exec(
        text(
            "SELECT id FROM catalog_issue "
            "WHERE external_source_ids IS NOT NULL "
            "AND external_source_ids->'COMICVINE' ? :cv_id "
            "LIMIT 1"
        ),
        params={"cv_id": cv_id},
    ).first()
    if row is None:
        return None
    return int(row[0] if isinstance(row, tuple) else row)


def _select_series_id_by_comicvine_postgres(session: Session, volume_id: str) -> int | None:
    row = session.exec(
        text(
            "SELECT id FROM catalog_series "
            "WHERE external_source_ids IS NOT NULL "
            "AND external_source_ids->'COMICVINE' ? :volume_id "
            "LIMIT 1"
        ),
        params={"volume_id": volume_id},
    ).first()
    if row is None:
        return None
    return int(row[0] if isinstance(row, tuple) else row)


def _find_issue_by_comicvine_id(session: Session, cv_id: str) -> CatalogIssue | None:
    if _session_dialect_name(session) == "postgresql":
        issue_id = _select_issue_id_by_comicvine_postgres(session, cv_id)
        return session.get(CatalogIssue, issue_id) if issue_id else None
    for row in session.exec(select(CatalogIssue)).all():
        if cv_id in comicvine_external_ids(row.external_source_ids):
            return row
    return None


def _find_series_by_comicvine_volume(session: Session, volume_id: str) -> CatalogSeries | None:
    if _session_dialect_name(session) == "postgresql":
        series_id = _select_series_id_by_comicvine_postgres(session, volume_id)
        return session.get(CatalogSeries, series_id) if series_id else None
    for row in session.exec(select(CatalogSeries)).all():
        if comicvine_volume_id_for_series(row) == volume_id:
            return row
    return None


def _should_use_scoped_issue_index(issue_row_count: int, issue_cv_id_count: int) -> bool:
    if issue_cv_id_count == 0 or issue_cv_id_count > SCOPED_COMICVINE_LOOKUP_MAX:
        return False
    if issue_row_count <= SMALL_SNAPSHOT_ISSUE_ROWS:
        return True
    return issue_cv_id_count * 50 < issue_row_count


def _build_publisher_index(
    session: Session,
    progress: _ImportProgress,
) -> tuple[dict[str, CatalogPublisher], dict[str, CatalogPublisher]]:
    query = "SELECT catalog_publisher (full table)"
    by_norm: dict[str, CatalogPublisher] = {}
    by_cv: dict[str, CatalogPublisher] = {}
    for row in _stream_catalog_rows(
        session,
        CatalogPublisher,
        progress=progress,
        phase="_build_publisher_index",
        query=query,
    ):
        by_norm[row.normalized_name] = row
        for cv in comicvine_external_ids(row.external_source_ids):
            by_cv[cv] = row
    return by_norm, by_cv


def _build_series_index(
    session: Session,
    progress: _ImportProgress,
    *,
    snapshot_volume_ids: set[str],
    issue_row_count: int,
) -> tuple[dict[str, CatalogSeries], dict[tuple[str, int | None], CatalogSeries]]:
    by_volume: dict[str, CatalogSeries] = {}
    by_norm_pub: dict[tuple[str, int | None], CatalogSeries] = {}
    use_scoped = (
        snapshot_volume_ids
        and len(snapshot_volume_ids) <= SCOPED_COMICVINE_LOOKUP_MAX
        and issue_row_count <= SMALL_SNAPSHOT_ISSUE_ROWS
    )
    if use_scoped:
        query = "SELECT catalog_series WHERE external_source_ids->'COMICVINE' ? :volume_id (per snapshot volume)"
        progress.phase_start("_build_series_index", query, mode="scoped_comicvine_lookup")
        started = time.perf_counter()
        for volume_id in sorted(snapshot_volume_ids):
            row = _find_series_by_comicvine_volume(session, volume_id)
            if row is None:
                continue
            by_volume[volume_id] = row
            by_norm_pub[(row.normalized_name, row.publisher_id)] = row
        progress.phase_done(
            "_build_series_index",
            query,
            len(by_volume),
            time.perf_counter() - started,
            mode="scoped_comicvine_lookup",
        )
        return by_volume, by_norm_pub

    query = "SELECT catalog_series (full table)"
    for row in _stream_catalog_rows(
        session,
        CatalogSeries,
        progress=progress,
        phase="_build_series_index",
        query=query,
    ):
        volume_id = comicvine_volume_id_for_series(row)
        if volume_id:
            by_volume[volume_id] = row
        by_norm_pub[(row.normalized_name, row.publisher_id)] = row
    return by_volume, by_norm_pub


def _build_issue_index(
    session: Session,
    progress: _ImportProgress,
    *,
    snapshot_issue_cv_ids: set[str],
    issue_row_count: int,
) -> tuple[dict[str, CatalogIssue], dict[tuple[int, str], CatalogIssue]]:
    by_cv: dict[str, CatalogIssue] = {}
    by_series_number: dict[tuple[int, str], CatalogIssue] = {}

    if _should_use_scoped_issue_index(issue_row_count, len(snapshot_issue_cv_ids)):
        query = (
            "SELECT catalog_issue WHERE external_source_ids->'COMICVINE' ? :cv_id "
            "(per snapshot issue; avoids full-table read)"
        )
        progress.phase_start("_build_issue_index", query, mode="scoped_comicvine_lookup")
        started = time.perf_counter()
        for cv_id in sorted(snapshot_issue_cv_ids):
            row = _find_issue_by_comicvine_id(session, cv_id)
            if row is None:
                continue
            by_cv[cv_id] = row
            by_series_number[(int(row.series_id), row.normalized_issue_number)] = row
        progress.phase_done(
            "_build_issue_index",
            query,
            len(by_cv),
            time.perf_counter() - started,
            mode="scoped_comicvine_lookup",
        )
        return by_cv, by_series_number

    query = "SELECT catalog_issue (full table — dominant cost on large production DBs)"
    for row in _stream_catalog_rows(
        session,
        CatalogIssue,
        progress=progress,
        phase="_build_issue_index",
        query=query,
    ):
        cv = primary_comicvine_id(row.external_source_ids)
        if cv:
            by_cv[cv] = row
        by_series_number[(int(row.series_id), row.normalized_issue_number)] = row
    return by_cv, by_series_number


def _build_image_index(
    session: Session,
    progress: _ImportProgress,
    issue_ids: set[int],
) -> dict[tuple[int, str], CatalogImage]:
    by_issue_url: dict[tuple[int, str], CatalogImage] = {}
    if not issue_ids:
        progress.phase_done(
            "_build_image_index",
            "SELECT catalog_image (skipped — no resolved issue ids yet)",
            0,
            0.0,
            mode="scoped_issue_ids",
        )
        return by_issue_url

    query = "SELECT catalog_image WHERE issue_id IN (<snapshot issue ids>)"
    progress.phase_start("_build_image_index", query, mode="scoped_issue_ids")
    started = time.perf_counter()
    count = 0
    id_list = sorted(issue_ids)
    chunk_size = 500
    for offset in range(0, len(id_list), chunk_size):
        chunk = id_list[offset : offset + chunk_size]
        for row in session.exec(
            select(CatalogImage).where(CatalogImage.issue_id.in_(chunk))  # type: ignore[attr-defined]
        ).all():
            count += 1
            if row.source_url:
                by_issue_url[(int(row.issue_id or 0), str(row.source_url))] = row
    progress.phase_done(
        "_build_image_index",
        query,
        count,
        time.perf_counter() - started,
        mode="scoped_issue_ids",
    )
    return by_issue_url


def _find_publisher(
    pub_by_norm: dict[str, CatalogPublisher],
    pub_by_cv: dict[str, CatalogPublisher],
    payload: dict[str, Any],
) -> CatalogPublisher | None:
    for cv in comicvine_external_ids(payload.get("external_source_ids") or {}):
        if cv in pub_by_cv:
            return pub_by_cv[cv]
    normalized = str(payload.get("normalized_name") or normalize_series_name(str(payload.get("name") or "")))
    return pub_by_norm.get(normalized)


def _find_series(
    series_by_volume: dict[str, CatalogSeries],
    series_by_norm_pub: dict[tuple[str, int | None], CatalogSeries],
    *,
    comicvine_volume_id: str | None,
    payload: dict[str, Any],
    publisher_id: int | None,
) -> CatalogSeries | None:
    if comicvine_volume_id and comicvine_volume_id in series_by_volume:
        return series_by_volume[comicvine_volume_id]
    normalized = str(payload.get("normalized_name") or normalize_series_name(str(payload.get("name") or "")))
    return series_by_norm_pub.get((normalized, publisher_id))


def _find_issue(
    issues_by_cv: dict[str, CatalogIssue],
    issues_by_series_number: dict[tuple[int, str], CatalogIssue],
    *,
    comicvine_issue_id: str | None,
    series_id: int | None,
    payload: dict[str, Any],
) -> CatalogIssue | None:
    if comicvine_issue_id and comicvine_issue_id in issues_by_cv:
        return issues_by_cv[comicvine_issue_id]
    if series_id is None:
        return None
    normalized_number = str(
        payload.get("normalized_issue_number")
        or normalize_issue_number(str(payload.get("issue_number") or ""))
    )
    return issues_by_series_number.get((series_id, normalized_number))


def import_catalog_snapshot(
    session: Session,
    input_path: Path,
    *,
    dry_run: bool = False,
    verbose: bool = False,
) -> CatalogSnapshotImportStats:
    progress = _ImportProgress(verbose=verbose)
    load_started = time.perf_counter()
    progress.log(f"Loading snapshot JSONL: {input_path}")
    records = _load_snapshot_records(input_path)
    progress.log(
        f"Snapshot parsed: {len(records)} lines in {time.perf_counter() - load_started:.2f}s"
    )

    stats = CatalogSnapshotImportStats(dry_run=dry_run)
    _, snapshot_volume_ids, snapshot_issue_cv_ids = _snapshot_comicvine_ids(records)
    issue_rows = [r for r in records if r.get("record_type") == "issue"]

    pub_by_norm, pub_by_cv = _build_publisher_index(session, progress)
    series_by_volume, series_by_norm_pub = _build_series_index(
        session,
        progress,
        snapshot_volume_ids=snapshot_volume_ids,
        issue_row_count=len(issue_rows),
    )
    issues_by_cv, issues_by_series_number = _build_issue_index(
        session,
        progress,
        snapshot_issue_cv_ids=snapshot_issue_cv_ids,
        issue_row_count=len(issue_rows),
    )
    stats.index_phases = list(progress.phases)

    snapshot_publisher_id: dict[str, int] = {}
    snapshot_series_id: dict[str, int] = {}
    snapshot_issue_id: dict[str, int] = {}

    publishers = [r for r in records if r.get("record_type") == "publisher"]
    series_rows = [r for r in records if r.get("record_type") == "series"]
    issue_rows = [r for r in records if r.get("record_type") == "issue"]
    image_rows = [r for r in records if r.get("record_type") == "image"]
    publisher_payload_by_key = {str(r.get("snapshot_key")): r.get("payload") or {} for r in publishers}

    for record in publishers:
        key = str(record.get("snapshot_key") or "")
        payload = record.get("payload") or {}
        if not key:
            stats.skipped += 1
            continue
        existing = _find_publisher(pub_by_norm, pub_by_cv, payload)
        cv = primary_comicvine_id(payload.get("external_source_ids"))
        if dry_run:
            if existing is None:
                stats.publishers_created += 1
            else:
                stats.publishers_updated += 1
            snapshot_publisher_id[key] = int(existing.id or 0) if existing else 0
            continue
        before_id = existing.id if existing else None
        row = upsert_publisher(
            session,
            name=str(payload.get("name") or "Unknown"),
            source=SOURCE,
            external_id=cv,
            aliases=payload.get("aliases"),
        )
        if before_id is None:
            stats.publishers_created += 1
        else:
            stats.publishers_updated += 1
        snapshot_publisher_id[key] = int(row.id or 0)
        pub_by_norm[row.normalized_name] = row
        for cv_key in comicvine_external_ids(row.external_source_ids):
            pub_by_cv[cv_key] = row

    for record in series_rows:
        key = str(record.get("snapshot_key") or "")
        payload = record.get("payload") or {}
        if not key:
            stats.skipped += 1
            continue
        pub_key = record.get("publisher_snapshot_key")
        publisher_id = snapshot_publisher_id.get(str(pub_key)) if pub_key else None
        if not publisher_id and pub_key:
            pub_payload = publisher_payload_by_key.get(str(pub_key), {})
            existing_pub = _find_publisher(pub_by_norm, pub_by_cv, pub_payload)
            publisher_id = int(existing_pub.id or 0) if existing_pub else None
        volume_id = record.get("comicvine_volume_id")
        existing = _find_series(
            series_by_volume,
            series_by_norm_pub,
            comicvine_volume_id=str(volume_id) if volume_id else None,
            payload=payload,
            publisher_id=publisher_id,
        )
        cv = str(volume_id) if volume_id else primary_comicvine_id(payload.get("external_source_ids"))
        if dry_run:
            if existing is None:
                stats.series_created += 1
            else:
                stats.series_updated += 1
            snapshot_series_id[key] = int(existing.id or 0) if existing else 0
            continue
        before_id = existing.id if existing else None
        row = upsert_series(
            session,
            name=str(payload.get("name") or "Unknown"),
            publisher_id=publisher_id,
            source=SOURCE,
            external_id=cv,
            volume_number=payload.get("volume_number"),
            start_year=payload.get("start_year"),
            end_year=payload.get("end_year"),
        )
        if before_id is None:
            stats.series_created += 1
        else:
            stats.series_updated += 1
        snapshot_series_id[key] = int(row.id or 0)
        if cv:
            series_by_volume[str(cv)] = row
        series_by_norm_pub[(row.normalized_name, row.publisher_id)] = row

    for record in issue_rows:
        key = str(record.get("snapshot_key") or "")
        payload = record.get("payload") or {}
        if not key:
            stats.skipped += 1
            continue
        series_key = record.get("series_snapshot_key")
        series_id = snapshot_series_id.get(str(series_key)) if series_key else None
        if not series_id and series_key:
            for candidate in series_rows:
                if str(candidate.get("snapshot_key")) == str(series_key):
                    volume_id = candidate.get("comicvine_volume_id")
                    existing_series = _find_series(
                        series_by_volume,
                        series_by_norm_pub,
                        comicvine_volume_id=str(volume_id) if volume_id else None,
                        payload=candidate.get("payload") or {},
                        publisher_id=None,
                    )
                    if existing_series is not None:
                        series_id = int(existing_series.id or 0)
                    break
        pub_key = record.get("publisher_snapshot_key")
        publisher_id = snapshot_publisher_id.get(str(pub_key)) if pub_key else None
        if not publisher_id and pub_key:
            pub_payload = publisher_payload_by_key.get(str(pub_key), {})
            existing_pub = _find_publisher(pub_by_norm, pub_by_cv, pub_payload)
            publisher_id = int(existing_pub.id or 0) if existing_pub else None
        cv_issue = record.get("comicvine_issue_id")
        existing = _find_issue(
            issues_by_cv,
            issues_by_series_number,
            comicvine_issue_id=str(cv_issue) if cv_issue else None,
            series_id=series_id,
            payload=payload,
        )
        if series_id is None and existing is None:
            stats.skipped += 1
            continue
        if dry_run:
            if existing is None:
                stats.issues_created += 1
            else:
                stats.issues_updated += 1
            snapshot_issue_id[key] = int(existing.id or 0) if existing else 0
            continue
        if series_id is None:
            stats.skipped += 1
            continue
        before_id = existing.id if existing else None
        row = upsert_issue(
            session,
            series_id=int(series_id),
            publisher_id=publisher_id,
            issue_number=str(payload.get("issue_number") or "?"),
            source=SOURCE,
            external_id=str(cv_issue) if cv_issue else None,
            title=payload.get("title"),
            description=payload.get("description"),
            cover_date=_parse_date(payload.get("cover_date")),
            store_date=_parse_date(payload.get("store_date")),
            release_date=_parse_date(payload.get("release_date")),
            page_count=payload.get("page_count"),
            cover_price=_parse_decimal(payload.get("cover_price")),
            source_confidence=_parse_decimal(payload.get("source_confidence")),
        )
        if before_id is None:
            stats.issues_created += 1
        else:
            stats.issues_updated += 1
        snapshot_issue_id[key] = int(row.id or 0)
        if cv_issue:
            issues_by_cv[str(cv_issue)] = row
        issues_by_series_number[(int(row.series_id), row.normalized_issue_number)] = row

    resolved_issue_ids = {int(issue_id) for issue_id in snapshot_issue_id.values() if issue_id}
    images_by_issue_url = _build_image_index(session, progress, resolved_issue_ids)
    stats.index_phases = list(progress.phases)

    for record in image_rows:
        payload = record.get("payload") or {}
        issue_key = record.get("issue_snapshot_key")
        issue_id = snapshot_issue_id.get(str(issue_key)) if issue_key else None
        if not issue_id and issue_key:
            for candidate in issue_rows:
                if str(candidate.get("snapshot_key")) == str(issue_key):
                    cv_issue = candidate.get("comicvine_issue_id")
                    existing_issue = _find_issue(
                        issues_by_cv,
                        issues_by_series_number,
                        comicvine_issue_id=str(cv_issue) if cv_issue else None,
                        series_id=None,
                        payload=candidate.get("payload") or {},
                    )
                    if existing_issue is not None:
                        issue_id = int(existing_issue.id or 0)
                    break
        if issue_id is None:
            stats.skipped += 1
            continue
        source_url = payload.get("source_url")
        external_image_id = payload.get("external_image_id")
        existing = None
        if source_url and issue_id:
            existing = images_by_issue_url.get((int(issue_id), str(source_url)))
            if existing is None:
                existing = session.exec(
                    select(CatalogImage)
                    .where(CatalogImage.issue_id == issue_id)
                    .where(CatalogImage.source_url == source_url)
                ).first()
                if existing is not None and source_url:
                    images_by_issue_url[(int(issue_id), str(source_url))] = existing
        if dry_run:
            if existing is None:
                stats.images_created += 1
            else:
                stats.images_updated += 1
            continue
        before_id = existing.id if existing else None
        upsert_image(
            session,
            issue_id=int(issue_id),
            variant_id=None,
            source_url=source_url,
            source=str(payload.get("source") or SOURCE),
            image_type=str(payload.get("image_type") or "cover"),
            external_image_id=external_image_id,
            local_path=None,
            checksum=payload.get("checksum"),
        )
        if before_id is None:
            stats.images_created += 1
        else:
            stats.images_updated += 1

    if not dry_run:
        session.commit()
    return stats
