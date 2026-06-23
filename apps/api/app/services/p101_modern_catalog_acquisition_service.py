"""P101 Modern Catalog Acquisition — gap volumes, queue preview/build, runbook plans."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from sqlmodel import Session, func, select

from app.models.catalog_p97 import ComicVineVolumeUniverse, P97VolumeIssueImportQueue
from app.services.p101_modern_catalog_audit_service import (
    P101_YEAR_MAX,
    P101_YEAR_MIN,
    canonical_focus_publisher_label,
)
from app.services.p97_comicvine_universe_analytics_service import (
    build_catalog_coverage_indexes,
    existing_issue_count_for_volume,
    volume_coverage_percent,
)
from app.services.p97_volume_issue_import_queue_service import (
    STATUS_PENDING,
    STATUS_RUNNING,
    STATUS_FAILED,
    build_volume_issue_import_queue,
)

P101_FOCUS_PUBLISHER_LABELS: tuple[str, ...] = (
    "Marvel",
    "DC",
    "Image",
    "Dark Horse",
    "IDW",
    "Boom",
    "Dynamite",
    "Valiant",
)

P101_BULK_CV_PUBLISHERS: tuple[str, ...] = (
    "Marvel",
    "DC Comics",
    "Image",
    "Dark Horse Comics",
    "IDW Publishing",
    "BOOM! Studios",
    "Dynamite Entertainment",
    "Valiant Entertainment",
)


@dataclass(frozen=True)
class ModernGapVolume:
    comicvine_volume_id: int
    name: str
    publisher: str
    publisher_label: str
    start_year: int | None
    count_of_issues: int
    existing_issue_count: int
    missing_issue_count: int
    coverage_percent: float


@dataclass
class P101QueuePreview:
    mode: Literal["dry_run"] = "dry_run"
    universe_volumes_total: int = 0
    modern_focus_volumes: int = 0
    gap_volumes: int = 0
    missing_issues: int = 0
    by_publisher: dict[str, dict[str, int]] = field(default_factory=dict)
    top_gap_volumes: list[ModernGapVolume] = field(default_factory=list)


@dataclass
class P101QueueBuildResult:
    dry_run: bool
    preview: P101QueuePreview
    build_inserted: int = 0
    build_updated: int = 0
    pending_queue_size: int = 0
    p101_pending_volumes: int = 0
    p101_pending_missing_issues: int = 0


@dataclass
class P101RunbookPlan:
    generated_at: str
    year_min: int
    year_max: int
    focus_publishers: tuple[str, ...]
    prerequisites: tuple[str, ...]
    phases: tuple[dict[str, Any], ...]
    powershell_commands: tuple[str, ...]


def _modern_volume_start_year(universe: ComicVineVolumeUniverse) -> int | None:
    if universe.start_year is None:
        return None
    try:
        return int(universe.start_year)
    except (TypeError, ValueError):
        return None


def is_p101_modern_universe_volume(universe: ComicVineVolumeUniverse) -> bool:
    label = canonical_focus_publisher_label(universe.publisher)
    if label is None:
        return False
    start_year = _modern_volume_start_year(universe)
    if start_year is None:
        return False
    return P101_YEAR_MIN <= start_year <= P101_YEAR_MAX


def list_modern_gap_volumes(session: Session, *, limit: int | None = None) -> list[ModernGapVolume]:
    indexes = build_catalog_coverage_indexes(session)
    rows: list[ModernGapVolume] = []
    for universe in session.exec(select(ComicVineVolumeUniverse)).all():
        if not is_p101_modern_universe_volume(universe):
            continue
        count_of_issues = int(universe.count_of_issues or 0)
        if count_of_issues <= 0:
            continue
        existing = existing_issue_count_for_volume(
            volume_id=int(universe.volume_id),
            name=universe.name,
            publisher=universe.publisher,
            indexes=indexes,
        )
        missing = max(count_of_issues - existing, 0)
        if missing <= 0:
            continue
        label = canonical_focus_publisher_label(universe.publisher) or "Unknown"
        rows.append(
            ModernGapVolume(
                comicvine_volume_id=int(universe.volume_id),
                name=universe.name,
                publisher=(universe.publisher or "").strip() or "Unknown",
                publisher_label=label,
                start_year=_modern_volume_start_year(universe),
                count_of_issues=count_of_issues,
                existing_issue_count=existing,
                missing_issue_count=missing,
                coverage_percent=volume_coverage_percent(
                    count_of_issues=count_of_issues,
                    existing_issue_count=existing,
                ),
            )
        )
    rows.sort(key=lambda row: (-row.missing_issue_count, row.comicvine_volume_id))
    if limit is not None:
        return rows[: max(0, int(limit))]
    return rows


def preview_p101_queue(session: Session, *, top: int = 50) -> P101QueuePreview:
    preview = P101QueuePreview()
    preview.universe_volumes_total = int(
        session.exec(select(func.count()).select_from(ComicVineVolumeUniverse)).one()
    )
    gap_all = list_modern_gap_volumes(session)
    preview.gap_volumes = len(gap_all)
    preview.missing_issues = sum(row.missing_issue_count for row in gap_all)
    preview.top_gap_volumes = gap_all[: max(1, int(top))]

    modern_focus = 0
    by_pub: dict[str, dict[str, int]] = {}
    for universe in session.exec(select(ComicVineVolumeUniverse)).all():
        if not is_p101_modern_universe_volume(universe):
            continue
        modern_focus += 1
    preview.modern_focus_volumes = modern_focus

    for row in gap_all:
        bucket = by_pub.setdefault(
            row.publisher_label,
            {"gap_volumes": 0, "missing_issues": 0},
        )
        bucket["gap_volumes"] += 1
        bucket["missing_issues"] += row.missing_issue_count
    preview.by_publisher = dict(sorted(by_pub.items(), key=lambda item: (-item[1]["missing_issues"], item[0])))
    return preview


def _p101_pending_queue_stats(session: Session) -> tuple[int, int]:
    """Pending/running/failed queue rows that match P101 modern focus filter."""
    volume_ids = {
        int(u.volume_id)
        for u in session.exec(select(ComicVineVolumeUniverse)).all()
        if is_p101_modern_universe_volume(u)
    }
    if not volume_ids:
        return 0, 0
    rows = session.exec(
        select(P97VolumeIssueImportQueue).where(
            P97VolumeIssueImportQueue.status.in_((STATUS_PENDING, STATUS_RUNNING, STATUS_FAILED))
        )
    ).all()
    volumes = 0
    missing = 0
    for row in rows:
        if int(row.comicvine_volume_id) not in volume_ids:
            continue
        volumes += 1
        missing += int(row.missing_issue_count or 0)
    return volumes, missing


def build_p101_queue(
    session: Session,
    *,
    dry_run: bool = True,
    refresh_complete: bool = False,
    preview_top: int = 50,
) -> P101QueueBuildResult:
    preview = preview_p101_queue(session, top=preview_top)
    result = P101QueueBuildResult(dry_run=dry_run, preview=preview)
    if dry_run:
        p101_vol, p101_miss = _p101_pending_queue_stats(session)
        result.p101_pending_volumes = p101_vol
        result.p101_pending_missing_issues = p101_miss
        result.pending_queue_size = int(
            session.exec(
                select(func.count())
                .select_from(P97VolumeIssueImportQueue)
                .where(P97VolumeIssueImportQueue.status == STATUS_PENDING)
            ).one()
        )
        return result

    build = build_volume_issue_import_queue(session, refresh_complete=refresh_complete)
    result.build_inserted = build.queue_rows_inserted
    result.build_updated = build.queue_rows_updated
    result.pending_queue_size = build.pending_queue_size
    p101_vol, p101_miss = _p101_pending_queue_stats(session)
    result.p101_pending_volumes = p101_vol
    result.p101_pending_missing_issues = p101_miss
    return result


def build_p101_runbook_plan(*, api_root: str | None = None) -> P101RunbookPlan:
    api = (api_root or r"C:\comic-os-p41-feed\apps\api").rstrip("\\/")
    ps: list[str] = [
        f"Set-Location {api}",
        "# Real URL required (or leave unset to use apps/api/.env):",
        '# $env:DATABASE_URL = "postgresql+pg8000://USER:PASS@HOST/dbname"',
        '$db = $env:DATABASE_URL  # optional if .env has DATABASE_URL',
        "",
        "# --- Phase 0: Audit (read-only) ---",
        "python scripts/p101_modern_catalog_audit.py --database-url $db",
        "",
        "# --- Phase 1: Universe metadata (skip if universe_volumes_total > 0 in audit) ---",
        "python scripts/p97_discover_comicvine_universe.py --database-url $db --pages 20",
        "# Long run: python scripts/p97_discover_comicvine_universe.py --database-url $db --until-complete",
        "",
        "# --- Phase 2: Queue preview (dry-run) ---",
        "python scripts/p101_modern_catalog_runbook.py --database-url $db queue-preview",
        "",
        "# --- Phase 3: Build P97 issue import queue (writes DB) ---",
        "python scripts/p97_build_volume_issue_import_queue.py --database-url $db",
        "python scripts/p101_modern_catalog_runbook.py --database-url $db queue-preview",
        "",
        "# --- Phase 4: Bulk modern volumes by publisher (optional; uses DATABASE_URL / .env) ---",
        "# Dry-run one publisher first:",
        'python scripts/p97_import_comicvine_catalog.py --publisher "Marvel" '
        f"--min-start-year {P101_YEAR_MIN} --import-issues --limit 20 --dry-run",
        "# Live resume loop (one publisher at a time):",
        'python scripts/p97_import_comicvine_catalog.py --publisher "Marvel" '
        f'--min-start-year {P101_YEAR_MIN} --strict-publisher --import-issues --resume --limit 100 --sleep-seconds 1',
        "",
        "# --- Phase 5: Import from queue — DRY-RUN first ---",
        "python scripts/p97_import_volume_issue_queue.py --database-url $db --dry-run --limit-volumes 5",
        "",
        "# --- Phase 6: Import from queue — LIVE (bounded batches) ---",
        "python scripts/p97_import_volume_issue_queue.py --database-url $db --limit-volumes 10 --max-api-requests 180",
        "# Repeat Phase 6 until pending queue for P101 gap is near zero.",
        "",
        "# --- Phase 7: Cover harvest (catalog_image only; not inventory) ---",
        "python scripts/p97_harvest_catalog_covers.py --database-url $db --resume --loop --limit 500 --source COMICVINE",
        "",
        "# --- Phase 8: Re-audit ---",
        "python scripts/p101_modern_catalog_audit.py --database-url $db --json",
        "python scripts/p97_catalog_health.py --database-url $db",
    ]

    phases = (
        {
            "id": "audit",
            "title": "Baseline coverage audit",
            "dry_run": True,
            "script": "p101_modern_catalog_audit.py",
        },
        {
            "id": "discover_universe",
            "title": "ComicVine volume universe discovery",
            "dry_run": False,
            "script": "p97_discover_comicvine_universe.py",
            "skip_when": "comicvine_volume_universe row count > 0",
        },
        {
            "id": "queue_preview",
            "title": "P101 gap + queue preview",
            "dry_run": True,
            "script": "p101_modern_catalog_runbook.py queue-preview",
        },
        {
            "id": "queue_build",
            "title": "Build p97_volume_issue_import_queue from universe",
            "dry_run": False,
            "script": "p97_build_volume_issue_import_queue.py",
        },
        {
            "id": "bulk_publisher_import",
            "title": "Optional per-publisher CV bulk (--min-start-year)",
            "dry_run_first": True,
            "script": "p97_import_comicvine_catalog.py",
        },
        {
            "id": "queue_import_dry_run",
            "title": "Queue issue import dry-run",
            "dry_run": True,
            "script": "p97_import_volume_issue_queue.py --dry-run",
        },
        {
            "id": "queue_import_live",
            "title": "Queue issue import live batches",
            "dry_run": False,
            "script": "p97_import_volume_issue_queue.py",
        },
        {
            "id": "cover_harvest",
            "title": "Harvest pending catalog covers",
            "dry_run": False,
            "script": "p97_harvest_catalog_covers.py",
        },
        {
            "id": "re_audit",
            "title": "Measure 2009–2026 growth",
            "dry_run": True,
            "script": "p101_modern_catalog_audit.py",
        },
    )

    return P101RunbookPlan(
        generated_at=datetime.now(timezone.utc).isoformat(),
        year_min=P101_YEAR_MIN,
        year_max=P101_YEAR_MAX,
        focus_publishers=P101_FOCUS_PUBLISHER_LABELS,
        prerequisites=(
            "COMICVINE_API_KEY in apps/api/.env or environment",
            "DATABASE_URL pointing at production catalog DB",
            "Does not modify user inventory tables",
        ),
        phases=phases,
        powershell_commands=tuple(ps),
    )


def runbook_plan_to_json(plan: P101RunbookPlan) -> dict[str, Any]:
    return {
        "generated_at": plan.generated_at,
        "year_min": plan.year_min,
        "year_max": plan.year_max,
        "focus_publishers": list(plan.focus_publishers),
        "prerequisites": list(plan.prerequisites),
        "phases": list(plan.phases),
        "powershell_commands": list(plan.powershell_commands),
    }
