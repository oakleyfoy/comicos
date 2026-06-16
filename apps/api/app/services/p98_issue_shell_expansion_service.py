"""P98 — Expand VOLUME_ONLY / BUILD_ISSUE_SHELLS volumes from discovered metadata.

Uses ``comicvine_volume_universe.count_of_issues`` (and universe_volume fallback)
to synthesize issue numbers 1..N with UNKNOWN variant shells. No ComicVine API
calls, no catalog import, no acquisition/inventory changes.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.catalog_p97 import ComicVineVolumeUniverse
from app.models.universe import (
    UNIVERSE_ISSUE_STATUS_CATALOGED,
    UniverseIssue,
    UniverseVariant,
    UniverseVolume,
)
from app.services.catalog_ingestion_service import normalize_issue_number
from app.services.p98_gap_priority_service import MAJOR_PUBLISHERS, resolve_requested_publisher
from app.services.p98_skeleton_gap_service import (
    ACTION_BUILD_SHELLS,
    STATUS_CATALOG_COMPLETE,
    build_action_queue,
    classify_volume,
)
from app.services.universe.universe_issue_service import (
    VOLUME_STATUS_BUILT,
    VOLUME_STATUS_VOLUME_ONLY,
    _ensure_default_variant,
    upsert_issue_shell,
)

VOLUME_STATUS_SHELL_ONLY = "SHELL_ONLY"
DEFAULT_QUEUE_REL = Path("data/p98/major_publisher_action_queue.json")
DEFAULT_PROGRESS_REL = Path("data/p98/issue_shell_expansion_progress.json")

PUBLISHER_EXPANSION_ORDER: tuple[str, ...] = tuple(p.canonical for p in MAJOR_PUBLISHERS)


def _api_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_queue_path() -> Path:
    return _api_root() / DEFAULT_QUEUE_REL


def default_progress_path() -> Path:
    return _api_root() / DEFAULT_PROGRESS_REL


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _publisher_rank(publisher_label: str) -> int:
    needle = (publisher_label or "").strip().lower()
    for idx, canonical in enumerate(PUBLISHER_EXPANSION_ORDER):
        if needle == canonical.lower():
            return idx
    return len(PUBLISHER_EXPANSION_ORDER) + 1


@dataclass
class ExpansionCandidate:
    comicvine_volume_id: int
    universe_volume_id: int
    publisher: str
    volume_name: str
    expected_issue_count: int
    existing_issue_count: int
    priority_score: int

    @property
    def missing_to_generate(self) -> int:
        return max(self.expected_issue_count - self.existing_issue_count, 0)


@dataclass
class ExpansionStats:
    volumes_selected: int = 0
    volumes_expanded: int = 0
    volumes_skipped: int = 0
    volumes_failed: int = 0
    issues_created: int = 0
    variants_created: int = 0
    failed_comicvine_volume_ids: list[int] = field(default_factory=list)
    by_publisher: dict[str, dict[str, int]] = field(default_factory=dict)
    started_at: float = field(default_factory=time.monotonic)

    @property
    def elapsed_seconds(self) -> float:
        return time.monotonic() - self.started_at

    def bump_publisher(self, publisher: str, *, volumes: int = 0, issues: int = 0, variants: int = 0) -> None:
        bucket = self.by_publisher.setdefault(
            publisher, {"volumes_expanded": 0, "issues_created": 0, "variants_created": 0}
        )
        bucket["volumes_expanded"] += volumes
        bucket["issues_created"] += issues
        bucket["variants_created"] += variants

    def as_dict(self) -> dict:
        return {
            "volumes_selected": self.volumes_selected,
            "volumes_expanded": self.volumes_expanded,
            "volumes_skipped": self.volumes_skipped,
            "volumes_failed": self.volumes_failed,
            "issues_created": self.issues_created,
            "variants_created": self.variants_created,
            "failed_comicvine_volume_ids": list(self.failed_comicvine_volume_ids),
            "by_publisher": dict(self.by_publisher),
            "elapsed_seconds": round(self.elapsed_seconds, 2),
        }


@dataclass
class ExpansionReport:
    current_issues: int
    current_variants: int
    remaining_build_shells_volumes: int
    projected_issue_total: int
    projected_gain: int
    by_publisher_remaining: dict[str, int]
    by_publisher_projected_gain: dict[str, int]

    def as_dict(self) -> dict:
        return {
            "current_issues": self.current_issues,
            "current_variants": self.current_variants,
            "remaining_build_shells_volumes": self.remaining_build_shells_volumes,
            "projected_issue_total": self.projected_issue_total,
            "projected_gain": self.projected_gain,
            "by_publisher_remaining": dict(self.by_publisher_remaining),
            "by_publisher_projected_gain": dict(self.by_publisher_projected_gain),
        }


def load_action_queue_file(path: Path | None = None) -> list[dict]:
    queue_path = path or default_queue_path()
    if not queue_path.is_file():
        return []
    with open(queue_path, encoding="utf-8") as fh:
        data = json.load(fh)
    return data if isinstance(data, list) else []


def _expected_issue_count(
    session: Session,
    *,
    comicvine_volume_id: int,
    volume: UniverseVolume | None,
) -> int:
    row = session.exec(
        select(ComicVineVolumeUniverse).where(ComicVineVolumeUniverse.volume_id == comicvine_volume_id)
    ).first()
    if row is not None and row.count_of_issues is not None and int(row.count_of_issues) > 0:
        return int(row.count_of_issues)
    if volume is not None and volume.count_of_issues is not None and int(volume.count_of_issues) > 0:
        return int(volume.count_of_issues)
    return 0


def _existing_issue_count(session: Session, volume_id: int) -> int:
    return int(
        session.exec(
            select(func.count())
            .select_from(UniverseIssue)
            .where(UniverseIssue.volume_id == volume_id)
        ).one()
    )


def _catalog_linked_count(session: Session, volume_id: int) -> int:
    return int(
        session.exec(
            select(func.count())
            .select_from(UniverseIssue)
            .where(
                UniverseIssue.volume_id == volume_id,
                UniverseIssue.status == UNIVERSE_ISSUE_STATUS_CATALOGED,
            )
        ).one()
    )


def _volume_by_cv_id(session: Session, comicvine_volume_id: int) -> UniverseVolume | None:
    return session.exec(
        select(UniverseVolume).where(UniverseVolume.comicvine_volume_id == comicvine_volume_id)
    ).first()


def _sort_queue_rows(rows: list[dict]) -> list[dict]:
    build_rows = [r for r in rows if r.get("recommended_action") == ACTION_BUILD_SHELLS]
    build_rows.sort(
        key=lambda r: (
            _publisher_rank(str(r.get("publisher") or "")),
            -int(r.get("priority_score") or 0),
            int(r.get("comicvine_volume_id") or 0),
        )
    )
    return build_rows


def get_volume_expansion_candidates(
    session: Session,
    *,
    publisher: str | None = None,
    top: int | None = None,
    limit_volumes: int | None = None,
    queue_path: Path | None = None,
    use_live_gap_queue: bool = False,
) -> list[ExpansionCandidate]:
    """BUILD_ISSUE_SHELLS volumes ordered by major-publisher priority then score."""
    if use_live_gap_queue or not load_action_queue_file(queue_path):
        rows = build_action_queue(session, publisher=publisher)
        rows = [r for r in rows if r.get("recommended_action") == ACTION_BUILD_SHELLS]
        rows.sort(
            key=lambda r: (
                _publisher_rank(str(r.get("publisher") or "")),
                -int(r.get("priority_score") or 0),
                int(r.get("comicvine_volume_id") or 0),
            )
        )
    else:
        rows = _sort_queue_rows(load_action_queue_file(queue_path))
        if publisher and publisher.strip():
            entry = resolve_requested_publisher(publisher)
            if entry is not None:
                canon = entry.canonical.lower()
                rows = [r for r in rows if str(r.get("publisher") or "").lower().startswith(canon.lower())]
            else:
                needle = publisher.strip().lower()
                rows = [r for r in rows if needle in str(r.get("publisher") or "").lower()]

    cap = limit_volumes if limit_volumes is not None else top
    if cap is not None and cap > 0:
        rows = rows[: int(cap)]

    candidates: list[ExpansionCandidate] = []
    for row in rows:
        cv_id = int(row.get("comicvine_volume_id") or 0)
        if cv_id <= 0:
            continue
        volume = _volume_by_cv_id(session, cv_id)
        if volume is None:
            continue
        vid = int(volume.id or 0)
        expected = _expected_issue_count(session, comicvine_volume_id=cv_id, volume=volume)
        existing = _existing_issue_count(session, vid)
        candidates.append(
            ExpansionCandidate(
                comicvine_volume_id=cv_id,
                universe_volume_id=vid,
                publisher=str(row.get("publisher") or "Unknown"),
                volume_name=str(row.get("volume") or volume.name),
                expected_issue_count=expected,
                existing_issue_count=existing,
                priority_score=int(row.get("priority_score") or 0),
            )
        )
    return candidates


def _issue_numbers_for_range(expected_count: int) -> list[str]:
    return [str(n) for n in range(1, expected_count + 1)]


def _refresh_volume_status(session: Session, volume: UniverseVolume) -> None:
    vid = int(volume.id or 0)
    universe_count = _existing_issue_count(session, vid)
    catalog_count = _catalog_linked_count(session, vid)
    status = classify_volume(universe_count, catalog_count)
    if status == STATUS_CATALOG_COMPLETE:
        volume.volume_status = VOLUME_STATUS_BUILT
    elif universe_count > 0:
        volume.volume_status = VOLUME_STATUS_SHELL_ONLY
    else:
        volume.volume_status = VOLUME_STATUS_VOLUME_ONLY
    volume.updated_at = _utc_now()
    session.add(volume)


def expand_volume_issue_shells(
    session: Session,
    *,
    volume: UniverseVolume,
    expected_issue_count: int,
    stats: ExpansionStats,
    publisher_label: str,
) -> int:
    """Create missing issue shells 1..expected_issue_count. Returns issues created."""
    if expected_issue_count <= 0:
        return 0
    vid = int(volume.id or 0)
    existing_norms = {
        row
        for row in session.exec(
            select(UniverseIssue.normalized_issue_number).where(UniverseIssue.volume_id == vid)
        ).all()
        if row
    }
    created = 0
    for issue_number in _issue_numbers_for_range(expected_issue_count):
        norm = normalize_issue_number(issue_number)
        if not norm or norm in existing_norms:
            continue
        existing_issue = session.exec(
            select(UniverseIssue).where(
                UniverseIssue.volume_id == vid,
                UniverseIssue.normalized_issue_number == norm,
            )
        ).first()
        had_variant = False
        if existing_issue is not None:
            had_variant = (
                session.exec(
                    select(UniverseVariant.id).where(
                        UniverseVariant.issue_id == int(existing_issue.id or 0),
                        UniverseVariant.variant_type == "UNKNOWN",
                        UniverseVariant.variant_name == "",
                    )
                ).first()
                is not None
            )
        shell = upsert_issue_shell(
            session,
            volume=volume,
            issue_number=issue_number,
            issue_title=None,
            cover_date=None,
            comicvine_issue_id=None,
            catalog_issue_id=None,
        )
        existing_norms.add(norm)
        if existing_issue is None:
            stats.issues_created += 1
            stats.variants_created += 1
            created += 1
        elif not had_variant:
            _variant, variant_created = _ensure_default_variant(session, shell)
            if variant_created:
                stats.variants_created += 1
    _refresh_volume_status(session, volume)
    if created > 0:
        stats.bump_publisher(publisher_label, volumes=1, issues=created, variants=0)
    return created


def expand_publisher_issue_shells(
    session: Session,
    *,
    publisher: str,
    stats: ExpansionStats,
    top: int | None = None,
    limit_volumes: int | None = None,
    queue_path: Path | None = None,
    skip_if_complete: bool = True,
) -> list[ExpansionCandidate]:
    candidates = get_volume_expansion_candidates(
        session,
        publisher=publisher,
        top=top,
        limit_volumes=limit_volumes,
        queue_path=queue_path,
    )
    stats.volumes_selected += len(candidates)
    for cand in candidates:
        volume = session.get(UniverseVolume, cand.universe_volume_id)
        if volume is None:
            stats.volumes_failed += 1
            stats.failed_comicvine_volume_ids.append(cand.comicvine_volume_id)
            continue
        if skip_if_complete and cand.existing_issue_count >= cand.expected_issue_count > 0:
            stats.volumes_skipped += 1
            continue
        if cand.expected_issue_count <= 0:
            stats.volumes_skipped += 1
            continue
        before_issues = stats.issues_created
        expand_volume_issue_shells(
            session,
            volume=volume,
            expected_issue_count=cand.expected_issue_count,
            stats=stats,
            publisher_label=cand.publisher,
        )
        if stats.issues_created > before_issues:
            stats.volumes_expanded += 1
        else:
            stats.volumes_skipped += 1
    return candidates


def load_progress(path: Path | None = None) -> dict:
    progress_path = path or default_progress_path()
    if not progress_path.is_file():
        return {
            "last_updated": None,
            "resume_after_comicvine_volume_id": None,
            "totals": {"volumes_completed": 0, "issues_created": 0, "variants_created": 0},
            "by_publisher": {},
            "completed_comicvine_volume_ids": [],
        }
    with open(progress_path, encoding="utf-8") as fh:
        return json.load(fh)


def save_progress(progress: dict, path: Path | None = None) -> None:
    progress_path = path or default_progress_path()
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    progress["last_updated"] = _utc_now().isoformat()
    with open(progress_path, "w", encoding="utf-8") as fh:
        json.dump(progress, fh, indent=2)


def merge_stats_into_progress(progress: dict, stats: ExpansionStats, *, last_cv_id: int | None) -> None:
    totals = progress.setdefault("totals", {"volumes_completed": 0, "issues_created": 0, "variants_created": 0})
    totals["volumes_completed"] = int(totals.get("volumes_completed", 0)) + stats.volumes_expanded
    totals["issues_created"] = int(totals.get("issues_created", 0)) + stats.issues_created
    totals["variants_created"] = int(totals.get("variants_created", 0)) + stats.variants_created
    by_pub = progress.setdefault("by_publisher", {})
    for pub, bucket in stats.by_publisher.items():
        row = by_pub.setdefault(pub, {"volumes": 0, "issues": 0, "variants": 0})
        row["volumes"] = int(row.get("volumes", 0)) + int(bucket.get("volumes_expanded", 0))
        row["issues"] = int(row.get("issues", 0)) + int(bucket.get("issues_created", 0))
        row["variants"] = int(row.get("variants", 0)) + int(bucket.get("variants_created", 0))
    if last_cv_id is not None:
        progress["resume_after_comicvine_volume_id"] = last_cv_id
        done = progress.setdefault("completed_comicvine_volume_ids", [])
        if last_cv_id not in done:
            done.append(last_cv_id)


def expand_action_queue(
    session: Session,
    *,
    publisher: str | None = None,
    top: int | None = None,
    limit_volumes: int | None = None,
    queue_path: Path | None = None,
    progress_path: Path | None = None,
    commit_every: int = 10,
    dry_run: bool = True,
    resume_from_progress: bool = True,
    progress_callback: Callable[[ExpansionStats, ExpansionCandidate], None] | None = None,
) -> ExpansionStats:
    stats = ExpansionStats()
    progress = load_progress(progress_path)
    completed_ids: set[int] = set()
    if resume_from_progress:
        completed_ids = {int(x) for x in progress.get("completed_comicvine_volume_ids", [])}

    candidates = get_volume_expansion_candidates(
        session,
        publisher=publisher,
        top=top,
        limit_volumes=limit_volumes,
        queue_path=queue_path,
    )
    if resume_from_progress and completed_ids:
        candidates = [c for c in candidates if c.comicvine_volume_id not in completed_ids]

    stats.volumes_selected = len(candidates)
    commit_every = max(1, int(commit_every))
    pending = 0
    last_cv: int | None = None
    flush_issues = 0
    flush_variants = 0
    flush_volumes = 0
    flush_by_pub: dict[str, dict[str, int]] = {}

    def _flush_progress() -> None:
        nonlocal flush_issues, flush_variants, flush_volumes, flush_by_pub
        if flush_volumes <= 0 and flush_issues <= 0 and flush_variants <= 0:
            return
        batch_stats = ExpansionStats()
        batch_stats.volumes_expanded = flush_volumes
        batch_stats.issues_created = flush_issues
        batch_stats.variants_created = flush_variants
        batch_stats.by_publisher = {
            k: {
                "volumes_expanded": v.get("volumes_expanded", 0),
                "issues_created": v.get("issues_created", 0),
                "variants_created": v.get("variants_created", 0),
            }
            for k, v in flush_by_pub.items()
        }
        merge_stats_into_progress(progress, batch_stats, last_cv_id=last_cv)
        save_progress(progress, progress_path)
        flush_issues = 0
        flush_variants = 0
        flush_volumes = 0
        flush_by_pub = {}

    for cand in candidates:
        volume = session.get(UniverseVolume, cand.universe_volume_id)
        if volume is None:
            stats.volumes_failed += 1
            stats.failed_comicvine_volume_ids.append(cand.comicvine_volume_id)
            continue
        if cand.expected_issue_count <= 0:
            stats.volumes_skipped += 1
            continue
        if cand.existing_issue_count >= cand.expected_issue_count:
            stats.volumes_skipped += 1
            if resume_from_progress and not dry_run:
                completed_ids.add(cand.comicvine_volume_id)
            continue

        issues_before = stats.issues_created
        variants_before = stats.variants_created
        try:
            nested = session.begin_nested()
            try:
                expand_volume_issue_shells(
                    session,
                    volume=volume,
                    expected_issue_count=cand.expected_issue_count,
                    stats=stats,
                    publisher_label=cand.publisher,
                )
                if dry_run:
                    nested.rollback()
                else:
                    nested.commit()
            except Exception:
                nested.rollback()
                raise
        except Exception:  # noqa: BLE001
            stats.volumes_failed += 1
            stats.failed_comicvine_volume_ids.append(cand.comicvine_volume_id)
            if progress_callback:
                progress_callback(stats, cand)
            continue

        delta_issues = stats.issues_created - issues_before
        delta_variants = stats.variants_created - variants_before
        if dry_run:
            stats.issues_created = issues_before
            stats.variants_created = variants_before
            if progress_callback:
                progress_callback(stats, cand)
            continue

        if delta_issues > 0:
            stats.volumes_expanded += 1
        else:
            stats.volumes_skipped += 1

        if delta_issues > 0:
            flush_volumes += 1
            flush_issues += delta_issues
            flush_variants += delta_variants
            pub_bucket = flush_by_pub.setdefault(
                cand.publisher,
                {"volumes_expanded": 0, "issues_created": 0, "variants_created": 0},
            )
            pub_bucket["volumes_expanded"] += 1
            pub_bucket["issues_created"] += delta_issues
            pub_bucket["variants_created"] += delta_variants

        pending += 1
        last_cv = cand.comicvine_volume_id
        if resume_from_progress:
            completed_ids.add(cand.comicvine_volume_id)
            done = progress.setdefault("completed_comicvine_volume_ids", [])
            if cand.comicvine_volume_id not in done:
                done.append(cand.comicvine_volume_id)
        if pending >= commit_every:
            session.commit()
            _flush_progress()
            pending = 0

        if progress_callback:
            progress_callback(stats, cand)

    if dry_run:
        session.rollback()
    elif pending > 0:
        session.commit()
        _flush_progress()

    return stats


def build_expansion_report(session: Session, *, queue_path: Path | None = None) -> ExpansionReport:
    current_issues = int(session.exec(select(func.count()).select_from(UniverseIssue)).one())
    current_variants = int(session.exec(select(func.count()).select_from(UniverseVariant)).one())

    rows = _sort_queue_rows(load_action_queue_file(queue_path))
    if not rows:
        rows = [r for r in build_action_queue(session) if r.get("recommended_action") == ACTION_BUILD_SHELLS]

    remaining = 0
    projected_gain = 0
    by_pub_remaining: dict[str, int] = {}
    by_pub_gain: dict[str, int] = {}

    for row in rows:
        cv_id = int(row.get("comicvine_volume_id") or 0)
        volume = _volume_by_cv_id(session, cv_id)
        if volume is None:
            continue
        expected = _expected_issue_count(session, comicvine_volume_id=cv_id, volume=volume)
        existing = _existing_issue_count(session, int(volume.id or 0))
        if existing >= expected > 0:
            continue
        remaining += 1
        gain = max(expected - existing, 0)
        projected_gain += gain
        pub = str(row.get("publisher") or "Unknown")
        by_pub_remaining[pub] = by_pub_remaining.get(pub, 0) + 1
        by_pub_gain[pub] = by_pub_gain.get(pub, 0) + gain

    return ExpansionReport(
        current_issues=current_issues,
        current_variants=current_variants,
        remaining_build_shells_volumes=remaining,
        projected_issue_total=current_issues + projected_gain,
        projected_gain=projected_gain,
        by_publisher_remaining=by_pub_remaining,
        by_publisher_projected_gain=by_pub_gain,
    )
