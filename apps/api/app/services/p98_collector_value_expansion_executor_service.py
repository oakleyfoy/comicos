"""P98-18H — Execute issue shell expansion from P98-18G collector-value rankings."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from sqlmodel import Session, select

from app.models.catalog_p97 import ComicVineVolumeUniverse
from app.services.p98_collector_value_gap_service import (
    GROUP_A,
    GROUP_B,
    GROUP_C,
    GROUP_D,
    PUBLISHER_COLLECTOR_WEIGHT,
    default_groups_path,
    default_report_path,
    default_top_volumes_path,
)
from app.services.p98_issue_shell_expansion_service import (
    ExpansionStats,
    _expected_issue_count,
    _existing_issue_count,
    _volume_by_cv_id,
    expand_volume_issue_shells,
)
from app.services.p98_publisher_match_repair_service import VOLUME_STATUS_FOREIGN_SUPERSEDED
from app.services.catalog_ingestion_service import normalize_series_name
from app.services.universe.universe_health_service import compute_skeleton_health

PROGRESS_REL = Path("data/p98/collector_expansion_progress.json")

GROUP_KEY_ALIASES: dict[str, str] = {
    "A": GROUP_A,
    "B": GROUP_B,
    "C": GROUP_C,
    "D": GROUP_D,
    "GROUP_A": GROUP_A,
    "GROUP_B": GROUP_B,
    "GROUP_C": GROUP_C,
    "GROUP_D": GROUP_D,
}

DEFAULT_GROUP_KEYS: tuple[str, ...] = (GROUP_A, GROUP_B)


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


def _publisher_priority(publisher: str | None) -> int:
    norm = normalize_series_name(publisher or "")
    best = 0
    for key, pts in PUBLISHER_COLLECTOR_WEIGHT.items():
        if norm == key or norm.startswith(f"{key} ") or key.startswith(f"{norm} "):
            best = max(best, pts)
    return best


def parse_group_spec(spec: str | None) -> list[str]:
    """Parse ``A``, ``A,B``, or ``GROUP_A,GROUP_B`` into canonical group keys."""
    if not spec or not str(spec).strip():
        return list(DEFAULT_GROUP_KEYS)
    parts = re.split(r"[\s,]+", str(spec).strip().upper())
    out: list[str] = []
    for part in parts:
        if not part:
            continue
        key = GROUP_KEY_ALIASES.get(part)
        if key is None:
            raise ValueError(f"Unknown expansion group: {part!r} (use A, B, C, D)")
        if key not in out:
            out.append(key)
    if not out:
        return list(DEFAULT_GROUP_KEYS)
    return out


def load_expansion_groups_file(path: Path | None = None) -> dict[str, Any]:
    gp = path or default_groups_path()
    if not gp.is_file():
        raise FileNotFoundError(f"Missing collector expansion groups file: {gp}")
    data = json.loads(gp.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"Invalid groups JSON (expected object): {gp}")
    return data


def load_top_collector_volumes(path: Path | None = None) -> list[dict[str, Any]]:
    tp = path or default_top_volumes_path()
    if not tp.is_file():
        raise FileNotFoundError(f"Missing top collector volumes file: {tp}")
    data = json.loads(tp.read_text(encoding="utf-8-sig"))
    if not isinstance(data, list):
        raise ValueError(f"Invalid top volumes JSON (expected list): {tp}")
    return list(data)


def top_collector_rank_map(top_rows: list[dict[str, Any]]) -> dict[int, int]:
    """Lower rank index = higher priority (exact P98-18G top list order)."""
    return {
        int(row["comicvine_volume_id"]): idx
        for idx, row in enumerate(top_rows)
        if int(row.get("comicvine_volume_id") or 0) > 0
    }


def collect_volumes_for_groups(
    groups_data: dict[str, Any],
    group_keys: list[str],
) -> list[dict[str, Any]]:
    groups = groups_data.get("groups") or {}
    if not isinstance(groups, dict):
        raise ValueError("final_expansion_groups.json missing 'groups' object")
    seen: set[int] = set()
    rows: list[dict[str, Any]] = []
    for gk in group_keys:
        bucket = groups.get(gk) or []
        if not isinstance(bucket, list):
            continue
        for raw in bucket:
            if not isinstance(raw, dict):
                continue
            cv_id = int(raw.get("comicvine_volume_id") or 0)
            if cv_id <= 0 or cv_id in seen:
                continue
            seen.add(cv_id)
            row = dict(raw)
            row["execution_group"] = gk
            rows.append(row)
    return rows


def order_collector_volumes(
    rows: list[dict[str, Any]],
    *,
    collector_ranked: bool,
    rank_map: dict[int, int],
) -> list[dict[str, Any]]:
    if not collector_ranked:
        return list(rows)

    def sort_key(raw: dict[str, Any]) -> tuple[Any, ...]:
        cv_id = int(raw.get("comicvine_volume_id") or 0)
        score = float(raw.get("collector_value_score") or 0.0)
        missing = int(raw.get("missing_shells") or 0)
        pub_pri = _publisher_priority(str(raw.get("publisher") or ""))
        top_rank = rank_map.get(cv_id, 999_999)
        return (-score, -missing, -pub_pri, top_rank)

    return sorted(rows, key=sort_key)


def load_baseline_useful_gap(report_path: Path | None = None) -> int | None:
    rp = report_path or default_report_path()
    if not rp.is_file():
        return None
    try:
        data = json.loads(rp.read_text(encoding="utf-8-sig"))
        if isinstance(data, dict) and data.get("useful_missing_shells") is not None:
            return int(data["useful_missing_shells"])
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return None
    return None


@dataclass
class CollectorPlannedVolume:
    comicvine_volume_id: int
    volume_name: str
    publisher: str
    execution_group: str
    collector_value_score: float
    shells_to_create: int
    missing_shells: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "comicvine_volume_id": self.comicvine_volume_id,
            "volume": self.volume_name,
            "publisher": self.publisher,
            "execution_group": self.execution_group,
            "collector_value_score": self.collector_value_score,
            "shells_to_create": self.shells_to_create,
            "missing_shells": self.missing_shells,
        }


@dataclass
class CollectorExpansionPlan:
    selected_groups: list[str]
    collector_ranked: bool
    volumes_selected: int
    shells_to_create: int
    projected_coverage_gain_percent: float
    volumes: list[CollectorPlannedVolume]
    dry_run: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "selected_groups": self.selected_groups,
            "collector_ranked": self.collector_ranked,
            "volumes_selected": self.volumes_selected,
            "shells_to_create": self.shells_to_create,
            "projected_coverage_gain_percent": self.projected_coverage_gain_percent,
            "volumes": [v.as_dict() for v in self.volumes],
        }


@dataclass
class CollectorVolumeResult:
    volume: str
    publisher: str
    collector_value_score: float
    shells_added: int
    coverage_gain_percent: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "volume": self.volume,
            "publisher": self.publisher,
            "collector_value_score": self.collector_value_score,
            "shells_added": self.shells_added,
            "coverage_gain_percent": self.coverage_gain_percent,
        }


@dataclass
class CollectorExpansionResult:
    dry_run: bool
    plan: CollectorExpansionPlan
    stats: ExpansionStats
    volume_results: list[CollectorVolumeResult] = field(default_factory=list)
    start_shell_count: int = 0
    end_shell_count: int = 0
    global_discoverable: int = 0
    coverage_percent: float = 0.0
    coverage_gain_percent: float = 0.0
    remaining_useful_gap: int | None = None
    baseline_useful_gap: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "plan": self.plan.as_dict(),
            "stats": self.stats.as_dict(),
            "volume_results": [v.as_dict() for v in self.volume_results],
            "start_shell_count": self.start_shell_count,
            "end_shell_count": self.end_shell_count,
            "global_discoverable": self.global_discoverable,
            "coverage_percent": self.coverage_percent,
            "coverage_gain_percent": self.coverage_gain_percent,
            "remaining_useful_gap": self.remaining_useful_gap,
            "baseline_useful_gap": self.baseline_useful_gap,
        }


def build_collector_expansion_plan(
    session: Session,
    *,
    group_keys: list[str] | None = None,
    groups_path: Path | None = None,
    top_volumes_path: Path | None = None,
    max_shells: int | None = None,
    collector_ranked: bool = False,
    dry_run: bool = True,
) -> CollectorExpansionPlan:
    keys = group_keys or list(DEFAULT_GROUP_KEYS)
    groups_data = load_expansion_groups_file(groups_path)
    top_rows = load_top_collector_volumes(top_volumes_path)
    rank_map = top_collector_rank_map(top_rows)
    rows = collect_volumes_for_groups(groups_data, keys)
    rows = order_collector_volumes(rows, collector_ranked=collector_ranked, rank_map=rank_map)

    discoverable = _global_discoverable(session)
    selected: list[CollectorPlannedVolume] = []
    budget = int(max_shells) if max_shells is not None and max_shells > 0 else None
    shells_total = 0

    for raw in rows:
        if budget is not None and shells_total >= budget:
            break
        cv_id = int(raw.get("comicvine_volume_id") or 0)
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
        selected.append(
            CollectorPlannedVolume(
                comicvine_volume_id=cv_id,
                volume_name=str(raw.get("volume") or volume.name),
                publisher=str(raw.get("publisher") or "Unknown"),
                execution_group=str(raw.get("execution_group") or ""),
                collector_value_score=float(raw.get("collector_value_score") or 0.0),
                shells_to_create=take,
                missing_shells=live_missing,
            )
        )
        shells_total += take

    gain = (shells_total / discoverable * 100.0) if discoverable else 0.0
    return CollectorExpansionPlan(
        selected_groups=keys,
        collector_ranked=collector_ranked,
        volumes_selected=len(selected),
        shells_to_create=shells_total,
        projected_coverage_gain_percent=round(gain, 2),
        volumes=selected,
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


def save_collector_expansion_progress(
    *,
    path: Path | None = None,
    start_shell_count: int,
    current_shell_count: int,
    global_discoverable: int,
    collector_shells_added: int,
    remaining_useful_gap: int | None,
    extra: dict[str, Any] | None = None,
) -> Path:
    out = path or default_progress_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    prev = _load_progress(out)
    cumulative = int(prev.get("collector_shells_added_cumulative") or 0)
    if collector_shells_added > 0:
        cumulative += collector_shells_added
    payload: dict[str, Any] = {
        "updated_at": _utc_now_iso(),
        "start_shell_count": start_shell_count,
        "current_shell_count": current_shell_count,
        "collector_shells_added": collector_shells_added,
        "collector_shells_added_cumulative": cumulative,
        "coverage_percent": _coverage(current_shell_count, global_discoverable),
        "remaining_useful_gap": remaining_useful_gap,
        "global_discoverable_issues": global_discoverable,
    }
    if extra:
        payload.update(extra)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def execute_collector_expansion_plan(
    session: Session,
    plan: CollectorExpansionPlan,
    *,
    dry_run: bool = True,
    commit_every: int = 5,
    baseline_useful_gap: int | None = None,
    on_volume: Callable[[CollectorPlannedVolume, int, float], None] | None = None,
) -> CollectorExpansionResult:
    discoverable = _global_discoverable(session)
    start_shells = int(compute_skeleton_health(session).issues)
    stats = ExpansionStats()
    stats.volumes_selected = plan.volumes_selected
    volume_results: list[CollectorVolumeResult] = []

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
            added = item.shells_to_create
            stats.issues_created += added
            stats.variants_created += added
            stats.volumes_expanded += 1
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
            else:
                stats.volumes_skipped += 1
            if commit_every > 0 and idx % int(commit_every) == 0:
                session.commit()

        gain = (added / discoverable * 100.0) if discoverable else 0.0
        volume_results.append(
            CollectorVolumeResult(
                volume=item.volume_name,
                publisher=item.publisher,
                collector_value_score=item.collector_value_score,
                shells_added=added,
                coverage_gain_percent=round(gain, 2),
            )
        )
        if on_volume is not None:
            on_volume(item, added, gain)

    if not dry_run:
        session.commit()

    end_shells = start_shells if dry_run else int(compute_skeleton_health(session).issues)
    if dry_run:
        end_shells = start_shells + stats.issues_created

    cov_before = _coverage(start_shells, discoverable)
    cov_after = _coverage(end_shells, discoverable)
    remaining: int | None = None
    if baseline_useful_gap is not None:
        remaining = max(baseline_useful_gap - stats.issues_created, 0)

    return CollectorExpansionResult(
        dry_run=dry_run,
        plan=plan,
        stats=stats,
        volume_results=volume_results,
        start_shell_count=start_shells,
        end_shell_count=end_shells,
        global_discoverable=discoverable,
        coverage_percent=cov_after,
        coverage_gain_percent=round(cov_after - cov_before, 2),
        remaining_useful_gap=remaining,
        baseline_useful_gap=baseline_useful_gap,
    )


def format_group_labels(group_keys: list[str]) -> str:
    labels = []
    for gk in group_keys:
        for alias, canonical in GROUP_KEY_ALIASES.items():
            if canonical == gk and len(alias) == 1:
                labels.append(alias)
                break
        else:
            labels.append(gk.replace("GROUP_", ""))
    return ",".join(labels)
