"""P97 queue repair planning and apply (issue import queue only)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.models.catalog_p97 import ComicVineVolumeUniverse, P97VolumeIssueImportQueue
from app.services.p97_comicvine_universe_analytics_service import (
    build_catalog_coverage_indexes,
    existing_issue_count_for_volume,
    volume_coverage_percent,
)
from app.services.p97_core_run_registry import (
    expected_publisher_for_report_label,
    pick_best_universe_match,
    publisher_matches_expected,
    volume_title_matches_report_label,
)
from app.services.p97_discovered_not_queued_service import (
    ACTION_ADD_TO_P97_QUEUE,
    build_discovered_not_queued_audit,
)
from app.services.p97_targeted_core_discovery import find_universe_matches_for_label
from app.services.p97_volume_issue_queue_priority import TIER_0_MANUAL, compute_volume_import_priority
from app.services.p97_volume_issue_import_queue_service import STATUS_COMPLETE, STATUS_FAILED, STATUS_RUNNING

ACTION_REQUEUE_FAILED = "REQUEUE_FAILED"
ACTION_SKIP_COMPLETE = "SKIP_COMPLETE"
ACTION_SKIP_LOW_VALUE = "SKIP_LOW_VALUE"
ACTION_REVIEW_PUBLISHER_MISMATCH = "REVIEW_PUBLISHER_MISMATCH"

DEFAULT_PLAN_PATH = Path("data/p97/queue_repair_plan.json")


def _api_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_plan_path() -> Path:
    return _api_root() / DEFAULT_PLAN_PATH


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class QueueRepairPlanRow:
    comicvine_volume_id: int
    name: str
    publisher: str | None
    missing_issue_count: int
    recommended_action: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "comicvine_volume_id": self.comicvine_volume_id,
            "name": self.name,
            "publisher": self.publisher,
            "missing_issue_count": self.missing_issue_count,
            "recommended_action": self.recommended_action,
        }


@dataclass
class QueueRepairApplyResult:
    dry_run: bool
    considered: int = 0
    would_add: int = 0
    added: int = 0
    updated: int = 0
    skipped: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "considered": self.considered,
            "would_add": self.would_add,
            "added": self.added,
            "updated": self.updated,
            "skipped": self.skipped,
        }


def _publisher_mismatch_for_volume(session: Session, universe: ComicVineVolumeUniverse) -> bool:
    universes = list(session.exec(select(ComicVineVolumeUniverse)).all())
    for label in ("Flash", "Teenage Mutant Ninja Turtles", "Batman", "Amazing Spider-Man"):
        if not volume_title_matches_report_label(universe.name, label):
            continue
        expected = expected_publisher_for_report_label(label)
        if publisher_matches_expected(universe.publisher, expected):
            return False
        matches = find_universe_matches_for_label(universes, label)
        best, pub_ok = pick_best_universe_match(
            matches,
            label,
            name_getter=lambda u: u.name,
            publisher_getter=lambda u: u.publisher,
            issue_count_getter=lambda u: u.count_of_issues,
            start_year_getter=lambda u: u.start_year,
        )
        if best is not None and int(best.volume_id) == int(universe.volume_id) and not pub_ok:
            return True
    return False


def build_queue_repair_plan(session: Session) -> list[QueueRepairPlanRow]:
    audit_rows = build_discovered_not_queued_audit(session)
    queue_by_id = {
        int(r.comicvine_volume_id): r for r in session.exec(select(P97VolumeIssueImportQueue)).all()
    }
    plan: list[QueueRepairPlanRow] = []
    for row in audit_rows:
        action = row.recommended_action
        q = queue_by_id.get(row.comicvine_volume_id)
        if q is not None and (q.status or "").lower() == STATUS_FAILED:
            action = ACTION_REQUEUE_FAILED
        elif row.missing_issue_count <= 3 and not row.highlight_core:
            action = ACTION_SKIP_LOW_VALUE
        uni = session.exec(
            select(ComicVineVolumeUniverse).where(
                ComicVineVolumeUniverse.volume_id == row.comicvine_volume_id
            )
        ).first()
        if uni is not None and _publisher_mismatch_for_volume(session, uni):
            action = ACTION_REVIEW_PUBLISHER_MISMATCH
        elif row.missing_issue_count <= 0:
            action = ACTION_SKIP_COMPLETE
        plan.append(
            QueueRepairPlanRow(
                comicvine_volume_id=row.comicvine_volume_id,
                name=row.name,
                publisher=row.publisher,
                missing_issue_count=row.missing_issue_count,
                recommended_action=action,
            )
        )
    return plan


def save_queue_repair_plan(rows: list[QueueRepairPlanRow], path: Path | None = None) -> Path:
    out = path or default_plan_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps([r.as_dict() for r in rows], indent=2),
        encoding="utf-8",
    )
    return out


def load_queue_repair_plan(path: Path | None = None) -> list[QueueRepairPlanRow]:
    plan_path = path or default_plan_path()
    if not plan_path.is_file():
        return []
    data = json.loads(plan_path.read_text(encoding="utf-8-sig"))
    rows: list[QueueRepairPlanRow] = []
    for raw in data:
        rows.append(
            QueueRepairPlanRow(
                comicvine_volume_id=int(raw["comicvine_volume_id"]),
                name=str(raw.get("name") or ""),
                publisher=raw.get("publisher"),
                missing_issue_count=int(raw.get("missing_issue_count") or 0),
                recommended_action=str(raw.get("recommended_action") or ""),
            )
        )
    return rows


def _upsert_queue_from_universe(session: Session, universe: ComicVineVolumeUniverse, *, dry_run: bool) -> str:
    indexes = build_catalog_coverage_indexes(session)
    volume_id = int(universe.volume_id)
    count_of_issues = int(universe.count_of_issues or 0)
    existing = existing_issue_count_for_volume(
        volume_id=volume_id,
        name=universe.name,
        publisher=universe.publisher,
        indexes=indexes,
    )
    missing = max(count_of_issues - existing, 0)
    if missing <= 0:
        return "skipped"
    coverage = volume_coverage_percent(count_of_issues=count_of_issues, existing_issue_count=existing)
    priority = compute_volume_import_priority(
        missing_issue_count=missing,
        count_of_issues=count_of_issues,
        coverage_percent=coverage,
        publisher=universe.publisher,
        name=universe.name,
        start_year=universe.start_year,
    )
    row = session.exec(
        select(P97VolumeIssueImportQueue).where(P97VolumeIssueImportQueue.comicvine_volume_id == volume_id)
    ).first()
    if row is not None:
        if row.launch_priority_tier == TIER_0_MANUAL:
            return "skipped"
        if (row.status or "").lower() == STATUS_RUNNING:
            return "skipped"
        if dry_run:
            return "updated"
        row.name = universe.name
        row.publisher = universe.publisher
        row.count_of_issues = count_of_issues
        row.existing_issue_count = existing
        row.missing_issue_count = missing
        row.coverage_percent = coverage
        row.priority_score = priority.priority_score
        row.launch_priority_tier = priority.launch_priority_tier
        if (row.status or "").lower() in (STATUS_COMPLETE, STATUS_FAILED):
            row.status = "pending"
        row.updated_at = _utc_now()
        session.add(row)
        session.commit()
        return "updated"
    if dry_run:
        return "added"
    now = _utc_now()
    session.add(
        P97VolumeIssueImportQueue(
            comicvine_volume_id=volume_id,
            name=universe.name,
            publisher=universe.publisher,
            count_of_issues=count_of_issues,
            existing_issue_count=existing,
            missing_issue_count=missing,
            coverage_percent=coverage,
            priority_score=priority.priority_score,
            launch_priority_tier=priority.launch_priority_tier,
            status="pending",
            created_at=now,
            updated_at=now,
        )
    )
    session.commit()
    return "added"


def apply_queue_repair_plan(
    session: Session,
    plan: list[QueueRepairPlanRow],
    *,
    dry_run: bool = True,
    allow_requeue_failed: bool = False,
) -> QueueRepairApplyResult:
    result = QueueRepairApplyResult(dry_run=dry_run)
    for entry in plan:
        result.considered += 1
        if entry.recommended_action == ACTION_REQUEUE_FAILED and not allow_requeue_failed:
            result.skipped += 1
            continue
        if entry.recommended_action not in (ACTION_ADD_TO_P97_QUEUE, ACTION_REQUEUE_FAILED):
            result.skipped += 1
            continue
        universe = session.exec(
            select(ComicVineVolumeUniverse).where(
                ComicVineVolumeUniverse.volume_id == entry.comicvine_volume_id
            )
        ).first()
        if universe is None:
            result.skipped += 1
            continue
        outcome = _upsert_queue_from_universe(session, universe, dry_run=dry_run)
        if outcome == "added":
            result.would_add += 1
            if not dry_run:
                result.added += 1
        elif outcome == "updated":
            if not dry_run:
                result.updated += 1
            else:
                result.would_add += 1
        else:
            result.skipped += 1
    return result
