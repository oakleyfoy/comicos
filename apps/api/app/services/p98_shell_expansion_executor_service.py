"""P98-18E — Controlled long-tail shell expansion from planner JSON (dry-run default)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.catalog_p97 import ComicVineVolumeUniverse
from app.models.universe import UniverseVolume
from app.services.p98_issue_shell_expansion_service import (
    ExpansionStats,
    _expected_issue_count,
    _existing_issue_count,
    _volume_by_cv_id,
    expand_volume_issue_shells,
)
from app.services.p98_long_tail_shell_planner_service import (
    default_top_publishers_path,
    default_top_volumes_path,
    default_top_volumes_tier4_path,
    is_tier4_label,
    tier_number_from_label,
)
from app.services.p98_publisher_match_repair_service import VOLUME_STATUS_FOREIGN_SUPERSEDED
from app.services.universe.universe_health_service import compute_skeleton_health

PROGRESS_REL = Path("data/p98/shell_expansion_progress.json")


def _api_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_progress_path() -> Path:
    return _api_root() / PROGRESS_REL


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _global_discoverable(session: Session) -> int:
    return int(
        sum(
            int(r.count_of_issues or 0)
            for r in session.exec(select(ComicVineVolumeUniverse)).all()
        )
    )


def _coverage(shells: int, discoverable: int) -> float:
    if discoverable <= 0:
        return 100.0
    return round(min(100.0, shells / discoverable * 100.0), 2)


@dataclass
class PlannedVolumeExpansion:
    comicvine_volume_id: int
    volume_name: str
    publisher: str
    priority_tier: str
    shells_to_create: int
    missing_shells: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "comicvine_volume_id": self.comicvine_volume_id,
            "volume": self.volume_name,
            "publisher": self.publisher,
            "priority_tier": self.priority_tier,
            "shells_to_create": self.shells_to_create,
            "missing_shells": self.missing_shells,
        }


@dataclass
class PublisherExpansionReport:
    publisher: str
    volumes_expanded: int = 0
    shells_added: int = 0
    coverage_gain_percent: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "publisher": self.publisher,
            "volumes_expanded": self.volumes_expanded,
            "shells_added": self.shells_added,
            "coverage_gain_percent": self.coverage_gain_percent,
        }


@dataclass
class ShellExpansionExecutionPlan:
    volumes_selected: int
    shells_to_create: int
    volumes: list[PlannedVolumeExpansion]
    shells_by_publisher: dict[str, int]
    dry_run: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "volumes_selected": self.volumes_selected,
            "shells_to_create": self.shells_to_create,
            "shells_by_publisher": self.shells_by_publisher,
            "volumes": [v.as_dict() for v in self.volumes],
        }


@dataclass
class ShellExpansionExecutionResult:
    dry_run: bool
    plan: ShellExpansionExecutionPlan
    stats: ExpansionStats
    publisher_reports: list[PublisherExpansionReport] = field(default_factory=list)
    start_shell_count: int = 0
    end_shell_count: int = 0
    global_discoverable: int = 0
    coverage_percent: float = 0.0
    remaining_gap: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "plan": self.plan.as_dict(),
            "stats": self.stats.as_dict(),
            "publisher_reports": [p.as_dict() for p in self.publisher_reports],
            "start_shell_count": self.start_shell_count,
            "end_shell_count": self.end_shell_count,
            "global_discoverable": self.global_discoverable,
            "coverage_percent": self.coverage_percent,
            "remaining_gap": self.remaining_gap,
        }


def load_planner_volume_rows(
    volumes_path: Path | None = None,
    *,
    include_tier4: bool = False,
) -> list[dict[str, Any]]:
    path = volumes_path or default_top_volumes_path()
    if not path.is_file():
        raise FileNotFoundError(f"Missing planner volumes file: {path}")
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, list):
        raise ValueError(f"Invalid volumes JSON (expected list): {path}")
    rows: list[dict[str, Any]] = list(data)
    if include_tier4:
        t4_path = default_top_volumes_tier4_path()
        if t4_path.is_file():
            t4_data = json.loads(t4_path.read_text(encoding="utf-8-sig"))
            if isinstance(t4_data, list):
                rows.extend(t4_data)
    return rows


def load_planner_publisher_rows(
    publishers_path: Path | None = None,
) -> list[dict[str, Any]]:
    path = publishers_path or default_top_publishers_path()
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return data if isinstance(data, list) else []


def _row_is_tier4(raw: dict[str, Any]) -> bool:
    tier = raw.get("tier")
    if tier is not None and int(tier) == 4:
        return True
    return is_tier4_label(str(raw.get("priority_tier") or ""))


def _tier_matches(raw: dict[str, Any], *, tier: int | None, include_tier4: bool) -> bool:
    if _row_is_tier4(raw) and not include_tier4:
        return False
    tier_label = str(raw.get("priority_tier") or "")
    row_tier = int(raw.get("tier") or tier_number_from_label(tier_label))
    if tier is None:
        return include_tier4 or not _row_is_tier4(raw)
    return row_tier == int(tier)


def build_shell_expansion_plan(
    session: Session,
    *,
    volume_rows: list[dict[str, Any]] | None = None,
    max_shells: int | None = None,
    tier: int | None = None,
    include_tier4: bool = False,
    dry_run: bool = True,
) -> ShellExpansionExecutionPlan:
    rows = (
        volume_rows
        if volume_rows is not None
        else load_planner_volume_rows(include_tier4=include_tier4)
    )
    selected: list[PlannedVolumeExpansion] = []
    shells_by_pub: dict[str, int] = {}
    budget = int(max_shells) if max_shells is not None and max_shells > 0 else None
    shells_total = 0

    for raw in rows:
        if budget is not None and shells_total >= budget:
            break
        tier_label = str(raw.get("priority_tier") or "")
        if not _tier_matches(raw, tier=tier, include_tier4=include_tier4):
            continue
        if not raw.get("has_canonical_p98_volume", True):
            continue
        cv_id = int(raw.get("comicvine_volume_id") or 0)
        if cv_id <= 0:
            continue
        missing = int(raw.get("missing_shells") or 0)
        if missing <= 0:
            continue
        volume = _volume_by_cv_id(session, cv_id)
        if volume is None:
            continue
        if (volume.volume_status or "").lower() == VOLUME_STATUS_FOREIGN_SUPERSEDED:
            continue
        expected = _expected_issue_count(session, comicvine_volume_id=cv_id, volume=volume)
        existing = _existing_issue_count(session, int(volume.id or 0))
        live_missing = max(expected - existing, 0)
        if live_missing <= 0:
            continue
        take = live_missing if budget is None else min(live_missing, budget - shells_total)
        if take <= 0:
            continue
        pub = str(raw.get("publisher") or "Unknown")
        selected.append(
            PlannedVolumeExpansion(
                comicvine_volume_id=cv_id,
                volume_name=str(raw.get("volume") or volume.name),
                publisher=pub,
                priority_tier=tier_label,
                shells_to_create=take,
                missing_shells=live_missing,
            )
        )
        shells_by_pub[pub] = shells_by_pub.get(pub, 0) + take
        shells_total += take

    return ShellExpansionExecutionPlan(
        volumes_selected=len(selected),
        shells_to_create=shells_total,
        volumes=selected,
        shells_by_publisher=shells_by_pub,
        dry_run=dry_run,
    )


def _load_progress(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_shell_expansion_progress(
    *,
    path: Path | None = None,
    start_shell_count: int,
    current_shell_count: int,
    global_discoverable: int,
    shells_added_this_run: int,
    extra: dict[str, Any] | None = None,
) -> Path:
    out = path or default_progress_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    prev = _load_progress(out)
    cumulative = int(prev.get("shells_added_cumulative") or 0)
    if shells_added_this_run > 0:
        cumulative += shells_added_this_run
    payload = {
        "updated_at": _utc_now_iso(),
        "start_shell_count": start_shell_count,
        "current_shell_count": current_shell_count,
        "shells_added": shells_added_this_run,
        "shells_added_cumulative": cumulative,
        "coverage_percent": _coverage(current_shell_count, global_discoverable),
        "remaining_gap": max(global_discoverable - current_shell_count, 0),
        "global_discoverable_issues": global_discoverable,
    }
    if extra:
        payload.update(extra)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def execute_shell_expansion_plan(
    session: Session,
    plan: ShellExpansionExecutionPlan,
    *,
    dry_run: bool = True,
    commit_every: int = 5,
    on_volume: Callable[[PlannedVolumeExpansion, ExpansionStats], None] | None = None,
) -> ShellExpansionExecutionResult:
    discoverable = _global_discoverable(session)
    start_shells = int(compute_skeleton_health(session).issues)
    stats = ExpansionStats()
    stats.volumes_selected = plan.volumes_selected
    pub_issues: dict[str, int] = {}
    pub_volumes: dict[str, int] = {}

    for idx, item in enumerate(plan.volumes, start=1):
        volume = _volume_by_cv_id(session, item.comicvine_volume_id)
        if volume is None:
            stats.volumes_failed += 1
            stats.failed_comicvine_volume_ids.append(item.comicvine_volume_id)
            continue
        expected = _expected_issue_count(
            session, comicvine_volume_id=item.comicvine_volume_id, volume=volume
        )
        before = stats.issues_created
        if dry_run:
            stats.issues_created += item.shells_to_create
            stats.variants_created += item.shells_to_create
            stats.volumes_expanded += 1
            pub_issues[item.publisher] = pub_issues.get(item.publisher, 0) + item.shells_to_create
            pub_volumes[item.publisher] = pub_volumes.get(item.publisher, 0) + 1
        else:
            expand_volume_issue_shells(
                session,
                volume=volume,
                expected_issue_count=expected,
                stats=stats,
                publisher_label=item.publisher,
                max_issues_to_create=item.shells_to_create,
            )
            added = stats.issues_created - before
            if added > 0:
                stats.volumes_expanded += 1
                pub_issues[item.publisher] = pub_issues.get(item.publisher, 0) + added
                pub_volumes[item.publisher] = pub_volumes.get(item.publisher, 0) + 1
            else:
                stats.volumes_skipped += 1
            if commit_every > 0 and idx % int(commit_every) == 0:
                session.commit()

        if on_volume is not None:
            on_volume(item, stats)

    if not dry_run:
        session.commit()

    end_shells = start_shells if dry_run else int(compute_skeleton_health(session).issues)
    if dry_run:
        end_shells = start_shells + stats.issues_created

    reports: list[PublisherExpansionReport] = []
    for pub, shells in sorted(pub_issues.items(), key=lambda x: -x[1]):
        gain = (shells / discoverable * 100.0) if discoverable else 0.0
        reports.append(
            PublisherExpansionReport(
                publisher=pub,
                volumes_expanded=pub_volumes.get(pub, 0),
                shells_added=shells,
                coverage_gain_percent=round(gain, 2),
            )
        )

    return ShellExpansionExecutionResult(
        dry_run=dry_run,
        plan=plan,
        stats=stats,
        publisher_reports=reports,
        start_shell_count=start_shells,
        end_shell_count=end_shells,
        global_discoverable=discoverable,
        coverage_percent=_coverage(end_shells, discoverable),
        remaining_gap=max(discoverable - end_shells, 0),
    )
