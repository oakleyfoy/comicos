"""P97 — Volumes discovered in comicvine_volume_universe but not on import queue."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.catalog_p97 import ComicVineVolumeUniverse, P97VolumeIssueImportQueue
from app.models.universe import UniverseIssue, UniverseVolume
from app.services.p97_comicvine_universe_analytics_service import (
    build_catalog_coverage_indexes,
    existing_issue_count_for_volume,
)
from app.services.p97_queue_priority_config import is_core_run
ACTION_ADD_TO_P97_QUEUE = "ADD_TO_P97_QUEUE"
ACTION_REVIEW = "REVIEW_PUBLISHER_MISMATCH"
ACTION_SKIP_COMPLETE = "SKIP_COMPLETE"

HIGHLIGHT_CORE_TITLES: tuple[str, ...] = (
    "Teenage Mutant Ninja Turtles",
    "Flash",
    "Uncanny X-Men",
    "Batman",
    "Detective Comics",
    "Action Comics",
    "Amazing Spider-Man",
    "Spawn",
    "Walking Dead",
    "Invincible",
    "Archie",
)


def _is_highlight(name: str | None) -> bool:
    from app.services.catalog_ingestion_service import normalize_series_name

    norm = normalize_series_name(name or "")
    for title in HIGHLIGHT_CORE_TITLES:
        if norm == normalize_series_name(title) or title.lower() in (name or "").lower():
            return True
    return False


@dataclass
class DiscoveredNotQueuedRow:
    comicvine_volume_id: int
    name: str
    publisher: str | None
    cv_issue_count: int
    catalog_issue_count: int
    missing_issue_count: int
    universe_volume_exists: bool
    universe_issue_shell_count: int
    p97_queue_status: str | None
    recommended_action: str
    highlight_core: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "comicvine_volume_id": self.comicvine_volume_id,
            "name": self.name,
            "publisher": self.publisher,
            "cv_issue_count": self.cv_issue_count,
            "catalog_issue_count": self.catalog_issue_count,
            "missing_issue_count": self.missing_issue_count,
            "universe_volume_exists": self.universe_volume_exists,
            "universe_issue_shell_count": self.universe_issue_shell_count,
            "p97_queue_status": self.p97_queue_status,
            "recommended_action": self.recommended_action,
            "highlight_core": self.highlight_core,
        }


def _universe_issue_counts(session: Session) -> dict[int, int]:
    return {
        int(vid): int(cnt)
        for vid, cnt in session.exec(
            select(UniverseVolume.comicvine_volume_id, func.count(UniverseIssue.id))
            .join(UniverseIssue, UniverseIssue.volume_id == UniverseVolume.id)
            .group_by(UniverseVolume.comicvine_volume_id)
        ).all()
        if vid is not None
    }


def build_discovered_not_queued_audit(
    session: Session,
    *,
    highlights_only: bool = False,
    min_missing: int = 1,
) -> list[DiscoveredNotQueuedRow]:
    indexes = build_catalog_coverage_indexes(session)
    queue_by_id = {
        int(r.comicvine_volume_id): r
        for r in session.exec(select(P97VolumeIssueImportQueue)).all()
    }
    p98_by_cv = {
        int(v.comicvine_volume_id): v
        for v in session.exec(select(UniverseVolume)).all()
    }
    shell_counts = _universe_issue_counts(session)
    rows: list[DiscoveredNotQueuedRow] = []

    for uni in session.exec(select(ComicVineVolumeUniverse)).all():
        volume_id = int(uni.volume_id)
        cv_issues = int(uni.count_of_issues or 0)
        if cv_issues <= 0:
            continue
        catalog = existing_issue_count_for_volume(
            volume_id=volume_id,
            name=uni.name,
            publisher=uni.publisher,
            indexes=indexes,
        )
        missing = max(cv_issues - catalog, 0)
        if missing < int(min_missing):
            continue
        queue = queue_by_id.get(volume_id)
        queue_status = queue.status if queue else None
        active_statuses = ("pending", "running", "failed")
        queued_ok = (
            queue is not None
            and (queue_status or "").lower() in active_statuses
            and int(queue.missing_issue_count or 0) > 0
        )
        if missing > 0 and queued_ok:
            continue
        if missing <= 0:
            continue

        highlight = _is_highlight(uni.name) or is_core_run(uni.name, uni.start_year)
        if highlights_only and not highlight:
            continue

        action = ACTION_ADD_TO_P97_QUEUE

        p98_vol = p98_by_cv.get(volume_id)
        rows.append(
            DiscoveredNotQueuedRow(
                comicvine_volume_id=volume_id,
                name=uni.name,
                publisher=uni.publisher,
                cv_issue_count=cv_issues,
                catalog_issue_count=catalog,
                missing_issue_count=missing,
                universe_volume_exists=p98_vol is not None,
                universe_issue_shell_count=shell_counts.get(volume_id, 0),
                p97_queue_status=queue_status,
                recommended_action=action,
                highlight_core=highlight,
            )
        )

    rows.sort(key=lambda r: (not r.highlight_core, -r.missing_issue_count, r.name))
    return rows
