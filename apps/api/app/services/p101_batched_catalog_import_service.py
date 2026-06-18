"""P101-04 batched catalog snapshot import (commit per batch, resume-safe)."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal

from sqlalchemy import func, inspect as sa_inspect, text
from sqlmodel import Session, select

from app.models.catalog_master import CatalogImage, CatalogIssue, CatalogPublisher, CatalogSeries
from app.services.catalog_ingestion_service import normalize_issue_number
from app.services.p97_catalog_snapshot_service import (
    SOURCE,
    CatalogSnapshotImportStats,
    _ImportProgress,
    _build_image_index,
    _build_issue_index,
    _build_publisher_index,
    _build_series_index,
    build_issue_id_lookup_maps,
    _find_issue,
    _find_publisher,
    _find_series,
    _load_snapshot_records,
    _parse_date,
    _parse_decimal,
    _snapshot_comicvine_ids,
    primary_comicvine_id,
)
from app.services.catalog_ingestion_service import upsert_image, upsert_issue, upsert_publisher, upsert_series
from app.services.p97_catalog_snapshot_service import comicvine_external_ids  # noqa: E402

PhaseName = Literal["publishers", "series", "issues", "images"]
PHASE_ORDER: list[PhaseName] = ["publishers", "series", "issues", "images"]

DEFAULT_BATCH_SIZES: dict[PhaseName, int] = {
    "publishers": 100,
    "series": 500,
    "issues": 1000,
    "images": 1000,
}

STATE_VERSION = 1


@dataclass
class BatchedImportState:
    version: int = STATE_VERSION
    job_id: str = ""
    input_path: str = ""
    input_fingerprint: str = ""
    database_target: str = ""
    dry_run: bool = False
    phase: PhaseName = "publishers"
    offsets: dict[str, int] = field(default_factory=lambda: {p: 0 for p in PHASE_ORDER})
    completed_phases: list[str] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)
    batch_sizes: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_BATCH_SIZES))
    started_at: str = ""
    updated_at: str = ""

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> BatchedImportState:
        offsets = {p: int((payload.get("offsets") or {}).get(p, 0)) for p in PHASE_ORDER}
        batch_sizes = dict(DEFAULT_BATCH_SIZES)
        batch_sizes.update({k: int(v) for k, v in (payload.get("batch_sizes") or {}).items() if k in DEFAULT_BATCH_SIZES})
        return cls(
            version=int(payload.get("version") or STATE_VERSION),
            job_id=str(payload.get("job_id") or ""),
            input_path=str(payload.get("input_path") or ""),
            input_fingerprint=str(payload.get("input_fingerprint") or ""),
            database_target=str(payload.get("database_target") or ""),
            dry_run=bool(payload.get("dry_run")),
            phase=_coerce_phase(payload.get("phase")),
            offsets=offsets,
            completed_phases=[str(p) for p in (payload.get("completed_phases") or [])],
            stats={str(k): int(v) for k, v in (payload.get("stats") or {}).items()},
            batch_sizes=batch_sizes,
            started_at=str(payload.get("started_at") or ""),
            updated_at=str(payload.get("updated_at") or ""),
        )


def _coerce_phase(value: Any) -> PhaseName:
    phase = str(value or "publishers")
    if phase not in PHASE_ORDER:
        raise ValueError(f"Invalid phase: {phase}")
    return phase  # type: ignore[return-value]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def fingerprint_input(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def default_state_path() -> Path:
    api_root = Path(__file__).resolve().parents[2]
    return api_root / "data" / "p101" / "batched_import_state.json"


def load_state(path: Path) -> BatchedImportState | None:
    if not path.is_file():
        return None
    return BatchedImportState.from_json(json.loads(path.read_text(encoding="utf-8")))


def save_state(path: Path, state: BatchedImportState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state.updated_at = _utc_now_iso()
    path.write_text(json.dumps(state.to_json(), indent=2), encoding="utf-8")


def catalog_table_counts(session: Session) -> dict[str, int]:
    return {
        "catalog_publisher": int(session.exec(select(func.count()).select_from(CatalogPublisher)).one()),
        "catalog_series": int(session.exec(select(func.count()).select_from(CatalogSeries)).one()),
        "catalog_issue": int(session.exec(select(func.count()).select_from(CatalogIssue)).one()),
        "catalog_image": int(session.exec(select(func.count()).select_from(CatalogImage)).one()),
    }


def verify_phase(session: Session, phase: PhaseName, *, emit: Callable[[str], None]) -> dict[str, int]:
    counts = catalog_table_counts(session)
    emit(f"[p101-verify] after phase={phase} counts={counts}")
    emit(
        "[p101-verify] rerun counts: cd apps/api && python scripts/p101_import_catalog_batched.py "
        "--verify-only --database-url <production-url>"
    )
    return counts


def _stats_to_dict(stats: CatalogSnapshotImportStats) -> dict[str, int]:
    return {
        "publishers_created": stats.publishers_created,
        "publishers_updated": stats.publishers_updated,
        "series_created": stats.series_created,
        "series_updated": stats.series_updated,
        "issues_created": stats.issues_created,
        "issues_updated": stats.issues_updated,
        "images_created": stats.images_created,
        "images_updated": stats.images_updated,
        "skipped": stats.skipped,
    }


def _merge_stats(state: BatchedImportState, batch_stats: CatalogSnapshotImportStats) -> None:
    merged = _stats_to_dict(batch_stats)
    for key, value in merged.items():
        state.stats[key] = int(state.stats.get(key, 0)) + value


@dataclass
class _ImportContext:
    records: list[dict[str, Any]]
    publishers: list[dict[str, Any]]
    series_rows: list[dict[str, Any]]
    issue_rows: list[dict[str, Any]]
    image_rows: list[dict[str, Any]]
    publisher_payload_by_key: dict[str, dict[str, Any]]
    snapshot_volume_ids: set[str]
    snapshot_issue_cv_ids: set[str]
    pub_by_norm: dict[str, CatalogPublisher]
    pub_by_cv: dict[str, CatalogPublisher]
    series_by_volume: dict[str, CatalogSeries]
    series_by_norm_pub: dict[tuple[str, int | None], CatalogSeries]
    issues_by_cv: dict[str, CatalogIssue]
    issues_by_series_number: dict[tuple[int, str], CatalogIssue]
    snapshot_publisher_id: dict[str, int]
    snapshot_series_id: dict[str, int]
    snapshot_issue_id: dict[str, int]
    issue_id_by_cv: dict[str, int]
    issue_id_by_series_number: dict[tuple[int, str], int]
    images_by_issue_url: dict[tuple[int, str], CatalogImage]
    stats: CatalogSnapshotImportStats


def _partition_records(records: list[dict[str, Any]]) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    publishers = [r for r in records if r.get("record_type") == "publisher"]
    series_rows = [r for r in records if r.get("record_type") == "series"]
    issue_rows = [r for r in records if r.get("record_type") == "issue"]
    image_rows = [r for r in records if r.get("record_type") == "image"]
    return publishers, series_rows, issue_rows, image_rows


def _rebuild_snapshot_publisher_id(
    ctx: _ImportContext,
    *,
    through_offset: int,
) -> None:
    ctx.snapshot_publisher_id.clear()
    for record in ctx.publishers[:through_offset]:
        key = str(record.get("snapshot_key") or "")
        if not key:
            continue
        payload = record.get("payload") or {}
        existing = _find_publisher(ctx.pub_by_norm, ctx.pub_by_cv, payload)
        if existing is not None and existing.id:
            ctx.snapshot_publisher_id[key] = int(existing.id)


def _rebuild_snapshot_series_id(
    ctx: _ImportContext,
    *,
    through_offset: int,
) -> None:
    ctx.snapshot_series_id.clear()
    for record in ctx.series_rows[:through_offset]:
        key = str(record.get("snapshot_key") or "")
        if not key:
            continue
        payload = record.get("payload") or {}
        pub_key = record.get("publisher_snapshot_key")
        publisher_id = ctx.snapshot_publisher_id.get(str(pub_key)) if pub_key else None
        if not publisher_id and pub_key:
            pub_payload = ctx.publisher_payload_by_key.get(str(pub_key), {})
            existing_pub = _find_publisher(ctx.pub_by_norm, ctx.pub_by_cv, pub_payload)
            publisher_id = int(existing_pub.id or 0) if existing_pub else None
        volume_id = record.get("comicvine_volume_id")
        existing = _find_series(
            ctx.series_by_volume,
            ctx.series_by_norm_pub,
            comicvine_volume_id=str(volume_id) if volume_id else None,
            payload=payload,
            publisher_id=publisher_id,
        )
        if existing is not None and existing.id:
            ctx.snapshot_series_id[key] = int(existing.id)


def _resolve_issue_id_for_snapshot_record(
    ctx: _ImportContext,
    record: dict[str, Any],
    *,
    issue_id_by_cv: dict[str, int],
    issue_id_by_series_number: dict[tuple[int, str], int],
) -> int | None:
    payload = record.get("payload") or {}
    cv_issue = record.get("comicvine_issue_id")
    if cv_issue:
        matched = issue_id_by_cv.get(str(cv_issue))
        if matched:
            return int(matched)
    series_id = _resolve_series_id_for_issue(ctx, record)
    if series_id is None:
        return None
    normalized_number = str(
        payload.get("normalized_issue_number")
        or normalize_issue_number(str(payload.get("issue_number") or ""))
    )
    return issue_id_by_series_number.get((int(series_id), normalized_number))


def _rebuild_snapshot_issue_id(
    ctx: _ImportContext,
    *,
    through_offset: int,
    issue_id_by_cv: dict[str, int],
    issue_id_by_series_number: dict[tuple[int, str], int],
) -> int:
    ctx.snapshot_issue_id.clear()
    resolved = 0
    for record in ctx.issue_rows[:through_offset]:
        key = str(record.get("snapshot_key") or "")
        if not key:
            continue
        issue_id = _resolve_issue_id_for_snapshot_record(
            ctx,
            record,
            issue_id_by_cv=issue_id_by_cv,
            issue_id_by_series_number=issue_id_by_series_number,
        )
        if issue_id:
            ctx.snapshot_issue_id[key] = int(issue_id)
            resolved += 1
    return resolved


def _prepare_context(
    session: Session,
    records: list[dict[str, Any]],
    *,
    progress: _ImportProgress,
    rebuild_maps_through: dict[PhaseName, int] | None = None,
    skip_issue_id_rebuild: bool = False,
) -> _ImportContext:
    publishers, series_rows, issue_rows, image_rows = _partition_records(records)
    _, snapshot_volume_ids, snapshot_issue_cv_ids = _snapshot_comicvine_ids(records)
    publisher_payload_by_key = {str(r.get("snapshot_key")): r.get("payload") or {} for r in publishers}

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

    ctx = _ImportContext(
        records=records,
        publishers=publishers,
        series_rows=series_rows,
        issue_rows=issue_rows,
        image_rows=image_rows,
        publisher_payload_by_key=publisher_payload_by_key,
        snapshot_volume_ids=snapshot_volume_ids,
        snapshot_issue_cv_ids=snapshot_issue_cv_ids,
        pub_by_norm=pub_by_norm,
        pub_by_cv=pub_by_cv,
        series_by_volume=series_by_volume,
        series_by_norm_pub=series_by_norm_pub,
        issues_by_cv=issues_by_cv,
        issues_by_series_number=issues_by_series_number,
        snapshot_publisher_id={},
        snapshot_series_id={},
        snapshot_issue_id={},
        issue_id_by_cv={},
        issue_id_by_series_number={},
        images_by_issue_url={},
        stats=CatalogSnapshotImportStats(),
    )

    rebuild_maps_through = rebuild_maps_through or {}
    if rebuild_maps_through.get("publishers", 0) > 0:
        _rebuild_snapshot_publisher_id(ctx, through_offset=rebuild_maps_through["publishers"])
    if rebuild_maps_through.get("series", 0) > 0:
        _rebuild_snapshot_series_id(ctx, through_offset=rebuild_maps_through["series"])
    if rebuild_maps_through.get("issues", 0) > 0 and not skip_issue_id_rebuild:
        issue_id_by_cv, issue_id_by_series_number = build_issue_id_lookup_maps(session, progress)
        ctx.issue_id_by_cv = issue_id_by_cv
        ctx.issue_id_by_series_number = issue_id_by_series_number
        _rebuild_snapshot_issue_id(
            ctx,
            through_offset=rebuild_maps_through["issues"],
            issue_id_by_cv=issue_id_by_cv,
            issue_id_by_series_number=issue_id_by_series_number,
        )
    return ctx


def _process_publisher_record(ctx: _ImportContext, session: Session, record: dict[str, Any], *, dry_run: bool) -> None:
    key = str(record.get("snapshot_key") or "")
    payload = record.get("payload") or {}
    if not key:
        ctx.stats.skipped += 1
        return
    existing = _find_publisher(ctx.pub_by_norm, ctx.pub_by_cv, payload)
    cv = primary_comicvine_id(payload.get("external_source_ids"))
    if dry_run:
        if existing is None:
            ctx.stats.publishers_created += 1
        else:
            ctx.stats.publishers_updated += 1
        ctx.snapshot_publisher_id[key] = int(existing.id or 0) if existing else 0
        return
    before_id = existing.id if existing else None
    row = upsert_publisher(
        session,
        name=str(payload.get("name") or "Unknown"),
        source=SOURCE,
        external_id=cv,
        aliases=payload.get("aliases"),
    )
    if before_id is None:
        ctx.stats.publishers_created += 1
    else:
        ctx.stats.publishers_updated += 1
    ctx.snapshot_publisher_id[key] = int(row.id or 0)
    ctx.pub_by_norm[row.normalized_name] = row
    for cv_key in comicvine_external_ids(row.external_source_ids):
        ctx.pub_by_cv[cv_key] = row


def _process_series_record(ctx: _ImportContext, session: Session, record: dict[str, Any], *, dry_run: bool) -> None:
    key = str(record.get("snapshot_key") or "")
    payload = record.get("payload") or {}
    if not key:
        ctx.stats.skipped += 1
        return
    pub_key = record.get("publisher_snapshot_key")
    publisher_id = ctx.snapshot_publisher_id.get(str(pub_key)) if pub_key else None
    if not publisher_id and pub_key:
        pub_payload = ctx.publisher_payload_by_key.get(str(pub_key), {})
        existing_pub = _find_publisher(ctx.pub_by_norm, ctx.pub_by_cv, pub_payload)
        publisher_id = int(existing_pub.id or 0) if existing_pub else None
    volume_id = record.get("comicvine_volume_id")
    existing = _find_series(
        ctx.series_by_volume,
        ctx.series_by_norm_pub,
        comicvine_volume_id=str(volume_id) if volume_id else None,
        payload=payload,
        publisher_id=publisher_id,
    )
    cv = str(volume_id) if volume_id else primary_comicvine_id(payload.get("external_source_ids"))
    if dry_run:
        if existing is None:
            ctx.stats.series_created += 1
        else:
            ctx.stats.series_updated += 1
        ctx.snapshot_series_id[key] = int(existing.id or 0) if existing else 0
        return
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
        ctx.stats.series_created += 1
    else:
        ctx.stats.series_updated += 1
    ctx.snapshot_series_id[key] = int(row.id or 0)
    if cv:
        ctx.series_by_volume[str(cv)] = row
    ctx.series_by_norm_pub[(row.normalized_name, row.publisher_id)] = row


def _resolve_series_id_for_issue(ctx: _ImportContext, record: dict[str, Any]) -> int | None:
    series_key = record.get("series_snapshot_key")
    series_id = ctx.snapshot_series_id.get(str(series_key)) if series_key else None
    if series_id or not series_key:
        return int(series_id) if series_id else None
    for candidate in ctx.series_rows:
        if str(candidate.get("snapshot_key")) != str(series_key):
            continue
        volume_id = candidate.get("comicvine_volume_id")
        existing_series = _find_series(
            ctx.series_by_volume,
            ctx.series_by_norm_pub,
            comicvine_volume_id=str(volume_id) if volume_id else None,
            payload=candidate.get("payload") or {},
            publisher_id=None,
        )
        if existing_series is not None:
            return int(existing_series.id or 0)
    return None


def _process_issue_record(ctx: _ImportContext, session: Session, record: dict[str, Any], *, dry_run: bool) -> None:
    key = str(record.get("snapshot_key") or "")
    payload = record.get("payload") or {}
    if not key:
        ctx.stats.skipped += 1
        return
    series_id = _resolve_series_id_for_issue(ctx, record)
    pub_key = record.get("publisher_snapshot_key")
    publisher_id = ctx.snapshot_publisher_id.get(str(pub_key)) if pub_key else None
    if not publisher_id and pub_key:
        pub_payload = ctx.publisher_payload_by_key.get(str(pub_key), {})
        existing_pub = _find_publisher(ctx.pub_by_norm, ctx.pub_by_cv, pub_payload)
        publisher_id = int(existing_pub.id or 0) if existing_pub else None
    cv_issue = record.get("comicvine_issue_id")
    existing = _find_issue(
        ctx.issues_by_cv,
        ctx.issues_by_series_number,
        comicvine_issue_id=str(cv_issue) if cv_issue else None,
        series_id=series_id,
        payload=payload,
    )
    if series_id is None and existing is None:
        ctx.stats.skipped += 1
        return
    if dry_run:
        if existing is None:
            ctx.stats.issues_created += 1
        else:
            ctx.stats.issues_updated += 1
        ctx.snapshot_issue_id[key] = int(existing.id or 0) if existing else 0
        return
    if series_id is None:
        ctx.stats.skipped += 1
        return
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
        ctx.stats.issues_created += 1
    else:
        ctx.stats.issues_updated += 1
    ctx.snapshot_issue_id[key] = int(row.id or 0)
    if cv_issue:
        ctx.issues_by_cv[str(cv_issue)] = row
    ctx.issues_by_series_number[(int(row.series_id), row.normalized_issue_number)] = row


def _resolve_issue_id_for_image(ctx: _ImportContext, record: dict[str, Any]) -> int | None:
    issue_key = record.get("issue_snapshot_key")
    issue_id = ctx.snapshot_issue_id.get(str(issue_key)) if issue_key else None
    if issue_id or not issue_key:
        return int(issue_id) if issue_id else None
    for candidate in ctx.issue_rows:
        if str(candidate.get("snapshot_key")) != str(issue_key):
            continue
        if ctx.issue_id_by_cv or ctx.issue_id_by_series_number:
            resolved = _resolve_issue_id_for_snapshot_record(
                ctx,
                candidate,
                issue_id_by_cv=ctx.issue_id_by_cv,
                issue_id_by_series_number=ctx.issue_id_by_series_number,
            )
            if resolved:
                return int(resolved)
        cv_issue = candidate.get("comicvine_issue_id")
        existing_issue = _find_issue(
            ctx.issues_by_cv,
            ctx.issues_by_series_number,
            comicvine_issue_id=str(cv_issue) if cv_issue else None,
            series_id=_resolve_series_id_for_issue(ctx, candidate),
            payload=candidate.get("payload") or {},
        )
        if existing_issue is not None:
            ident = sa_inspect(existing_issue).identity
            if ident and ident[0] is not None:
                return int(ident[0])
    return None


def _process_image_record(ctx: _ImportContext, session: Session, record: dict[str, Any], *, dry_run: bool) -> None:
    payload = record.get("payload") or {}
    issue_id = _resolve_issue_id_for_image(ctx, record)
    if issue_id is None:
        ctx.stats.skipped += 1
        return
    source_url = payload.get("source_url")
    external_image_id = payload.get("external_image_id")
    existing = None
    if source_url and issue_id:
        existing = ctx.images_by_issue_url.get((int(issue_id), str(source_url)))
        if existing is None:
            existing = session.exec(
                select(CatalogImage)
                .where(CatalogImage.issue_id == issue_id)
                .where(CatalogImage.source_url == source_url)
            ).first()
            if existing is not None and source_url:
                ctx.images_by_issue_url[(int(issue_id), str(source_url))] = existing
    if dry_run:
        if existing is None:
            ctx.stats.images_created += 1
        else:
            ctx.stats.images_updated += 1
        return
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
        ctx.stats.images_created += 1
    else:
        ctx.stats.images_updated += 1
    if source_url:
        refreshed = session.exec(
            select(CatalogImage)
            .where(CatalogImage.issue_id == issue_id)
            .where(CatalogImage.source_url == source_url)
        ).first()
        if refreshed is not None:
            ctx.images_by_issue_url[(int(issue_id), str(source_url))] = refreshed


def _phase_rows(ctx: _ImportContext, phase: PhaseName) -> list[dict[str, Any]]:
    if phase == "publishers":
        return ctx.publishers
    if phase == "series":
        return ctx.series_rows
    if phase == "issues":
        return ctx.issue_rows
    return ctx.image_rows


def _process_record(
    ctx: _ImportContext,
    session: Session,
    phase: PhaseName,
    record: dict[str, Any],
    *,
    dry_run: bool,
) -> None:
    if phase == "publishers":
        _process_publisher_record(ctx, session, record, dry_run=dry_run)
    elif phase == "series":
        _process_series_record(ctx, session, record, dry_run=dry_run)
    elif phase == "issues":
        _process_issue_record(ctx, session, record, dry_run=dry_run)
    else:
        _process_image_record(ctx, session, record, dry_run=dry_run)


def run_batched_catalog_import(
    session: Session,
    *,
    input_path: Path,
    database_target: str,
    dry_run: bool = False,
    verbose: bool = False,
    batch_sizes: dict[PhaseName, int] | None = None,
    start_phase: PhaseName | None = None,
    resume: bool = False,
    state_path: Path | None = None,
    emit: Callable[[str], None] | None = None,
) -> BatchedImportState:
    log = emit or (lambda message: print(f"[p101-batched-import] {message}", flush=True))
    state_file = state_path or default_state_path()
    sizes = dict(DEFAULT_BATCH_SIZES)
    if batch_sizes:
        sizes.update(batch_sizes)

    if not input_path.is_file():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    input_fingerprint = fingerprint_input(input_path)
    prior = load_state(state_file) if resume else None
    if resume and prior is None:
        raise FileNotFoundError(f"Resume requested but state file missing: {state_file}")

    load_started = time.perf_counter()
    records = _load_snapshot_records(input_path)
    log(f"Loaded snapshot {len(records)} lines in {time.perf_counter() - load_started:.2f}s")

    if prior is not None:
        if prior.input_fingerprint != input_fingerprint:
            raise ValueError("Resume state input fingerprint does not match --input file")
        if prior.database_target != database_target:
            raise ValueError("Resume state database_target does not match current --database-url")
        state = prior
        state.dry_run = dry_run
        state.batch_sizes = {k: int(sizes[k]) for k in PHASE_ORDER}
    else:
        state = BatchedImportState(
            job_id=input_fingerprint[:16],
            input_path=str(input_path),
            input_fingerprint=input_fingerprint,
            database_target=database_target,
            dry_run=dry_run,
            phase="publishers",
            offsets={p: 0 for p in PHASE_ORDER},
            completed_phases=[],
            stats={},
            batch_sizes={k: int(sizes[k]) for k in PHASE_ORDER},
            started_at=_utc_now_iso(),
            updated_at=_utc_now_iso(),
        )

    if start_phase is not None:
        state.phase = start_phase
        for phase in PHASE_ORDER:
            if phase == start_phase:
                break
            if phase not in state.completed_phases:
                state.completed_phases.append(phase)

    progress = _ImportProgress(
        verbose=verbose,
        emit=lambda message: log(message.replace("[p97-catalog-import]", "[p101-batched-import]")),
    )

    rebuild_through: dict[PhaseName, int] = {
        "publishers": state.offsets["publishers"],
        "series": state.offsets["series"],
        "issues": state.offsets["issues"],
    }
    _, _, issue_rows_for_skip, _ = _partition_records(records)
    skip_prepare_issue_rebuild = (
        start_phase == "images"
        and "issues" in state.completed_phases
        and int(state.offsets.get("issues", 0)) >= len(issue_rows_for_skip)
    )
    ctx = _prepare_context(
        session,
        records,
        progress=progress,
        rebuild_maps_through=rebuild_through,
        skip_issue_id_rebuild=skip_prepare_issue_rebuild,
    )

    start_index = PHASE_ORDER.index(state.phase)
    for phase in PHASE_ORDER[start_index:]:
        if phase in state.completed_phases and state.offsets[phase] >= len(_phase_rows(ctx, phase)):
            continue
        state.phase = phase
        rows = _phase_rows(ctx, phase)
        total = len(rows)
        offset = int(state.offsets.get(phase, 0))
        batch_size = int(state.batch_sizes.get(phase) or DEFAULT_BATCH_SIZES[phase])
        log(f"Phase {phase} starting offset={offset} total={total} batch_size={batch_size} dry_run={dry_run}")

        if phase == "images":
            map_started = time.perf_counter()
            log(
                "issue id map build start "
                f"through_offset={int(state.offsets['issues'])} "
                f"snapshot_issue_rows={len(ctx.issue_rows)}"
            )
            issue_id_by_cv, issue_id_by_series_number = build_issue_id_lookup_maps(session, progress)
            ctx.issue_id_by_cv = issue_id_by_cv
            ctx.issue_id_by_series_number = issue_id_by_series_number
            resolved_count = _rebuild_snapshot_issue_id(
                ctx,
                through_offset=int(state.offsets["issues"]),
                issue_id_by_cv=issue_id_by_cv,
                issue_id_by_series_number=issue_id_by_series_number,
            )
            map_elapsed = time.perf_counter() - map_started
            log(
                "issue id map build end "
                f"resolved={resolved_count} snapshot_keys={len(ctx.snapshot_issue_id)} "
                f"elapsed_s={map_elapsed:.2f}"
            )
            resolved_issue_ids = {int(i) for i in ctx.snapshot_issue_id.values() if i}
            ctx.images_by_issue_url = _build_image_index(session, progress, resolved_issue_ids)

        batch_no = 0
        while offset < total:
            batch_no += 1
            if phase == "images" and batch_no == 1:
                log(
                    f"first image batch starting batch={batch_no} "
                    f"size={min(batch_size, total - offset)} offset={offset}/{total}"
                )
            batch = rows[offset : offset + batch_size]
            batch_stats = CatalogSnapshotImportStats(dry_run=dry_run)
            batch_started = time.perf_counter()
            for record in batch:
                before = _stats_to_dict(ctx.stats)
                _process_record(ctx, session, phase, record, dry_run=dry_run)
                after = _stats_to_dict(ctx.stats)
                for key, value in after.items():
                    delta = value - before.get(key, 0)
                    if delta:
                        setattr(batch_stats, key, getattr(batch_stats, key) + delta)

            offset += len(batch)
            state.offsets[phase] = offset
            if not dry_run:
                session.commit()
                session.expire_all()
            _merge_stats(state, batch_stats)
            counts = catalog_table_counts(session)
            elapsed = time.perf_counter() - batch_started
            log(
                f"batch phase={phase} batch={batch_no} processed={len(batch)} "
                f"offset={offset}/{total} elapsed_s={elapsed:.1f} "
                f"batch_stats={_stats_to_dict(batch_stats)} table_counts={counts}"
            )
            save_state(state_file, state)

        if phase not in state.completed_phases:
            state.completed_phases.append(phase)
        save_state(state_file, state)
        verify_phase(session, phase, emit=log)

    log(f"Import finished cumulative_stats={state.stats}")
    save_state(state_file, state)
    return state
