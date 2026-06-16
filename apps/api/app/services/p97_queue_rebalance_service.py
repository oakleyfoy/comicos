"""Rebalance P97 volume issue import queue toward collector-first ordering."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.catalog_p97 import ComicVineVolumeUniverse, P97VolumeIssueImportQueue
from app.services.p97_queue_priority_config import compute_collector_queue_score, is_core_run
from app.services.p97_volume_issue_import_queue_service import (
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_RUNNING,
)
from app.services.p97_volume_issue_queue_priority import (
    TIER_0_MANUAL,
    is_foreign_anthology_title,
)

REBALANCE_STATUSES = (STATUS_PENDING, STATUS_RUNNING, STATUS_FAILED)
APPLY_STATUSES = (STATUS_PENDING, STATUS_FAILED)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _force_foreign_archive(*, publisher: str | None, name: str | None) -> bool:
    return is_foreign_anthology_title(name)


def compute_rebalance_score_for_row(
    row: P97VolumeIssueImportQueue,
    *,
    start_year: int | None = None,
) -> float:
    return compute_collector_queue_score(
        publisher=row.publisher,
        name=row.name,
        missing_issue_count=int(row.missing_issue_count or 0),
        total_issue_count=int(row.count_of_issues or 0),
        start_year=start_year,
        force_foreign_archive=_force_foreign_archive(
            publisher=row.publisher, name=row.name
        ),
    )


def _load_start_years(session: Session, volume_ids: list[int]) -> dict[int, int | None]:
    if not volume_ids:
        return {}
    rows = session.exec(
        select(ComicVineVolumeUniverse.volume_id, ComicVineVolumeUniverse.start_year).where(
            ComicVineVolumeUniverse.volume_id.in_(volume_ids)
        )
    ).all()
    return {int(vid): (int(sy) if sy is not None else None) for vid, sy in rows}


def _rank_rows(
    rows: list[P97VolumeIssueImportQueue],
    scores: dict[int, float],
) -> list[tuple[int, P97VolumeIssueImportQueue, float]]:
    ordered = sorted(
        rows,
        key=lambda r: (
            -scores[int(r.comicvine_volume_id)],
            -int(r.missing_issue_count or 0),
            int(r.comicvine_volume_id),
        ),
    )
    return [(idx + 1, row, scores[int(row.comicvine_volume_id)]) for idx, row in enumerate(ordered)]


@dataclass(frozen=True)
class QueueVolumeRank:
    rank: int
    comicvine_volume_id: int
    name: str
    publisher: str | None
    missing_issue_count: int
    run_size: int
    is_core_run: bool
    priority_score: float
    rebalance_score: float | None = None


@dataclass(frozen=True)
class CoreRunVolumeRank:
    rank: int
    name: str
    publisher: str | None
    missing_issue_count: int
    run_size: int
    score: float


@dataclass(frozen=True)
class CoverageVolumeRank:
    name: str
    publisher: str | None
    missing_issue_count: int
    run_size: int
    score: float


@dataclass(frozen=True)
class CoverageMovement:
    name: str
    publisher: str | None
    missing_issue_count: int
    old_rank: int
    new_rank: int
    rank_delta: int


@dataclass(frozen=True)
class RankMovement:
    name: str
    publisher: str | None
    old_rank: int
    new_rank: int
    rank_delta: int


@dataclass
class RebalanceComparisonReport:
    eligible_row_count: int
    current_top_100: list[QueueVolumeRank] = field(default_factory=list)
    rebalanced_top_100: list[QueueVolumeRank] = field(default_factory=list)
    largest_movers_up: list[RankMovement] = field(default_factory=list)
    largest_movers_down: list[RankMovement] = field(default_factory=list)
    current_top_100_publisher_distribution: dict[str, int] = field(default_factory=dict)
    rebalanced_top_100_publisher_distribution: dict[str, int] = field(default_factory=dict)
    top_core_runs: list[CoreRunVolumeRank] = field(default_factory=list)
    core_runs_before: list[CoreRunVolumeRank] = field(default_factory=list)
    core_runs_after: list[CoreRunVolumeRank] = field(default_factory=list)
    top_coverage_opportunities: list[CoverageVolumeRank] = field(default_factory=list)
    largest_coverage_movers: list[CoverageMovement] = field(default_factory=list)
    coverage_gain_potential: int = 0


def _publisher_label(publisher: str | None) -> str:
    return (publisher or "Unknown").strip() or "Unknown"


def _publisher_distribution(ranked: list[QueueVolumeRank], *, limit: int = 100) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for entry in ranked[:limit]:
        counts[_publisher_label(entry.publisher)] += 1
    return dict(counts.most_common())


def _is_core_row(row: P97VolumeIssueImportQueue, start_years: dict[int, int | None]) -> bool:
    return is_core_run(row.name, start_years.get(int(row.comicvine_volume_id)))


def _queue_volume_rank(
    rank: int,
    row: P97VolumeIssueImportQueue,
    *,
    priority_score: float,
    rebalance_score: float | None,
    start_years: dict[int, int | None],
) -> QueueVolumeRank:
    return QueueVolumeRank(
        rank=rank,
        comicvine_volume_id=int(row.comicvine_volume_id),
        name=row.name,
        publisher=row.publisher,
        missing_issue_count=int(row.missing_issue_count or 0),
        run_size=int(row.count_of_issues or 0),
        is_core_run=_is_core_row(row, start_years),
        priority_score=priority_score,
        rebalance_score=rebalance_score,
    )


def _core_run_rank_list(
    ranked: list[tuple[int, P97VolumeIssueImportQueue, float]],
    start_years: dict[int, int | None],
    *,
    limit: int = 30,
) -> list[CoreRunVolumeRank]:
    entries: list[CoreRunVolumeRank] = []
    for rank, row, score in ranked:
        if not _is_core_row(row, start_years):
            continue
        entries.append(
            CoreRunVolumeRank(
                rank=rank,
                name=row.name,
                publisher=row.publisher,
                missing_issue_count=int(row.missing_issue_count or 0),
                run_size=int(row.count_of_issues or 0),
                score=score,
            )
        )
        if len(entries) >= limit:
            break
    return entries


def _coverage_opportunities(
    rows: list[P97VolumeIssueImportQueue],
    scores: dict[int, float],
    *,
    limit: int = 30,
) -> list[CoverageVolumeRank]:
    ordered = sorted(
        rows,
        key=lambda r: (
            -int(r.missing_issue_count or 0),
            -scores[int(r.comicvine_volume_id)],
            int(r.comicvine_volume_id),
        ),
    )
    result: list[CoverageVolumeRank] = []
    for row in ordered[:limit]:
        vid = int(row.comicvine_volume_id)
        result.append(
            CoverageVolumeRank(
                name=row.name,
                publisher=row.publisher,
                missing_issue_count=int(row.missing_issue_count or 0),
                run_size=int(row.count_of_issues or 0),
                score=scores[vid],
            )
        )
    return result


def build_rebalance_comparison(session: Session) -> RebalanceComparisonReport:
    rows = list(
        session.exec(
            select(P97VolumeIssueImportQueue).where(
                P97VolumeIssueImportQueue.status.in_(REBALANCE_STATUSES)
            )
        ).all()
    )
    volume_ids = [int(r.comicvine_volume_id) for r in rows]
    start_years = _load_start_years(session, volume_ids)

    current_scores = {int(r.comicvine_volume_id): float(r.priority_score or 0.0) for r in rows}
    new_scores = {
        int(r.comicvine_volume_id): compute_rebalance_score_for_row(
            r, start_year=start_years.get(int(r.comicvine_volume_id))
        )
        for r in rows
    }

    current_ranked = _rank_rows(rows, current_scores)
    new_ranked = _rank_rows(rows, new_scores)

    old_rank_by_volume: dict[int, int] = {
        int(row.comicvine_volume_id): rank for rank, row, _ in current_ranked
    }
    new_rank_by_volume: dict[int, int] = {
        int(row.comicvine_volume_id): rank for rank, row, _ in new_ranked
    }

    report = RebalanceComparisonReport(eligible_row_count=len(rows))

    for rank, row, score in current_ranked[:100]:
        vid = int(row.comicvine_volume_id)
        report.current_top_100.append(
            _queue_volume_rank(
                rank,
                row,
                priority_score=score,
                rebalance_score=new_scores.get(vid),
                start_years=start_years,
            )
        )

    for rank, row, score in new_ranked[:100]:
        report.rebalanced_top_100.append(
            _queue_volume_rank(
                rank,
                row,
                priority_score=current_scores.get(int(row.comicvine_volume_id), 0.0),
                rebalance_score=score,
                start_years=start_years,
            )
        )

    movements: list[RankMovement] = []
    coverage_movements: list[CoverageMovement] = []
    for row in rows:
        vid = int(row.comicvine_volume_id)
        old_rank = old_rank_by_volume[vid]
        new_rank = new_rank_by_volume[vid]
        delta = old_rank - new_rank
        if delta == 0:
            continue
        movements.append(
            RankMovement(
                name=row.name,
                publisher=row.publisher,
                old_rank=old_rank,
                new_rank=new_rank,
                rank_delta=delta,
            )
        )
        if delta > 0:
            coverage_movements.append(
                CoverageMovement(
                    name=row.name,
                    publisher=row.publisher,
                    missing_issue_count=int(row.missing_issue_count or 0),
                    old_rank=old_rank,
                    new_rank=new_rank,
                    rank_delta=delta,
                )
            )

    movements.sort(key=lambda m: (-m.rank_delta, m.name))
    report.largest_movers_up = movements[:25]
    movements.sort(key=lambda m: (m.rank_delta, m.name))
    report.largest_movers_down = movements[:25]

    coverage_movements.sort(
        key=lambda m: (-m.missing_issue_count, -m.rank_delta, m.name)
    )
    report.largest_coverage_movers = coverage_movements[:25]

    report.current_top_100_publisher_distribution = _publisher_distribution(
        report.current_top_100
    )
    report.rebalanced_top_100_publisher_distribution = _publisher_distribution(
        report.rebalanced_top_100
    )
    report.top_core_runs = _core_run_rank_list(new_ranked, start_years, limit=30)
    report.core_runs_before = _core_run_rank_list(current_ranked, start_years, limit=30)
    report.core_runs_after = report.top_core_runs
    report.top_coverage_opportunities = _coverage_opportunities(rows, new_scores, limit=30)
    report.coverage_gain_potential = sum(
        entry.missing_issue_count for entry in report.top_coverage_opportunities
    )
    return report


@dataclass
class ApplyRebalanceResult:
    dry_run: bool
    rows_considered: int
    rows_updated: int
    rows_skipped_manual: int
    row_count_before: int
    row_count_after: int


def apply_queue_rebalance(session: Session, *, dry_run: bool = True) -> ApplyRebalanceResult:
    row_count_before = int(
        session.exec(select(func.count()).select_from(P97VolumeIssueImportQueue)).one()
    )
    rows = list(
        session.exec(
            select(P97VolumeIssueImportQueue).where(
                P97VolumeIssueImportQueue.status.in_(APPLY_STATUSES)
            )
        ).all()
    )
    volume_ids = [int(r.comicvine_volume_id) for r in rows]
    start_years = _load_start_years(session, volume_ids)

    updated = 0
    skipped_manual = 0
    for row in rows:
        if row.launch_priority_tier == TIER_0_MANUAL:
            skipped_manual += 1
            continue
        new_score = compute_rebalance_score_for_row(
            row, start_year=start_years.get(int(row.comicvine_volume_id))
        )
        if float(row.priority_score or 0.0) == new_score:
            continue
        if not dry_run:
            row.priority_score = new_score
            row.updated_at = _utc_now()
            session.add(row)
        updated += 1

    if not dry_run and updated:
        session.commit()

    row_count_after = int(
        session.exec(select(func.count()).select_from(P97VolumeIssueImportQueue)).one()
    )
    return ApplyRebalanceResult(
        dry_run=dry_run,
        rows_considered=len(rows),
        rows_updated=updated,
        rows_skipped_manual=skipped_manual,
        row_count_before=row_count_before,
        row_count_after=row_count_after,
    )
