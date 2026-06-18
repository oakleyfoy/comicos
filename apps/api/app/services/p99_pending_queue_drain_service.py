"""P99-02 — Pending P97 import queue drain planning (read-only)."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.models.catalog_p97 import P97VolumeIssueImportQueue
from app.models.universe import (
    UNIVERSE_ISSUE_STATUS_DISCOVERED,
    UniverseIssue,
    UniverseVolume,
)
from app.services.catalog_ingestion_service import normalize_series_name
from app.services.p98_gap_priority_service import (
    CORE_TITLES,
    is_core_title,
    major_publisher_for,
    score_volume,
)
from app.services.p98_long_tail_shell_planner_service import classify_publisher_tier, tier_number_from_label
from app.services.p98_major_publisher_completeness_service import _resolve_publisher_label
from app.services.p98_publisher_match_service import is_foreign_market_publisher
from app.services.p97_volume_issue_import_queue_service import STATUS_PENDING

PLAN_REL = Path("data/p99/pending_queue_drain_plan.json")
TOP_VOLUMES_REL = Path("data/p99/top_pending_queue_volumes.json")
BATCHES_REL = Path("data/p99/pending_queue_batches.json")

GROUP_1_MAJOR_CORE = "GROUP_1_MAJOR_CORE"
GROUP_2_LEGACY_US = "GROUP_2_LEGACY_US"
GROUP_3_ENGLISH_LONG_TAIL = "GROUP_3_ENGLISH_LONG_TAIL"
GROUP_4_FOREIGN_OR_LOW_PRIORITY = "GROUP_4_FOREIGN_OR_LOW_PRIORITY"
GROUP_5_UNKNOWN = "GROUP_5_UNKNOWN"

DRAIN_GROUPS: tuple[str, ...] = (
    GROUP_1_MAJOR_CORE,
    GROUP_2_LEGACY_US,
    GROUP_3_ENGLISH_LONG_TAIL,
    GROUP_4_FOREIGN_OR_LOW_PRIORITY,
    GROUP_5_UNKNOWN,
)

GROUP_1_PUBLISHERS: frozenset[str] = frozenset(
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
        "Valiant",
        "Valiant Comics",
        "Dynamite",
        "Dynamite Entertainment",
        "Titan Comics",
        "Titan",
    )
)

GROUP_2_PUBLISHERS: frozenset[str] = frozenset(
    normalize_series_name(n)
    for n in (
        "Dell",
        "Dell Comics",
        "Western Publishing",
        "Western",
        "Harvey",
        "Harvey Comics",
        "Charlton",
        "Charlton Comics",
        "EC",
        "EC Comics",
        "Warren",
        "Warren Publishing",
        "American Comics Group",
        "ACG",
        "Gold Key",
        "Gold Key Comics",
        "Fawcett",
        "Fawcett Publications",
        "Quality Comics",
        "Quality",
    )
)

GROUP_3_PUBLISHERS: frozenset[str] = frozenset(
    normalize_series_name(n)
    for n in (
        "Rebellion",
        "2000 AD",
        "First",
        "First Comics",
        "Eclipse",
        "Eclipse Comics",
        "Malibu",
        "Malibu Comics",
        "CrossGen",
        "Crossgen",
        "Fantagraphics",
        "Comico",
        "Warp Graphics",
        "Heavy Metal",
        "Bongo Comics",
        "Bongo",
    )
)

GROUP_4_PUBLISHER_TOKENS: frozenset[str] = frozenset(
    normalize_series_name(n)
    for n in (
        "Egmont",
        "Egmont Comics",
        "Eura Editoriale",
        "Panini Comics",
        "Panini",
        "Topolino",
        "Editoriale Corno",
        "Corno",
        "Astorina",
        "Sergio Bonelli Editore",
        "Dardo",
    )
)

GROUP_WEIGHT: dict[str, int] = {
    GROUP_1_MAJOR_CORE: 100_000,
    GROUP_2_LEGACY_US: 72_000,
    GROUP_3_ENGLISH_LONG_TAIL: 38_000,
    GROUP_4_FOREIGN_OR_LOW_PRIORITY: 6_000,
    GROUP_5_UNKNOWN: 22_000,
}


def _api_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_plan_path() -> Path:
    return _api_root() / PLAN_REL


def default_top_volumes_path() -> Path:
    return _api_root() / TOP_VOLUMES_REL


def default_batches_path() -> Path:
    return _api_root() / BATCHES_REL


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _publisher_norm(publisher: str | None) -> str:
    return normalize_series_name(publisher or "")


def _name_matches_set(norm: str, names: frozenset[str]) -> bool:
    if norm in names:
        return True
    for key in names:
        if norm.startswith(f"{key} ") or key.startswith(f"{norm} "):
            return True
    return False


def classify_drain_group(publisher: str | None, volume_name: str | None = None) -> str:
    norm = _publisher_norm(publisher)
    vol_norm = normalize_series_name(volume_name or "")
    if _name_matches_set(norm, GROUP_1_PUBLISHERS):
        return GROUP_1_MAJOR_CORE
    if _resolve_publisher_label(publisher or "") in {
        "Marvel",
        "DC Comics",
        "Image",
        "IDW Publishing",
        "Dark Horse Comics",
        "Boom! Studios",
        "Valiant",
        "Dynamite",
        "Titan Comics",
    }:
        return GROUP_1_MAJOR_CORE
    if _name_matches_set(norm, GROUP_2_PUBLISHERS):
        return GROUP_2_LEGACY_US
    if _name_matches_set(norm, GROUP_3_PUBLISHERS):
        return GROUP_3_ENGLISH_LONG_TAIL
    if _name_matches_set(norm, GROUP_4_PUBLISHER_TOKENS):
        return GROUP_4_FOREIGN_OR_LOW_PRIORITY
    if is_foreign_market_publisher(publisher):
        return GROUP_4_FOREIGN_OR_LOW_PRIORITY
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
        )
    ):
        return GROUP_4_FOREIGN_OR_LOW_PRIORITY
    if vol_norm in ("topolino", "diabolik", "dylan dog"):
        return GROUP_4_FOREIGN_OR_LOW_PRIORITY
    tier_label = classify_publisher_tier(publisher)
    if tier_label.endswith("FOREIGN"):
        return GROUP_4_FOREIGN_OR_LOW_PRIORITY
    if tier_label.endswith("LEGACY"):
        return GROUP_2_LEGACY_US
    if tier_label.endswith("CORE"):
        return GROUP_1_MAJOR_CORE
    if tier_label.endswith("LONG_TAIL"):
        return GROUP_3_ENGLISH_LONG_TAIL
    return GROUP_5_UNKNOWN


def compute_drain_score(
    *,
    drain_group: str,
    publisher: str | None,
    volume_name: str,
    missing_issue_count: int,
    shells_without_catalog: int,
    queue_priority_score: float,
    start_year: int | None,
) -> int:
    pub_norm = _publisher_norm(publisher)
    major = major_publisher_for(pub_norm)
    core_flag = drain_group == GROUP_1_MAJOR_CORE or major is not None

    score = int(GROUP_WEIGHT.get(drain_group, 20_000))
    score += int(min(max(queue_priority_score, 0.0), 2_000_000) / 50)
    score += min(int(shells_without_catalog), 800) * 18
    score += min(int(missing_issue_count), 800) * 8
    if core_flag:
        score += 28_000
    if major is not None:
        score += major.weight // 400
    collector = score_volume(
        publisher_normalized=pub_norm,
        volume_name=volume_name,
        start_year=start_year,
        missing_issue_count=missing_issue_count,
        issue_count=max(missing_issue_count, shells_without_catalog, 1),
    )
    score += collector // 800
    if is_core_title(volume_name) or normalize_series_name(volume_name) in CORE_TITLES:
        score += 12_000
    if drain_group == GROUP_4_FOREIGN_OR_LOW_PRIORITY:
        score -= 45_000
    return max(score, 0)


def _reason_from_row(
    *,
    drain_group: str,
    core_publisher: bool,
    missing_issue_count: int,
    shells_without_catalog: int,
    drain_score: int,
) -> str:
    parts: list[str] = [drain_group.replace("_", " ").lower()]
    if core_publisher:
        parts.append("core publisher")
    if shells_without_catalog > 0:
        parts.append(f"{shells_without_catalog} discovered shells")
    parts.append(f"queue missing={missing_issue_count}")
    parts.append(f"drain_score={drain_score}")
    return "; ".join(parts)


def _discovered_shells_by_cv_id(session: Session) -> dict[int, int]:
    rows = session.exec(
        select(UniverseVolume.comicvine_volume_id, UniverseIssue.id)
        .join(UniverseIssue, UniverseIssue.volume_id == UniverseVolume.id)
        .where(UniverseIssue.status == UNIVERSE_ISSUE_STATUS_DISCOVERED)
    ).all()
    out: dict[int, int] = {}
    for cv_id, _iid in rows:
        cid = int(cv_id)
        out[cid] = out.get(cid, 0) + 1
    return out


def _start_year_by_cv(session: Session, cv_ids: list[int]) -> dict[int, int | None]:
    if not cv_ids:
        return {}
    from app.models.catalog_p97 import ComicVineVolumeUniverse

    pairs = session.exec(
        select(ComicVineVolumeUniverse.volume_id, ComicVineVolumeUniverse.start_year).where(
            ComicVineVolumeUniverse.volume_id.in_(cv_ids)
        )
    ).all()
    return {int(vid): (int(y) if y is not None else None) for vid, y in pairs}


@dataclass
class PendingQueueDrainRow:
    rank: int
    comicvine_volume_id: int
    volume_name: str
    publisher: str | None
    drain_group: str
    tier: int
    core_publisher: bool
    missing_issue_count: int
    shells_without_catalog: int
    queue_priority_score: float
    launch_priority_tier: str
    estimated_import_value: int
    drain_score: int
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "comicvine_volume_id": self.comicvine_volume_id,
            "volume": self.volume_name,
            "publisher": self.publisher,
            "group": self.drain_group,
            "tier": self.tier,
            "core_publisher": self.core_publisher,
            "missing_count": self.missing_issue_count,
            "shell_gap": self.shells_without_catalog,
            "queue_priority": round(self.queue_priority_score, 2),
            "launch_priority_tier": self.launch_priority_tier,
            "estimated_import_value": self.estimated_import_value,
            "drain_score": self.drain_score,
            "reason": self.reason,
        }


@dataclass
class DrainBatchScenario:
    batch_id: str
    label: str
    volume_count: int
    shells_affected: int
    missing_issues_queued: int
    expected_catalog_gain: int
    publisher_mix: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "label": self.label,
            "volume_count": self.volume_count,
            "shells_affected": self.shells_affected,
            "missing_issues_queued": self.missing_issues_queued,
            "expected_catalog_gain": self.expected_catalog_gain,
            "publisher_mix": self.publisher_mix,
        }


@dataclass
class PendingQueueDrainPlan:
    generated_at: str
    summary: dict[str, Any]
    group_counts: list[dict[str, Any]]
    top_volumes: list[PendingQueueDrainRow]
    batches: list[DrainBatchScenario]
    report_answers: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "summary": self.summary,
            "group_counts": self.group_counts,
            "top_volumes": [r.as_dict() for r in self.top_volumes],
            "batches": [b.as_dict() for b in self.batches],
            "report_answers": self.report_answers,
        }


def _publisher_mix(rows: list[PendingQueueDrainRow], limit: int = 15) -> list[dict[str, Any]]:
    by_pub: Counter[str] = Counter()
    shells: Counter[str] = Counter()
    for row in rows:
        pub = row.publisher or "Unknown"
        by_pub[pub] += 1
        shells[pub] += row.shells_without_catalog
    return [
        {"publisher": pub, "volumes": vols, "shells_without_catalog": int(shells[pub])}
        for pub, vols in by_pub.most_common(limit)
    ]


def _build_batch(
    batch_id: str,
    label: str,
    rows: list[PendingQueueDrainRow],
) -> DrainBatchScenario:
    missing = sum(r.missing_issue_count for r in rows)
    shell_gap = sum(r.shells_without_catalog for r in rows)
    gain = sum(r.estimated_import_value for r in rows)
    return DrainBatchScenario(
        batch_id=batch_id,
        label=label,
        volume_count=len(rows),
        shells_affected=shell_gap,
        missing_issues_queued=missing,
        expected_catalog_gain=gain,
        publisher_mix=_publisher_mix(rows),
    )


def build_pending_queue_drain_plan(
    session: Session,
    *,
    top_n: int = 250,
) -> PendingQueueDrainPlan:
    discovered_by_cv = _discovered_shells_by_cv_id(session)
    pending_rows = list(
        session.exec(
            select(P97VolumeIssueImportQueue).where(P97VolumeIssueImportQueue.status == STATUS_PENDING)
        ).all()
    )
    cv_ids = [int(r.comicvine_volume_id) for r in pending_rows]
    start_years = _start_year_by_cv(session, cv_ids)

    scored: list[PendingQueueDrainRow] = []
    group_volume_counts: Counter[str] = Counter()
    group_shell_counts: Counter[str] = Counter()

    for row in pending_rows:
        cv_id = int(row.comicvine_volume_id)
        missing = int(row.missing_issue_count or 0)
        shell_gap = int(discovered_by_cv.get(cv_id, 0))
        group = classify_drain_group(row.publisher, row.name)
        tier_label = classify_publisher_tier(row.publisher)
        tier = tier_number_from_label(tier_label)
        pub_norm = _publisher_norm(row.publisher)
        major = major_publisher_for(pub_norm)
        core = group == GROUP_1_MAJOR_CORE or major is not None
        drain_score = compute_drain_score(
            drain_group=group,
            publisher=row.publisher,
            volume_name=row.name,
            missing_issue_count=missing,
            shells_without_catalog=shell_gap,
            queue_priority_score=float(row.priority_score or 0),
            start_year=start_years.get(cv_id),
        )
        est_value = min(missing, shell_gap) if shell_gap > 0 else missing
        scored.append(
            PendingQueueDrainRow(
                rank=0,
                comicvine_volume_id=cv_id,
                volume_name=row.name,
                publisher=row.publisher,
                drain_group=group,
                tier=tier,
                core_publisher=core,
                missing_issue_count=missing,
                shells_without_catalog=shell_gap,
                queue_priority_score=float(row.priority_score or 0),
                launch_priority_tier=str(row.launch_priority_tier or ""),
                estimated_import_value=est_value,
                drain_score=drain_score,
                reason=_reason_from_row(
                    drain_group=group,
                    core_publisher=core,
                    missing_issue_count=missing,
                    shells_without_catalog=shell_gap,
                    drain_score=drain_score,
                ),
            )
        )
        group_volume_counts[group] += 1
        group_shell_counts[group] += shell_gap if shell_gap > 0 else missing

    scored.sort(key=lambda r: (-r.drain_score, -r.shells_without_catalog, -r.missing_issue_count))
    for idx, row in enumerate(scored, start=1):
        row.rank = idx

    top = scored[: max(1, int(top_n))]
    total_shells_pending = sum(r.shells_without_catalog for r in scored)
    total_missing = sum(r.missing_issue_count for r in scored)

    group_counts = [
        {
            "group": g,
            "pending_rows": int(group_volume_counts.get(g, 0)),
            "shells_without_catalog": int(group_shell_counts.get(g, 0)),
        }
        for g in DRAIN_GROUPS
    ]

    batches = [
        _build_batch("batch_1", "Top 25 pending volumes", scored[:25]),
        _build_batch("batch_2", "Top 100 pending volumes", scored[:100]),
        _build_batch("batch_3", "Top 250 pending volumes", scored[: min(250, len(scored))]),
        _build_batch(
            "batch_4",
            "All GROUP_1_MAJOR_CORE pending",
            [r for r in scored if r.drain_group == GROUP_1_MAJOR_CORE],
        ),
        _build_batch(
            "batch_5",
            "All GROUP_2_LEGACY_US pending",
            [r for r in scored if r.drain_group == GROUP_2_LEGACY_US],
        ),
    ]

    major_rows = sum(1 for r in scored if r.drain_group == GROUP_1_MAJOR_CORE)
    legacy_rows = sum(1 for r in scored if r.drain_group == GROUP_2_LEGACY_US)
    foreign_rows = sum(1 for r in scored if r.drain_group == GROUP_4_FOREIGN_OR_LOW_PRIORITY)

    safest = scored[:25]
    report_answers = {
        "pending_queue_row_count": len(scored),
        "pending_shells_without_catalog_link": total_shells_pending,
        "pending_missing_issues_queued": total_missing,
        "explain_39826_pending": (
            "These are universe shells on volumes with p97_volume_issue_import_queue.status=pending. "
            "Import workers have not yet populated catalog_issue records for these rows."
        ),
        "first_volumes_to_run": [r.as_dict() for r in top[:10]],
        "major_core_pending_rows": major_rows,
        "legacy_us_pending_rows": legacy_rows,
        "foreign_low_priority_pending_rows": foreign_rows,
        "safest_first_import_batch": "batch_1 (top 25 by drain_score: major/core and high shell gap first)",
        "safest_first_batch_volumes": len(safest),
        "safest_first_batch_shell_gap": sum(r.shells_without_catalog for r in safest),
        "safest_first_batch_expected_catalog_gain": sum(r.estimated_import_value for r in safest),
    }

    summary = {
        "pending_queue_rows": len(scored),
        "shells_without_catalog_on_pending_volumes": total_shells_pending,
        "missing_issues_on_pending_rows": total_missing,
        "planning_note": "drain_score is P99 planning only; queue priority_score is unchanged",
    }

    return PendingQueueDrainPlan(
        generated_at=_utc_now_iso(),
        summary=summary,
        group_counts=group_counts,
        top_volumes=top,
        batches=batches,
        report_answers=report_answers,
    )


def save_pending_queue_drain_outputs(
    plan: PendingQueueDrainPlan,
    *,
    plan_path: Path | None = None,
    top_volumes_path: Path | None = None,
    batches_path: Path | None = None,
) -> tuple[Path, Path, Path]:
    pp = plan_path or default_plan_path()
    tv = top_volumes_path or default_top_volumes_path()
    bp = batches_path or default_batches_path()
    for path in (pp, tv, bp):
        path.parent.mkdir(parents=True, exist_ok=True)
    pp.write_text(json.dumps(plan.as_dict(), indent=2), encoding="utf-8")
    tv.write_text(json.dumps([r.as_dict() for r in plan.top_volumes], indent=2), encoding="utf-8")
    bp.write_text(json.dumps([b.as_dict() for b in plan.batches], indent=2), encoding="utf-8")
    return pp, tv, bp
