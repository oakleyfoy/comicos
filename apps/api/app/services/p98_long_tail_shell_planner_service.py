"""P98 — Long-tail issue shell expansion planning (read-only)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.models.catalog_p97 import ComicVineVolumeUniverse, P97VolumeIssueImportQueue
from app.services.catalog_ingestion_service import normalize_series_name
from app.services.p98_gap_priority_service import CORE_TITLES, major_publisher_for
from app.services.p98_major_publisher_completeness_service import (
    ACTIVE_QUEUE_STATUSES,
    _issue_shell_counts,
    _p98_volume_by_cv_id,
    _queued_missing_by_cv,
)
from app.services.p98_major_publisher_registry import config_for_comicvine_publisher_name
from app.services.p98_publisher_match_service import is_foreign_market_publisher
from app.services.p98_publisher_match_repair_service import VOLUME_STATUS_FOREIGN_SUPERSEDED
from app.services.universe.universe_health_service import compute_skeleton_health

PLANNER_REL = Path("data/p98/long_tail_shell_planner.json")
TOP_PUBLISHERS_REL = Path("data/p98/top_expansion_publishers.json")
TOP_VOLUMES_REL = Path("data/p98/top_expansion_volumes.json")
TOP_VOLUMES_TIER4_REL = Path("data/p98/top_expansion_volumes_tier4.json")

TIER_1_LABEL = "TIER_1_CORE_US"
TIER_2_LABEL = "TIER_2_LEGACY_US"
TIER_3_LABEL = "TIER_3_ENGLISH_LONG_TAIL"
TIER_4_LABEL = "TIER_4_FOREIGN"

TIER_1_NAMES: frozenset[str] = frozenset(
    normalize_series_name(n)
    for n in (
        "Marvel",
        "Marvel Comics",
        "DC Comics",
        "DC",
        "Image",
        "Image Comics",
        "IDW Publishing",
        "IDW",
        "Dark Horse Comics",
        "Dark Horse",
        "Boom! Studios",
        "Boom",
        "Dynamite",
        "Dynamite Entertainment",
        "Valiant",
        "Valiant Comics",
        "Titan Comics",
        "Titan",
        "Archie Comics",
        "Archie",
        "Mad Cave Studios",
        "Mad Cave",
        "AWA Studios",
        "AWA",
        "Oni Press",
        "Oni",
        "AfterShock Comics",
        "AfterShock",
        "CrossGen",
        "Crossgen",
    )
)

TIER_2_NAMES: frozenset[str] = frozenset(
    normalize_series_name(n)
    for n in (
        "Charlton Comics",
        "Charlton",
        "Dell Comics",
        "Dell",
        "Harvey Comics",
        "Harvey",
        "Gold Key",
        "Western Publishing",
        "Western",
        "American Comics Group",
        "ACG",
        "Warren Publishing",
        "Warren",
    )
)

TIER_3_NAMES: frozenset[str] = frozenset(
    normalize_series_name(n)
    for n in (
        "2000 AD",
        "Rebellion",
        "Heavy Metal",
        "Wizard Entertainment",
        "Wizard",
        "Aardvark-Vanaheim",
        "Cerebus",
        "Kenzer & Company",
        "Knights of the Dinner Table",
    )
)


def _api_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_planner_path() -> Path:
    return _api_root() / PLANNER_REL


def default_top_publishers_path() -> Path:
    return _api_root() / TOP_PUBLISHERS_REL


def default_top_volumes_path() -> Path:
    return _api_root() / TOP_VOLUMES_REL


def default_top_volumes_tier4_path() -> Path:
    return _api_root() / TOP_VOLUMES_TIER4_REL


def tier_number_from_label(tier_label: str) -> int:
    label = str(tier_label or "")
    if label.startswith("TIER_1"):
        return 1
    if label.startswith("TIER_2"):
        return 2
    if label.startswith("TIER_3"):
        return 3
    if label.startswith("TIER_4") or label == TIER_4_LABEL:
        return 4
    return 3


def is_tier4_label(tier_label: str) -> bool:
    label = str(tier_label or "")
    return label == TIER_4_LABEL or label.startswith("TIER_4") or label == "TIER_4_FOREIGN_LOW"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _coverage_percent(built: int, discoverable: int) -> float:
    if discoverable <= 0:
        return 100.0 if built <= 0 else 0.0
    return round(min(100.0, built / discoverable * 100.0), 2)


def _norm_pub(name: str | None) -> str:
    return normalize_series_name(name or "")


def _name_in_set(norm: str, names: frozenset[str]) -> bool:
    if norm in names:
        return True
    for key in names:
        if norm.startswith(f"{key} ") or key.startswith(f"{norm} "):
            return True
    return False


def classify_publisher_tier(publisher: str | None) -> str:
    norm = _norm_pub(publisher)
    if not norm:
        return TIER_3_LABEL
    if _name_in_set(norm, TIER_1_NAMES) or config_for_comicvine_publisher_name(publisher) is not None:
        return TIER_1_LABEL
    if _name_in_set(norm, TIER_2_NAMES):
        return TIER_2_LABEL
    if _name_in_set(norm, TIER_3_NAMES):
        return TIER_3_LABEL
    if is_foreign_market_publisher(publisher):
        return TIER_4_LABEL
    if any(
        token in norm
        for token in (
            "ediciones",
            "editore",
            "editoriale",
            "verlag",
            "forlag",
            "panini",
            "egmont",
            "bonelli",
            "topolino",
            "astorina",
            "dardo",
        )
    ):
        return TIER_4_LABEL
    return TIER_3_LABEL


def _tier_multiplier(tier: str) -> float:
    return {
        TIER_1_LABEL: 0.08,
        TIER_2_LABEL: 1.35,
        TIER_3_LABEL: 1.15,
        TIER_4_LABEL: 0.12,
    }.get(tier, 1.0)


def _english_weight(publisher: str | None, tier: str) -> float:
    if tier == TIER_4_LABEL:
        return 0.2
    if tier == TIER_1_LABEL:
        return 1.0
    norm = _norm_pub(publisher)
    if "comics" in norm or norm.endswith(" press") or norm.endswith(" studios"):
        return 1.0
    return 0.85


def _us_market_weight(publisher: str | None, tier: str) -> float:
    if tier == TIER_1_LABEL:
        major = major_publisher_for(_norm_pub(publisher))
        return 1.0 if major else 0.9
    if tier == TIER_2_LABEL:
        return 0.95
    if tier == TIER_4_LABEL:
        return 0.15
    return 0.75


def _collector_interest_weight(publisher: str | None) -> float:
    major = major_publisher_for(_norm_pub(publisher))
    if major is not None:
        return 1.0 + major.weight / 20_000.0
    norm = _norm_pub(publisher)
    if _name_in_set(norm, TIER_2_NAMES):
        return 0.9
    if _name_in_set(norm, TIER_3_NAMES):
        return 0.85
    return 0.6


def _volume_collector_weight(volume_name: str | None) -> float:
    norm = normalize_series_name(volume_name or "")
    if norm in CORE_TITLES:
        return 1.4
    return 1.0


def compute_publisher_expansion_score(
    *,
    missing_shells: int,
    publisher: str | None,
    tier: str,
    queue_volume_count: int,
    queue_missing_issues: int,
) -> float:
    if missing_shells <= 0:
        return 0.0
    base = float(missing_shells)
    score = (
        base
        * _tier_multiplier(tier)
        * _english_weight(publisher, tier)
        * _us_market_weight(publisher, tier)
        * _collector_interest_weight(publisher)
    )
    score += min(queue_missing_issues, 500) * 0.5
    score += queue_volume_count * 2.0
    return round(score, 2)


def compute_volume_expansion_score(
    *,
    missing_shells: int,
    publisher: str | None,
    tier: str,
    volume_name: str | None,
    queue_missing: int,
) -> float:
    if missing_shells <= 0:
        return 0.0
    pub_score = compute_publisher_expansion_score(
        missing_shells=missing_shells,
        publisher=publisher,
        tier=tier,
        queue_volume_count=1 if queue_missing > 0 else 0,
        queue_missing_issues=queue_missing,
    )
    return round(pub_score * _volume_collector_weight(volume_name), 2)


def _priority_label(score: float, tier: str) -> str:
    if score <= 0:
        return "SKIP"
    if tier == TIER_4_LABEL:
        return "LOW"
    if score >= 5000:
        return "HIGH"
    if score >= 500:
        return "MEDIUM"
    return "NORMAL"


@dataclass
class PublisherShellStats:
    publisher: str
    volumes: int = 0
    discoverable_issues: int = 0
    current_shells: int = 0
    missing_shells: int = 0
    coverage_percent: float = 0.0
    queue_volume_count: int = 0
    queue_missing_issues: int = 0
    priority_tier: str = TIER_3_LABEL
    expansion_score: float = 0.0
    recommended_priority: str = "SKIP"

    def as_dict(self) -> dict[str, Any]:
        return {
            "publisher": self.publisher,
            "tier": tier_number_from_label(self.priority_tier),
            "priority": self.recommended_priority,
            "volumes": self.volumes,
            "discoverable_issues": self.discoverable_issues,
            "current_shells": self.current_shells,
            "missing_shells": self.missing_shells,
            "coverage_percent": self.coverage_percent,
            "queue_volume_count": self.queue_volume_count,
            "queue_missing_issues": self.queue_missing_issues,
            "priority_tier": self.priority_tier,
            "expansion_score": self.expansion_score,
            "recommended_priority": self.recommended_priority,
        }


@dataclass
class VolumeExpansionTarget:
    comicvine_volume_id: int
    volume_name: str
    publisher: str
    missing_shells: int
    expansion_score: float
    priority_tier: str
    recommended_priority: str
    has_canonical_p98_volume: bool
    queue_missing_issues: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "volume": self.volume_name,
            "comicvine_volume_id": self.comicvine_volume_id,
            "publisher": self.publisher,
            "tier": tier_number_from_label(self.priority_tier),
            "priority": self.recommended_priority,
            "missing_shells": self.missing_shells,
            "expansion_score": self.expansion_score,
            "priority_tier": self.priority_tier,
            "has_canonical_p98_volume": self.has_canonical_p98_volume,
            "queue_missing_issues": self.queue_missing_issues,
        }


@dataclass
class ShellBuildScenario:
    target_shells: int
    publishers: list[dict[str, Any]]
    expected_shell_gain: int
    expected_coverage_gain_percent: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "target_shells": self.target_shells,
            "publishers": self.publishers,
            "expected_shell_gain": self.expected_shell_gain,
            "expected_coverage_gain_percent": self.expected_coverage_gain_percent,
        }


@dataclass
class LongTailShellPlannerReport:
    generated_at: str
    global_discoverable_issues: int
    global_current_shells: int
    global_missing_shells: int
    global_coverage_percent: float
    publishers: list[PublisherShellStats]
    top_expansion_publishers: list[PublisherShellStats]
    top_expansion_volumes: list[VolumeExpansionTarget]
    top_expansion_volumes_tier4: list[VolumeExpansionTarget]
    scenarios: list[ShellBuildScenario]
    final_recommendation: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "global_discoverable_issues": self.global_discoverable_issues,
            "global_current_shells": self.global_current_shells,
            "global_missing_shells": self.global_missing_shells,
            "global_coverage_percent": self.global_coverage_percent,
            "publishers": [p.as_dict() for p in self.publishers],
            "top_expansion_publishers": [p.as_dict() for p in self.top_expansion_publishers],
            "top_expansion_volumes": [v.as_dict() for v in self.top_expansion_volumes],
            "top_expansion_volumes_tier4": [v.as_dict() for v in self.top_expansion_volumes_tier4],
            "scenarios": [s.as_dict() for s in self.scenarios],
            "final_recommendation": self.final_recommendation,
        }


def _queue_stats_by_publisher(session: Session) -> dict[str, tuple[int, int]]:
    """publisher display name -> (volume_count, missing_issues)."""
    out: dict[str, tuple[int, int]] = {}
    for row in session.exec(select(P97VolumeIssueImportQueue)).all():
        status = (row.status or "").lower()
        if status not in ACTIVE_QUEUE_STATUSES:
            continue
        missing = int(row.missing_issue_count or 0)
        if missing <= 0:
            continue
        pub = str(row.publisher or "Unknown")
        vols, miss = out.get(pub, (0, 0))
        out[pub] = (vols + 1, miss + missing)
    return out


def _publisher_key(display: str) -> str:
    return display.strip() or "Unknown"


def build_long_tail_shell_planner_report(
    session: Session,
    *,
    top_publishers: int = 100,
    top_volumes: int = 250,
) -> LongTailShellPlannerReport:
    cv_rows = list(session.exec(select(ComicVineVolumeUniverse)).all())
    p98_by_cv = _p98_volume_by_cv_id(session)
    shell_by_cv = _issue_shell_counts(session)
    queued_by_cv = _queued_missing_by_cv(session)
    queue_by_pub = _queue_stats_by_publisher(session)
    health = compute_skeleton_health(session)

    global_discoverable = sum(int(r.count_of_issues or 0) for r in cv_rows)
    global_shells = health.issues
    global_missing = max(global_discoverable - global_shells, 0)

    pub_stats: dict[str, PublisherShellStats] = {}
    volume_targets: list[VolumeExpansionTarget] = []

    for cv in cv_rows:
        pub_display = _publisher_key(str(cv.publisher or "Unknown"))
        stats = pub_stats.get(pub_display)
        if stats is None:
            tier = classify_publisher_tier(cv.publisher)
            q_vol, q_miss = queue_by_pub.get(pub_display, (0, 0))
            stats = PublisherShellStats(
                publisher=pub_display,
                priority_tier=tier,
                queue_volume_count=q_vol,
                queue_missing_issues=q_miss,
            )
            pub_stats[pub_display] = stats

        vid = int(cv.volume_id)
        discoverable = max(int(cv.count_of_issues or 0), 0)
        stats.volumes += 1
        stats.discoverable_issues += discoverable

        p98 = p98_by_cv.get(vid)
        superseded = (
            p98 is not None
            and (p98.volume_status or "").lower() == VOLUME_STATUS_FOREIGN_SUPERSEDED
        )
        has_canonical = p98 is not None and not superseded
        shells = shell_by_cv.get(vid, 0) if has_canonical else 0
        if has_canonical:
            stats.current_shells += shells
        missing = max(discoverable - shells, 0) if has_canonical else discoverable
        stats.missing_shells += missing

        q_missing = queued_by_cv.get(vid, 0)
        if missing > 0:
            tier = stats.priority_tier
            v_score = compute_volume_expansion_score(
                missing_shells=missing,
                publisher=cv.publisher,
                tier=tier,
                volume_name=cv.name,
                queue_missing=q_missing,
            )
            volume_targets.append(
                VolumeExpansionTarget(
                    comicvine_volume_id=vid,
                    volume_name=cv.name,
                    publisher=pub_display,
                    missing_shells=missing,
                    expansion_score=v_score,
                    priority_tier=tier,
                    recommended_priority=_priority_label(v_score, tier),
                    has_canonical_p98_volume=has_canonical,
                    queue_missing_issues=q_missing,
                )
            )

    for stats in pub_stats.values():
        stats.coverage_percent = _coverage_percent(stats.current_shells, stats.discoverable_issues)
        stats.expansion_score = compute_publisher_expansion_score(
            missing_shells=stats.missing_shells,
            publisher=stats.publisher,
            tier=stats.priority_tier,
            queue_volume_count=stats.queue_volume_count,
            queue_missing_issues=stats.queue_missing_issues,
        )
        stats.recommended_priority = _priority_label(stats.expansion_score, stats.priority_tier)

    all_publishers = sorted(pub_stats.values(), key=lambda p: p.publisher.lower())
    expand_publishers = sorted(
        [
            p
            for p in pub_stats.values()
            if p.missing_shells > 0 and not is_tier4_label(p.priority_tier)
        ],
        key=lambda p: p.expansion_score,
        reverse=True,
    )
    top_pub = expand_publishers[: max(1, int(top_publishers))]

    strategy_volumes = [v for v in volume_targets if not is_tier4_label(v.priority_tier)]
    tier4_volumes = [v for v in volume_targets if is_tier4_label(v.priority_tier)]
    strategy_volumes.sort(key=lambda v: v.expansion_score, reverse=True)
    tier4_volumes.sort(key=lambda v: v.expansion_score, reverse=True)
    top_vol = strategy_volumes[: max(1, int(top_volumes))]
    top_vol_t4 = tier4_volumes[: max(1, int(top_volumes))]

    scenarios = [
        _build_scenario(
            target=10_000,
            volumes=volume_targets,
            global_discoverable=global_discoverable,
            global_shells=global_shells,
            top_publishers=10,
        ),
        _build_scenario(
            target=25_000,
            volumes=volume_targets,
            global_discoverable=global_discoverable,
            global_shells=global_shells,
            top_publishers=15,
        ),
        _build_scenario(
            target=50_000,
            volumes=volume_targets,
            global_discoverable=global_discoverable,
            global_shells=global_shells,
            top_publishers=20,
        ),
    ]

    recommendation = (
        "Prioritize TIER_2 legacy US and TIER_3 English long-tail publishers with the "
        "largest missing shell counts. Major US publishers (TIER_1) are already near "
        "complete; use targeted volume expansion on ranked top_expansion_volumes rather "
        "than broad ComicVine discovery."
    )

    return LongTailShellPlannerReport(
        generated_at=_utc_now_iso(),
        global_discoverable_issues=global_discoverable,
        global_current_shells=global_shells,
        global_missing_shells=global_missing,
        global_coverage_percent=_coverage_percent(global_shells, global_discoverable),
        publishers=all_publishers,
        top_expansion_publishers=top_pub,
        top_expansion_volumes=top_vol,
        top_expansion_volumes_tier4=top_vol_t4,
        scenarios=scenarios,
        final_recommendation=recommendation,
    )


def _build_scenario(
    *,
    target: int,
    volumes: list[VolumeExpansionTarget],
    global_discoverable: int,
    global_shells: int,
    top_publishers: int,
) -> ShellBuildScenario:
    remaining = int(target)
    by_pub: dict[str, int] = {}
    candidates = [v for v in volumes if not is_tier4_label(v.priority_tier)]
    for vol in candidates:
        if remaining <= 0:
            break
        take = min(remaining, vol.missing_shells)
        if take <= 0:
            continue
        by_pub[vol.publisher] = by_pub.get(vol.publisher, 0) + take
        remaining -= take
    gain = target - remaining
    pub_rows = sorted(by_pub.items(), key=lambda x: x[1], reverse=True)[:top_publishers]
    publishers = [
        {"publisher": name, "expected_shell_gain": shells} for name, shells in pub_rows
    ]
    cov_gain = (gain / global_discoverable * 100.0) if global_discoverable else 0.0
    new_cov = (
        _coverage_percent(global_shells + gain, global_discoverable) - _coverage_percent(global_shells, global_discoverable)
    )
    return ShellBuildScenario(
        target_shells=target,
        publishers=publishers,
        expected_shell_gain=gain,
        expected_coverage_gain_percent=round(new_cov, 2),
    )


def save_planner_outputs(
    report: LongTailShellPlannerReport,
    *,
    planner_path: Path | None = None,
    top_publishers_path: Path | None = None,
    top_volumes_path: Path | None = None,
    top_volumes_tier4_path: Path | None = None,
) -> tuple[Path, Path, Path, Path]:
    planner = planner_path or default_planner_path()
    tops_pub = top_publishers_path or default_top_publishers_path()
    tops_vol = top_volumes_path or default_top_volumes_path()
    tops_vol_t4 = top_volumes_tier4_path or default_top_volumes_tier4_path()
    for path in (planner, tops_pub, tops_vol, tops_vol_t4):
        path.parent.mkdir(parents=True, exist_ok=True)
    planner.write_text(json.dumps(report.as_dict(), indent=2), encoding="utf-8")
    tops_pub.write_text(
        json.dumps([p.as_dict() for p in report.top_expansion_publishers], indent=2),
        encoding="utf-8",
    )
    tops_vol.write_text(
        json.dumps([v.as_dict() for v in report.top_expansion_volumes], indent=2),
        encoding="utf-8",
    )
    tops_vol_t4.write_text(
        json.dumps([v.as_dict() for v in report.top_expansion_volumes_tier4], indent=2),
        encoding="utf-8",
    )
    return planner, tops_pub, tops_vol, tops_vol_t4
