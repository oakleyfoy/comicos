"""P98-18G — Collector-value ranking for remaining issue shell gaps (read-only)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.models.catalog_p97 import ComicVineVolumeUniverse
from app.models.universe import UniverseIssue, UniverseVolume
from app.services.catalog_ingestion_service import normalize_issue_number, normalize_series_name
from app.services.p98_gap_priority_service import CORE_TITLES, is_core_title
from app.services.p98_long_tail_shell_planner_service import (
    classify_publisher_tier,
    is_tier4_label,
    tier_number_from_label,
)
from app.services.p98_major_publisher_completeness_service import (
    _issue_shell_counts,
    _p98_volume_by_cv_id,
)
from app.services.p98_publisher_match_repair_service import VOLUME_STATUS_FOREIGN_SUPERSEDED
from app.services.universe.universe_health_service import compute_skeleton_health

REPORT_REL = Path("data/p98/collector_value_gap_report.json")
TOP_VOLUMES_REL = Path("data/p98/top_collector_gap_volumes.json")
GROUPS_REL = Path("data/p98/final_expansion_groups.json")

TAG_KEY_ISSUE = "KEY_ISSUE"
TAG_NUMBER_ONE = "NUMBER_ONE"
TAG_FIRST_APPEARANCE_RUN = "FIRST_APPEARANCE_RUN"
TAG_MAJOR_CHARACTER_RUN = "MAJOR_CHARACTER_RUN"
TAG_ONGOING_CORE_SERIES = "ONGOING_CORE_SERIES"
TAG_LIMITED_SERIES = "LIMITED_SERIES"
TAG_MINISERIES = "MINISERIES"
TAG_COLLECTOR_RELEVANT = "COLLECTOR_RELEVANT"
TAG_ARCHIVAL_ONLY = "ARCHIVAL_ONLY"
TAG_UNKNOWN = "UNKNOWN"

GROUP_A = "GROUP_A"
GROUP_B = "GROUP_B"
GROUP_C = "GROUP_C"
GROUP_D = "GROUP_D"

USEFUL_PUBLISHER_HINTS: frozenset[str] = frozenset(
    normalize_series_name(n)
    for n in (
        "Dell",
        "Charlton",
        "Western Publishing",
        "Western",
        "Harvey",
        "Eclipse",
        "Malibu",
        "Crossgen",
        "CrossGen",
        "EC",
        "First",
        "Fox Comics",
        "Quality Comics",
        "Gold Key",
        "Warren",
        "American Comics Group",
        "ACG",
        "Fantagraphics",
        "Rebellion",
        "2000 AD",
    )
)

FRANCHISE_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("tales from the crypt", TAG_KEY_ISSUE),
    ("vault of horror", TAG_KEY_ISSUE),
    ("shock suspenstories", TAG_KEY_ISSUE),
    ("blue beetle", TAG_MAJOR_CHARACTER_RUN),
    ("captain atom", TAG_MAJOR_CHARACTER_RUN),
    ("ultraverse", TAG_MAJOR_CHARACTER_RUN),
    ("spawn", TAG_MAJOR_CHARACTER_RUN),
    ("sad sack", TAG_COLLECTOR_RELEVANT),
    ("richie rich", TAG_COLLECTOR_RELEVANT),
    ("casper", TAG_COLLECTOR_RELEVANT),
    ("archie", TAG_COLLECTOR_RELEVANT),
    ("four color", TAG_COLLECTOR_RELEVANT),
    ("2000 ad", TAG_ONGOING_CORE_SERIES),
    ("cerebus", TAG_COLLECTOR_RELEVANT),
    ("teenage mutant ninja turtles", TAG_MAJOR_CHARACTER_RUN),
)

PUBLISHER_COLLECTOR_WEIGHT: dict[str, int] = {
    "ec": 25,
    "charlton": 22,
    "dell": 20,
    "harvey": 20,
    "western publishing": 18,
    "western": 18,
    "malibu": 18,
    "crossgen": 17,
    "eclipse": 16,
    "first": 15,
    "quality comics": 15,
    "quality": 15,
    "fox comics": 14,
    "fox": 14,
    "warren": 14,
    "gold key": 14,
    "american comics group": 13,
    "acg": 13,
    "rebellion": 12,
    "fantagraphics": 12,
}


def _api_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_report_path() -> Path:
    return _api_root() / REPORT_REL


def default_top_volumes_path() -> Path:
    return _api_root() / TOP_VOLUMES_REL


def default_groups_path() -> Path:
    return _api_root() / GROUPS_REL


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _publisher_collector_points(publisher: str | None) -> int:
    norm = normalize_series_name(publisher or "")
    best = 0
    for key, pts in PUBLISHER_COLLECTOR_WEIGHT.items():
        if norm == key or norm.startswith(f"{key} ") or key.startswith(f"{norm} "):
            best = max(best, pts)
    if norm in USEFUL_PUBLISHER_HINTS and best == 0:
        return 10
    return best


def _series_type(issue_count: int, volume_name: str) -> str:
    name = normalize_series_name(volume_name)
    if issue_count <= 4:
        return TAG_MINISERIES
    if issue_count <= 12:
        return TAG_LIMITED_SERIES
    if issue_count > 150 or re.search(r"(annual|comics)$", name):
        return TAG_ONGOING_CORE_SERIES
    if 13 <= issue_count <= 60:
        return TAG_LIMITED_SERIES
    return TAG_ONGOING_CORE_SERIES


def _existing_issue_norms(session: Session, universe_volume_id: int) -> set[str]:
    return {
        str(row)
        for row in session.exec(
            select(UniverseIssue.normalized_issue_number).where(
                UniverseIssue.volume_id == universe_volume_id
            )
        ).all()
        if row
    }


def classify_volume_tags(
    *,
    publisher: str | None,
    volume_name: str,
    start_year: int | None,
    issue_count: int,
    missing_shells: int,
    tier_label: str,
    includes_issue_one: bool,
) -> list[str]:
    tags: list[str] = []
    norm = normalize_series_name(volume_name)
    st = _series_type(issue_count, volume_name)
    tags.append(st)

    if is_tier4_label(tier_label) or is_foreign_archival_publisher(publisher):
        tags.append(TAG_ARCHIVAL_ONLY)
    if includes_issue_one and missing_shells > 0:
        tags.append(TAG_NUMBER_ONE)
        tags.append(TAG_FIRST_APPEARANCE_RUN)
    if is_core_title(volume_name) or norm in CORE_TITLES:
        tags.append(TAG_KEY_ISSUE)
        tags.append(TAG_MAJOR_CHARACTER_RUN)
    for keyword, tag in FRANCHISE_KEYWORDS:
        if keyword in norm:
            if tag not in tags:
                tags.append(tag)
    if _publisher_collector_points(publisher) >= 14:
        tags.append(TAG_COLLECTOR_RELEVANT)
    if start_year is not None and start_year <= 1960 and issue_count >= 20:
        tags.append(TAG_COLLECTOR_RELEVANT)
    if not tags or tags == [st]:
        tags.append(TAG_UNKNOWN)
    if TAG_ARCHIVAL_ONLY not in tags and TAG_COLLECTOR_RELEVANT not in tags:
        if st in (TAG_ONGOING_CORE_SERIES, TAG_LIMITED_SERIES):
            tags.append(TAG_COLLECTOR_RELEVANT)
    return sorted(set(tags))


def is_foreign_archival_publisher(publisher: str | None) -> bool:
    from app.services.p98_publisher_match_service import is_foreign_market_publisher

    return is_foreign_market_publisher(publisher)


def compute_collector_value_score(
    *,
    publisher: str | None,
    volume_name: str,
    start_year: int | None,
    issue_count: int,
    missing_shells: int,
    tier_label: str,
    tags: list[str],
    includes_issue_one: bool,
) -> float:
    if missing_shells <= 0:
        return 0.0
    if TAG_ARCHIVAL_ONLY in tags and tier_number_from_label(tier_label) >= 4:
        return min(25.0, 10.0 + missing_shells / 500.0)

    score = 0.0
    score += _publisher_collector_points(publisher)
    if includes_issue_one:
        score += 15.0
    if TAG_MAJOR_CHARACTER_RUN in tags or TAG_KEY_ISSUE in tags:
        score += 18.0
    elif TAG_COLLECTOR_RELEVANT in tags:
        score += 10.0
    if TAG_KEY_ISSUE in tags:
        score += 8.0
    if TAG_KEY_ISSUE in tags and _publisher_collector_points(publisher) >= 20:
        score += 10.0
    if tier_label.startswith("TIER_2"):
        score += 12.0
    elif tier_label.startswith("TIER_3"):
        score += 8.0
    elif tier_label.startswith("TIER_1"):
        score += 5.0
    if issue_count >= 100:
        score += 6.0
    elif issue_count >= 30:
        score += 4.0
    if start_year is not None and start_year < 1970:
        score += 5.0
    # Slight boost for meaningful remaining gap without letting size dominate.
    score += min(8.0, missing_shells / 40.0)
    return round(min(100.0, max(0.0, score)), 2)


def _execution_group(score: float, tags: list[str]) -> str:
    if TAG_ARCHIVAL_ONLY in tags and score < 50:
        return GROUP_D
    if score >= 85:
        return GROUP_A
    if score >= 70:
        return GROUP_B
    if score >= 50:
        return GROUP_C
    return GROUP_D


def _reason_from_tags(tags: list[str], score: float) -> str:
    parts: list[str] = []
    if TAG_KEY_ISSUE in tags:
        parts.append("key franchise title")
    if TAG_NUMBER_ONE in tags:
        parts.append("issue #1 gap")
    if TAG_MAJOR_CHARACTER_RUN in tags:
        parts.append("major character run")
    if TAG_COLLECTOR_RELEVANT in tags:
        parts.append("collector-relevant publisher/series")
    if TAG_ARCHIVAL_ONLY in tags:
        parts.append("archival/low collector priority")
    if not parts:
        parts.append("general completion")
    parts.append(f"score={score:.0f}")
    return "; ".join(parts)


@dataclass
class MissingShellSample:
    publisher: str
    volume: str
    comicvine_volume_id: int
    issue_number: str
    issue_count: int
    start_year: int | None
    series_type: str
    tags: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "publisher": self.publisher,
            "volume": self.volume,
            "comicvine_volume_id": self.comicvine_volume_id,
            "issue_number": self.issue_number,
            "issue_count": self.issue_count,
            "year": self.start_year,
            "series_type": self.series_type,
            "tags": self.tags,
        }


@dataclass
class CollectorGapVolume:
    publisher: str
    volume: str
    comicvine_volume_id: int
    missing_shells: int
    issue_count: int
    start_year: int | None
    series_type: str
    tags: list[str]
    collector_value_score: float
    reason: str
    execution_group: str
    includes_issue_one: bool
    useful_publisher: bool
    tier: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "publisher": self.publisher,
            "volume": self.volume,
            "comicvine_volume_id": self.comicvine_volume_id,
            "missing_shells": self.missing_shells,
            "issue_count": self.issue_count,
            "year": self.start_year,
            "series_type": self.series_type,
            "tags": self.tags,
            "collector_value_score": self.collector_value_score,
            "reason": self.reason,
            "execution_group": self.execution_group,
            "includes_issue_one": self.includes_issue_one,
            "useful_publisher": self.useful_publisher,
            "tier": self.tier,
        }


@dataclass
class ExpansionScenario:
    target_shells: int | None
    shells_allocated: int
    volume_count: int
    coverage_percent_after: float
    top_volumes: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "target_shells": self.target_shells,
            "shells_allocated": self.shells_allocated,
            "volume_count": self.volume_count,
            "coverage_percent_after": self.coverage_percent_after,
            "top_volumes": self.top_volumes,
        }


@dataclass
class CollectorValueGapReport:
    generated_at: str
    current_shells: int
    discoverable_issues: int
    missing_shells_total: int
    useful_missing_shells: int
    coverage_percent: float
    projected_coverage_all_useful: float
    shell_samples: list[MissingShellSample]
    volumes: list[CollectorGapVolume]
    top_opportunities: list[CollectorGapVolume]
    expansion_groups: dict[str, list[dict[str, Any]]]
    scenarios: list[ExpansionScenario]
    recommendation: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "current_shells": self.current_shells,
            "discoverable_issues": self.discoverable_issues,
            "missing_shells_total": self.missing_shells_total,
            "useful_missing_shells": self.useful_missing_shells,
            "coverage_percent": self.coverage_percent,
            "projected_coverage_all_useful": self.projected_coverage_all_useful,
            "shell_samples": [s.as_dict() for s in self.shell_samples],
            "volume_count_with_gaps": len(self.volumes),
            "top_opportunities": [v.as_dict() for v in self.top_opportunities],
            "expansion_groups": self.expansion_groups,
            "scenarios": [s.as_dict() for s in self.scenarios],
            "recommendation": self.recommendation,
        }


def _is_useful_volume(publisher: str, tier_label: str, score: float, tags: list[str]) -> bool:
    """Strategy-aligned useful gap: non–tier-4 expansion targets (matches ~14k long-tail plan)."""
    if is_tier4_label(tier_label):
        return False
    if TAG_ARCHIVAL_ONLY in tags and is_foreign_archival_publisher(publisher):
        return False
    return True


def _allocate_scenario(
    volumes: list[CollectorGapVolume],
    *,
    target: int | None,
    discoverable: int,
    current_shells: int,
) -> ExpansionScenario:
    ordered = sorted(volumes, key=lambda v: (-v.collector_value_score, -v.missing_shells))
    remaining = int(target) if target is not None else None
    allocated = 0
    picked: list[CollectorGapVolume] = []
    for vol in ordered:
        if remaining is not None and remaining <= 0:
            break
        take = vol.missing_shells if remaining is None else min(vol.missing_shells, remaining)
        if take <= 0:
            continue
        allocated += take
        picked.append(vol)
        if remaining is not None:
            remaining -= take
    after = current_shells + allocated
    cov = round(min(100.0, after / discoverable * 100.0), 2) if discoverable else 100.0
    return ExpansionScenario(
        target_shells=target,
        shells_allocated=allocated,
        volume_count=len(picked),
        coverage_percent_after=cov,
        top_volumes=[v.as_dict() for v in picked[:25]],
    )


def build_collector_value_gap_report(
    session: Session,
    *,
    top_n: int = 100,
    shell_sample_limit: int = 200,
    useful_only: bool = True,
) -> CollectorValueGapReport:
    cv_rows = list(session.exec(select(ComicVineVolumeUniverse)).all())
    p98_by_cv = _p98_volume_by_cv_id(session)
    shell_by_cv = _issue_shell_counts(session)
    health = compute_skeleton_health(session)
    discoverable = sum(int(r.count_of_issues or 0) for r in cv_rows)
    current_shells = health.issues
    missing_total = max(discoverable - current_shells, 0)

    gap_volumes: list[CollectorGapVolume] = []
    shell_samples: list[MissingShellSample] = []

    for cv in cv_rows:
        vid = int(cv.volume_id)
        p98 = p98_by_cv.get(vid)
        if p98 is None:
            continue
        if (p98.volume_status or "").lower() == VOLUME_STATUS_FOREIGN_SUPERSEDED:
            continue
        expected = max(int(cv.count_of_issues or 0), 0)
        shells = shell_by_cv.get(vid, 0)
        missing = max(expected - shells, 0)
        if missing <= 0:
            continue
        pub = str(cv.publisher or "Unknown")
        tier_label = classify_publisher_tier(cv.publisher)
        uv_id = int(p98.id or 0)
        existing = _existing_issue_norms(session, uv_id)
        one_norm = normalize_issue_number("1")
        includes_one = bool(one_norm and one_norm not in existing and expected >= 1)
        tags = classify_volume_tags(
            publisher=pub,
            volume_name=cv.name,
            start_year=cv.start_year,
            issue_count=expected,
            missing_shells=missing,
            tier_label=tier_label,
            includes_issue_one=includes_one,
        )
        score = compute_collector_value_score(
            publisher=pub,
            volume_name=cv.name,
            start_year=cv.start_year,
            issue_count=expected,
            missing_shells=missing,
            tier_label=tier_label,
            tags=tags,
            includes_issue_one=includes_one,
        )
        useful = _is_useful_volume(pub, tier_label, score, tags)
        if useful_only and not useful:
            continue
        st = _series_type(expected, cv.name)
        group = _execution_group(score, tags)
        gap_volumes.append(
            CollectorGapVolume(
                publisher=pub,
                volume=cv.name,
                comicvine_volume_id=vid,
                missing_shells=missing,
                issue_count=expected,
                start_year=cv.start_year,
                series_type=st,
                tags=tags,
                collector_value_score=score,
                reason=_reason_from_tags(tags, score),
                execution_group=group,
                includes_issue_one=includes_one,
                useful_publisher=useful,
                tier=tier_number_from_label(tier_label),
            )
        )
        if includes_one and len(shell_samples) < shell_sample_limit:
            shell_samples.append(
                MissingShellSample(
                    publisher=pub,
                    volume=cv.name,
                    comicvine_volume_id=vid,
                    issue_number="1",
                    issue_count=expected,
                    start_year=cv.start_year,
                    series_type=st,
                    tags=tags,
                )
            )
        if len(shell_samples) < shell_sample_limit and missing <= 30:
            start_n = 2 if includes_one else 1
            for n in range(start_n, min(expected, 30) + 1):
                norm = normalize_issue_number(str(n))
                if norm and norm not in existing:
                    shell_samples.append(
                        MissingShellSample(
                            publisher=pub,
                            volume=cv.name,
                            comicvine_volume_id=vid,
                            issue_number=str(n),
                            issue_count=expected,
                            start_year=cv.start_year,
                            series_type=st,
                            tags=tags,
                        )
                    )
                    if len(shell_samples) >= shell_sample_limit:
                        break

    gap_volumes.sort(key=lambda v: (-v.collector_value_score, -v.missing_shells))
    useful_missing = sum(v.missing_shells for v in gap_volumes)
    top = gap_volumes[: max(1, int(top_n))]

    groups: dict[str, list[dict[str, Any]]] = {
        GROUP_A: [],
        GROUP_B: [],
        GROUP_C: [],
        GROUP_D: [],
    }
    for vol in gap_volumes:
        groups[vol.execution_group].append(vol.as_dict())
    for key in groups:
        groups[key].sort(key=lambda r: -float(r["collector_value_score"]))

    cov = round(min(100.0, current_shells / discoverable * 100.0), 2) if discoverable else 0.0
    proj = (
        round(min(100.0, (current_shells + useful_missing) / discoverable * 100.0), 2)
        if discoverable
        else 100.0
    )

    scenarios = [
        _allocate_scenario(gap_volumes, target=5_000, discoverable=discoverable, current_shells=current_shells),
        _allocate_scenario(gap_volumes, target=10_000, discoverable=discoverable, current_shells=current_shells),
        _allocate_scenario(gap_volumes, target=None, discoverable=discoverable, current_shells=current_shells),
    ]

    recommendation = (
        "Expand GROUP_A and GROUP_B first (EC, Charlton key runs, Malibu/Crossgen, legacy #1 gaps), "
        "then GROUP_C for general Dell/Harvey/Western completion. Defer GROUP_D archival foreign runs."
    )

    return CollectorValueGapReport(
        generated_at=_utc_now_iso(),
        current_shells=current_shells,
        discoverable_issues=discoverable,
        missing_shells_total=missing_total,
        useful_missing_shells=useful_missing,
        coverage_percent=cov,
        projected_coverage_all_useful=proj,
        shell_samples=shell_samples[:shell_sample_limit],
        volumes=gap_volumes,
        top_opportunities=top,
        expansion_groups=groups,
        scenarios=scenarios,
        recommendation=recommendation,
    )


def save_collector_value_outputs(
    report: CollectorValueGapReport,
    *,
    report_path: Path | None = None,
    top_volumes_path: Path | None = None,
    groups_path: Path | None = None,
) -> tuple[Path, Path, Path]:
    rp = report_path or default_report_path()
    tv = top_volumes_path or default_top_volumes_path()
    gp = groups_path or default_groups_path()
    for path in (rp, tv, gp):
        path.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(json.dumps(report.as_dict(), indent=2), encoding="utf-8")
    tv.write_text(json.dumps([v.as_dict() for v in report.top_opportunities], indent=2), encoding="utf-8")
    gp.write_text(
        json.dumps(
            {
                "generated_at": report.generated_at,
                "groups": report.expansion_groups,
                "scenarios": [s.as_dict() for s in report.scenarios],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return rp, tv, gp
