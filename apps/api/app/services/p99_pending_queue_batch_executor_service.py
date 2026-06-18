"""P99-03 — Execute approved pending queue drain batches (dry-run default)."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.catalog_p97 import ComicVineVolumeUniverse, P97VolumeIssueImportQueue
from app.models.universe import UNIVERSE_ISSUE_STATUS_DISCOVERED, UniverseIssue, UniverseVolume
from app.services.comicvine_catalog_importer import ComicVineCatalogImporter
from app.services.p97_comicvine_rate_budget import (
    DEFAULT_MIN_SECONDS_BETWEEN_REQUESTS,
    ComicVineRateBudget,
)
from app.services.p97_comicvine_universe_analytics_service import (
    build_catalog_coverage_indexes,
    existing_issue_count_for_volume,
)
from app.services.p97_volume_issue_import_queue_service import STATUS_PENDING
from app.services.p97_volume_issue_queue_import_service import (
    STATUS_COMPLETE,
    STATUS_FAILED,
    VolumeQueueImportItemResult,
    import_one_queue_volume,
    is_transient_stop_error,
)
from app.services.p99_pending_queue_drain_service import (
    GROUP_1_MAJOR_CORE,
    GROUP_2_LEGACY_US,
    classify_drain_group,
    default_batches_path,
    default_top_volumes_path,
)

PROGRESS_REL = Path("data/p99/pending_queue_batch_progress.json")
CORE_DRAIN_PROGRESS_REL = Path("data/p99/core_queue_drain_progress.json")

BATCH_META_ID: dict[str, str] = {
    "1": "batch_1",
    "2": "batch_2",
    "3": "batch_3",
    "group1": "batch_4",
    "group2": "batch_5",
}

BATCH_SLICE: dict[str, int | None] = {
    "1": 25,
    "2": 100,
    "3": 250,
    "group1": None,
    "group2": None,
}

APPLY_ALLOWED_BATCH_KEYS: frozenset[str] = frozenset({"1", "group1"})


def _api_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_core_drain_progress_path() -> Path:
    return _api_root() / CORE_DRAIN_PROGRESS_REL


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_batch_key(raw: str) -> str:
    key = str(raw or "").strip().lower()
    if key in BATCH_META_ID:
        return key
    if key.startswith("batch"):
        num = key.replace("batch", "").strip("_")
        if num in BATCH_META_ID:
            return num
    raise ValueError(f"Unknown batch {raw!r} (use 1, 2, 3, group1, group2)")


def load_top_pending_volumes(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or default_top_volumes_path()
    if not p.is_file():
        raise FileNotFoundError(f"Missing top pending queue volumes file: {p}")
    data = json.loads(p.read_text(encoding="utf-8-sig"))
    if not isinstance(data, list):
        raise ValueError(f"Invalid top volumes JSON: {p}")
    return list(data)


def load_batch_metadata(path: Path | None = None) -> dict[str, dict[str, Any]]:
    p = path or default_batches_path()
    if not p.is_file():
        raise FileNotFoundError(f"Missing pending queue batches file: {p}")
    data = json.loads(p.read_text(encoding="utf-8-sig"))
    if not isinstance(data, list):
        raise ValueError(f"Invalid batches JSON: {p}")
    return {str(row["batch_id"]): row for row in data if isinstance(row, dict)}


def default_progress_path() -> Path:
    return _api_root() / PROGRESS_REL


def _group1_pending_volume_ids(session: Session) -> list[int]:
    pending = session.exec(
        select(P97VolumeIssueImportQueue).where(P97VolumeIssueImportQueue.status == STATUS_PENDING)
    ).all()
    return [
        int(row.comicvine_volume_id)
        for row in pending
        if classify_drain_group(row.publisher, row.name) == GROUP_1_MAJOR_CORE
    ]


def _discovered_shells_for_cv_ids(session: Session, cv_ids: list[int]) -> int:
    if not cv_ids:
        return 0
    return int(
        session.exec(
            select(func.count())
            .select_from(UniverseIssue)
            .join(UniverseVolume, UniverseIssue.volume_id == UniverseVolume.id)
            .where(
                UniverseIssue.status == UNIVERSE_ISSUE_STATUS_DISCOVERED,
                UniverseVolume.comicvine_volume_id.in_(cv_ids),
            )
        ).one()
    )


def _catalog_series_issue_count(session: Session) -> int:
    indexes = build_catalog_coverage_indexes(session)
    total = 0
    for cv in session.exec(select(ComicVineVolumeUniverse)).all():
        total += existing_issue_count_for_volume(
            volume_id=int(cv.volume_id),
            name=cv.name,
            publisher=cv.publisher,
            indexes=indexes,
        )
    return int(total)


@dataclass
class SkippedQueueRow:
    comicvine_volume_id: int
    volume: str
    publisher: str | None
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "comicvine_volume_id": self.comicvine_volume_id,
            "volume": self.volume,
            "publisher": self.publisher,
            "reason": self.reason,
        }


@dataclass
class BatchVolumePlan:
    batch_key: str
    batch_id: str
    label: str
    volumes_selected: int
    estimated_shell_gap: int
    estimated_catalog_gain: int
    volume_rows: list[dict[str, Any]]
    first_volume: dict[str, Any] | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "batch_key": self.batch_key,
            "batch_id": self.batch_id,
            "label": self.label,
            "volumes_selected": self.volumes_selected,
            "estimated_shell_gap": self.estimated_shell_gap,
            "estimated_catalog_gain": self.estimated_catalog_gain,
            "first_volume": self.first_volume,
            "volume_rows": self.volume_rows,
        }


def build_batch_volume_plan(
    session: Session,
    batch_key: str,
    *,
    top_volumes_path: Path | None = None,
    batches_path: Path | None = None,
    max_volumes: int | None = None,
) -> BatchVolumePlan:
    key = normalize_batch_key(batch_key)
    top_rows = load_top_pending_volumes(top_volumes_path)
    meta_by_id = load_batch_metadata(batches_path)
    batch_id = BATCH_META_ID[key]
    meta = meta_by_id.get(batch_id, {})

    rank_by_cv = {int(r["comicvine_volume_id"]): int(r["rank"]) for r in top_rows}

    if key in ("1", "2", "3"):
        limit = int(BATCH_SLICE[key] or 25)
        selected = top_rows[:limit]
    elif key == "group1":
        target_group = GROUP_1_MAJOR_CORE
        selected = _pending_rows_for_group(session, target_group, rank_by_cv)
    else:
        selected = _pending_rows_for_group(session, GROUP_2_LEGACY_US, rank_by_cv)

    if max_volumes is not None and int(max_volumes) > 0:
        selected = selected[: int(max_volumes)]

    first = selected[0] if selected else None
    return BatchVolumePlan(
        batch_key=key,
        batch_id=batch_id,
        label=str(meta.get("label") or batch_id),
        volumes_selected=len(selected),
        estimated_shell_gap=int(meta.get("shells_affected") or sum(int(r.get("shell_gap") or 0) for r in selected)),
        estimated_catalog_gain=int(
            meta.get("expected_catalog_gain") or sum(int(r.get("estimated_import_value") or 0) for r in selected)
        ),
        volume_rows=selected,
        first_volume=first,
    )


def _pending_rows_for_group(
    session: Session,
    group: str,
    rank_by_cv: dict[int, int],
) -> list[dict[str, Any]]:
    pending = list(
        session.exec(
            select(P97VolumeIssueImportQueue).where(P97VolumeIssueImportQueue.status == STATUS_PENDING)
        ).all()
    )
    rows: list[dict[str, Any]] = []
    for row in pending:
        if classify_drain_group(row.publisher, row.name) != group:
            continue
        cv_id = int(row.comicvine_volume_id)
        rows.append(
            {
                "rank": rank_by_cv.get(cv_id, 999_999),
                "comicvine_volume_id": cv_id,
                "volume": row.name,
                "publisher": row.publisher,
                "shell_gap": int(row.missing_issue_count or 0),
                "estimated_import_value": int(row.missing_issue_count or 0),
            }
        )
    rows.sort(key=lambda r: (int(r["rank"]), -int(r.get("shell_gap") or 0)))
    return rows


def resolve_queue_rows_for_plan(
    session: Session,
    plan: BatchVolumePlan,
) -> tuple[list[P97VolumeIssueImportQueue], list[SkippedQueueRow]]:
    ready: list[P97VolumeIssueImportQueue] = []
    skipped: list[SkippedQueueRow] = []
    for vol in plan.volume_rows:
        cv_id = int(vol["comicvine_volume_id"])
        row = session.exec(
            select(P97VolumeIssueImportQueue).where(P97VolumeIssueImportQueue.comicvine_volume_id == cv_id)
        ).first()
        if row is None:
            skipped.append(
                SkippedQueueRow(
                    comicvine_volume_id=cv_id,
                    volume=str(vol.get("volume") or ""),
                    publisher=vol.get("publisher"),
                    reason="missing_queue_row",
                )
            )
            continue
        status = (row.status or "").lower()
        if status != STATUS_PENDING:
            skipped.append(
                SkippedQueueRow(
                    comicvine_volume_id=cv_id,
                    volume=row.name,
                    publisher=row.publisher,
                    reason=f"status_{status}",
                )
            )
            continue
        ready.append(row)
    return ready, skipped


@dataclass
class BatchExecutionResult:
    dry_run: bool
    batch_key: str
    batch_id: str
    plan: BatchVolumePlan
    volumes_selected: int
    volumes_processed: int
    volumes_completed: int
    volumes_failed: int
    volumes_skipped: int
    skipped_rows: list[SkippedQueueRow]
    items: list[VolumeQueueImportItemResult] = field(default_factory=list)
    catalog_count_before: int = 0
    catalog_count_after: int = 0
    catalog_gain: int = 0
    group1_volumes_remaining: int | None = None
    group1_pending_shell_reduction: int | None = None
    stopped_reason: str | None = None
    start_time: str | None = None
    end_time: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "batch_key": self.batch_key,
            "batch_id": self.batch_id,
            "plan": self.plan.as_dict(),
            "volumes_selected": self.volumes_selected,
            "volumes_processed": self.volumes_processed,
            "volumes_completed": self.volumes_completed,
            "volumes_failed": self.volumes_failed,
            "volumes_skipped": self.volumes_skipped,
            "skipped_rows": [s.as_dict() for s in self.skipped_rows],
            "catalog_count_before": self.catalog_count_before,
            "catalog_count_after": self.catalog_count_after,
            "catalog_gain": self.catalog_gain,
            "group1_volumes_remaining": self.group1_volumes_remaining,
            "group1_pending_shell_reduction": self.group1_pending_shell_reduction,
            "stopped_reason": self.stopped_reason,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "items": [
                {
                    "volume_id": i.volume_id,
                    "name": i.name,
                    "created_issues": i.created_issues,
                    "updated_issues": i.updated_issues,
                    "queue_status": i.queue_status,
                    "failures": i.failures,
                }
                for i in self.items
            ],
        }


def execute_pending_queue_batch(
    session: Session,
    budget: ComicVineRateBudget,
    importer: ComicVineCatalogImporter,
    plan: BatchVolumePlan,
    *,
    dry_run: bool = True,
    inter_volume_delay_seconds: float = DEFAULT_MIN_SECONDS_BETWEEN_REQUESTS,
    issues_limit: int | None = None,
    stop_on_throttle: bool = True,
    sleep_fn: Callable[[float], None] = time.sleep,
    verbose: bool = False,
) -> BatchExecutionResult:
    start = _utc_now_iso()
    catalog_before = _catalog_series_issue_count(session)
    queue_rows, skipped = resolve_queue_rows_for_plan(session, plan)

    track_group1 = plan.batch_key == "group1"
    group1_cv_before = _group1_pending_volume_ids(session) if track_group1 else []
    discovered_before = (
        _discovered_shells_for_cv_ids(session, group1_cv_before) if track_group1 else 0
    )

    result = BatchExecutionResult(
        dry_run=dry_run,
        batch_key=plan.batch_key,
        batch_id=plan.batch_id,
        plan=plan,
        volumes_selected=len(plan.volume_rows),
        volumes_processed=0,
        volumes_completed=0,
        volumes_failed=0,
        volumes_skipped=len(skipped),
        skipped_rows=skipped,
        catalog_count_before=catalog_before,
        start_time=start,
    )

    if dry_run:
        result.volumes_processed = len(queue_rows)
        if track_group1:
            result.group1_volumes_remaining = len(_group1_pending_volume_ids(session))
        result.end_time = _utc_now_iso()
        return result

    for idx, row in enumerate(queue_rows):
        item = import_one_queue_volume(
            session,
            budget,
            importer,
            row,
            issues_limit=issues_limit,
            dry_run=dry_run,
            sleep_fn=sleep_fn,
            verbose=verbose,
        )
        result.items.append(item)
        result.volumes_processed += 1
        if item.queue_status == STATUS_COMPLETE:
            result.volumes_completed += 1
        elif item.queue_status == STATUS_FAILED:
            result.volumes_failed += 1

        if item.throttled or is_transient_stop_error(failures=item.failures):
            result.stopped_reason = "throttle" if item.throttled else "connection_reset"
            if stop_on_throttle:
                break

        if idx + 1 < len(queue_rows) and inter_volume_delay_seconds > 0:
            sleep_fn(float(inter_volume_delay_seconds))

    result.catalog_count_after = _catalog_series_issue_count(session)
    result.catalog_gain = max(result.catalog_count_after - catalog_before, 0)
    if track_group1:
        group1_cv_after = _group1_pending_volume_ids(session)
        discovered_after = _discovered_shells_for_cv_ids(session, group1_cv_after)
        result.group1_volumes_remaining = len(group1_cv_after)
        result.group1_pending_shell_reduction = max(discovered_before - discovered_after, 0)
    result.end_time = _utc_now_iso()
    return result


def _load_core_progress(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_core_queue_drain_progress(
    result: BatchExecutionResult,
    *,
    max_volumes: int | None = None,
    path: Path | None = None,
) -> Path | None:
    if result.batch_key != "group1":
        return None
    out = path or default_core_drain_progress_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    prev = _load_core_progress(out)
    cumulative_processed = int(prev.get("volumes_processed_cumulative") or 0)
    cumulative_gain = int(prev.get("catalog_gain_cumulative") or 0)
    cumulative_pending_reduction = int(prev.get("pending_reduction_cumulative") or 0)
    cumulative_failures = int(prev.get("failures_cumulative") or 0)
    if not result.dry_run:
        cumulative_processed += result.volumes_processed
        cumulative_gain += result.catalog_gain
        cumulative_pending_reduction += int(result.group1_pending_shell_reduction or 0)
        cumulative_failures += result.volumes_failed

    payload = {
        "updated_at": _utc_now_iso(),
        "batch_key": result.batch_key,
        "dry_run": result.dry_run,
        "max_volumes": max_volumes,
        "last_run": {
            "start_time": result.start_time,
            "end_time": result.end_time,
            "volumes_processed": result.volumes_processed,
            "volumes_failed": result.volumes_failed,
            "volumes_skipped": result.volumes_skipped,
            "catalog_gain": result.catalog_gain,
            "pending_reduction": result.group1_pending_shell_reduction,
            "volumes_remaining_group1": result.group1_volumes_remaining,
            "stopped_reason": result.stopped_reason,
        },
        "volumes_processed_cumulative": cumulative_processed,
        "volumes_remaining_group1": result.group1_volumes_remaining,
        "catalog_gain_cumulative": cumulative_gain,
        "pending_reduction_cumulative": cumulative_pending_reduction,
        "failures_cumulative": cumulative_failures,
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def save_batch_progress(result: BatchExecutionResult, *, path: Path | None = None) -> Path:
    out = path or default_progress_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": _utc_now_iso(),
        "batch_id": result.batch_id,
        "batch_key": result.batch_key,
        "start_time": result.start_time,
        "end_time": result.end_time,
        "dry_run": result.dry_run,
        "volumes_selected": result.volumes_selected,
        "volumes_processed": result.volumes_processed,
        "volumes_completed": result.volumes_completed,
        "volumes_failed": result.volumes_failed,
        "volumes_skipped": result.volumes_skipped,
        "catalog_count_before": result.catalog_count_before,
        "catalog_count_after": result.catalog_count_after,
        "catalog_gain": result.catalog_gain,
        "stopped_reason": result.stopped_reason,
        "skipped_rows": [s.as_dict() for s in result.skipped_rows],
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def assert_apply_allowed(batch_key: str, *, apply: bool) -> None:
    key = normalize_batch_key(batch_key)
    if apply and key not in APPLY_ALLOWED_BATCH_KEYS:
        raise ValueError(
            f"Apply mode is not enabled for batch {key!r}. "
            f"Allowed apply batches: {', '.join(sorted(APPLY_ALLOWED_BATCH_KEYS))}."
        )
