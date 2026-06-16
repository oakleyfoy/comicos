"""P98 — Major publisher gap analysis over the master universe skeleton.

Read-only reporting layer. It classifies every ``universe_volume`` by catalog
coverage and computes publisher-level gap metrics + priority. It does NOT:
import metadata, call ComicVine, modify acquisitions/inventory, or delete rows.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.universe import (
    UNIVERSE_ISSUE_STATUS_CATALOGED,
    UniverseIssue,
    UniversePublisher,
    UniverseVolume,
)
from app.services.p98_gap_priority_service import (
    MajorPublisher,
    major_publisher_for,
    resolve_requested_publisher,
    score_volume,
)

# Volume classification constants
STATUS_CATALOG_COMPLETE = "CATALOG_COMPLETE"
STATUS_CATALOG_PARTIAL = "CATALOG_PARTIAL"
STATUS_SHELL_ONLY = "SHELL_ONLY"
STATUS_VOLUME_ONLY = "VOLUME_ONLY"
STATUS_UNKNOWN = "UNKNOWN"

# Recommended actions
ACTION_READY = "READY_FOR_ACQUISITION_TREE"
ACTION_IMPORT = "IMPORT_CATALOG_METADATA"
ACTION_BUILD_SHELLS = "BUILD_ISSUE_SHELLS"
ACTION_DISCOVERY = "TARGET_DISCOVERY_REQUIRED"


def classify_volume(universe_issue_count: int, catalog_issue_count: int) -> str:
    if universe_issue_count <= 0:
        return STATUS_VOLUME_ONLY
    if catalog_issue_count <= 0:
        return STATUS_SHELL_ONLY
    if catalog_issue_count >= universe_issue_count:
        return STATUS_CATALOG_COMPLETE
    if catalog_issue_count > 0:
        return STATUS_CATALOG_PARTIAL
    return STATUS_UNKNOWN


def recommended_action(status: str) -> str:
    if status == STATUS_VOLUME_ONLY:
        return ACTION_BUILD_SHELLS
    if status in (STATUS_SHELL_ONLY, STATUS_CATALOG_PARTIAL):
        return ACTION_IMPORT
    if status == STATUS_CATALOG_COMPLETE:
        return ACTION_READY
    return ACTION_DISCOVERY


@dataclass
class VolumeGapRow:
    universe_volume_id: int
    comicvine_volume_id: int
    publisher_name: str
    publisher_normalized: str
    volume_name: str
    start_year: int | None
    expected_issue_count: int
    universe_issue_count: int
    catalog_issue_count: int
    missing_issue_count: int
    status: str
    recommended_action: str
    priority_score: int

    def as_dict(self) -> dict:
        return {
            "publisher": self.publisher_name,
            "volume": self.volume_name,
            "comicvine_volume_id": self.comicvine_volume_id,
            "start_year": self.start_year,
            "status": self.status,
            "universe_issue_count": self.universe_issue_count,
            "catalog_issue_count": self.catalog_issue_count,
            "missing_issue_count": self.missing_issue_count,
            "recommended_action": self.recommended_action,
            "priority_score": self.priority_score,
        }


@dataclass
class PublisherGapSummary:
    publisher: str
    universe_volumes: int = 0
    catalog_complete: int = 0
    catalog_partial: int = 0
    shell_only: int = 0
    volume_only: int = 0
    unknown: int = 0
    universe_issues: int = 0
    catalog_linked_issues: int = 0
    discovered_only_issues: int = 0
    expected_issues: int = 0

    @property
    def coverage_percent(self) -> float:
        if self.universe_issues <= 0:
            return 0.0
        return round(100.0 * self.catalog_linked_issues / self.universe_issues, 2)

    @property
    def shell_coverage_percent(self) -> float:
        denom = max(self.expected_issues, self.universe_issues)
        if denom <= 0:
            return 0.0
        return round(100.0 * self.universe_issues / denom, 2)

    @property
    def volume_coverage_percent(self) -> float:
        if self.universe_volumes <= 0:
            return 0.0
        with_issues = self.universe_volumes - self.volume_only
        return round(100.0 * with_issues / self.universe_volumes, 2)

    def as_dict(self) -> dict:
        return {
            "publisher": self.publisher,
            "universe_volumes": self.universe_volumes,
            "catalog_complete": self.catalog_complete,
            "catalog_partial": self.catalog_partial,
            "shell_only": self.shell_only,
            "volume_only": self.volume_only,
            "unknown": self.unknown,
            "universe_issues": self.universe_issues,
            "catalog_linked_issues": self.catalog_linked_issues,
            "discovered_only_issues": self.discovered_only_issues,
            "expected_issues": self.expected_issues,
            "coverage_percent": self.coverage_percent,
            "shell_coverage_percent": self.shell_coverage_percent,
            "volume_coverage_percent": self.volume_coverage_percent,
        }


def _publisher_id_to_name(session: Session) -> dict[int, str]:
    return {
        int(pid): name
        for pid, name in session.exec(select(UniversePublisher.id, UniversePublisher.name)).all()
        if pid is not None
    }


def _issue_count_maps(session: Session) -> tuple[dict[int, int], dict[int, int]]:
    """Return (total_issues_by_volume, cataloged_issues_by_volume)."""
    total: dict[int, int] = {
        int(vid): int(cnt)
        for vid, cnt in session.exec(
            select(UniverseIssue.volume_id, func.count(UniverseIssue.id)).group_by(UniverseIssue.volume_id)
        ).all()
    }
    cataloged: dict[int, int] = {
        int(vid): int(cnt)
        for vid, cnt in session.exec(
            select(UniverseIssue.volume_id, func.count(UniverseIssue.id))
            .where(UniverseIssue.status == UNIVERSE_ISSUE_STATUS_CATALOGED)
            .group_by(UniverseIssue.volume_id)
        ).all()
    }
    return total, cataloged


def _resolve_publisher_ids(session: Session, requested: str | None) -> tuple[list[int], str, MajorPublisher | None]:
    """Map a requested publisher string to universe_publisher ids.

    Returns (ids, label, registry_entry). Empty ids => no match.
    """
    if not requested or not requested.strip():
        return [], "(all major publishers)", None
    entry = resolve_requested_publisher(requested)
    rows = session.exec(select(UniversePublisher.id, UniversePublisher.normalized_name)).all()
    ids: list[int] = []
    if entry is not None:
        for pid, norm in rows:
            if pid is None:
                continue
            matched = major_publisher_for(norm)
            if matched is not None and matched.canonical == entry.canonical:
                ids.append(int(pid))
        return ids, entry.canonical, entry
    # Fall back to a direct name match.
    needle = requested.strip().lower()
    for pid, norm in rows:
        if pid is not None and needle in (norm or ""):
            ids.append(int(pid))
    return ids, requested.strip(), None


def _build_rows(
    session: Session,
    *,
    publisher_ids: list[int] | None,
) -> list[VolumeGapRow]:
    pub_names = _publisher_id_to_name(session)
    pub_norms = {
        int(pid): norm
        for pid, norm in session.exec(
            select(UniversePublisher.id, UniversePublisher.normalized_name)
        ).all()
        if pid is not None
    }
    total_map, cataloged_map = _issue_count_maps(session)

    stmt = select(UniverseVolume)
    if publisher_ids is not None:
        if not publisher_ids:
            return []
        stmt = stmt.where(UniverseVolume.publisher_id.in_(publisher_ids))
    volumes = list(session.exec(stmt).all())

    rows: list[VolumeGapRow] = []
    for vol in volumes:
        vid = int(vol.id or 0)
        universe_issues = total_map.get(vid, 0)
        catalog_issues = cataloged_map.get(vid, 0)
        status = classify_volume(universe_issues, catalog_issues)
        expected = int(vol.count_of_issues or 0)
        if universe_issues > 0:
            missing = max(universe_issues - catalog_issues, 0)
        else:
            missing = expected
        pub_norm = pub_norms.get(int(vol.publisher_id), "")
        priority = score_volume(
            publisher_normalized=pub_norm,
            volume_name=vol.name,
            start_year=vol.start_year,
            missing_issue_count=missing,
            issue_count=expected or universe_issues,
        )
        rows.append(
            VolumeGapRow(
                universe_volume_id=vid,
                comicvine_volume_id=int(vol.comicvine_volume_id),
                publisher_name=pub_names.get(int(vol.publisher_id), "Unknown"),
                publisher_normalized=pub_norm,
                volume_name=vol.name,
                start_year=vol.start_year,
                expected_issue_count=expected,
                universe_issue_count=universe_issues,
                catalog_issue_count=catalog_issues,
                missing_issue_count=missing,
                status=status,
                recommended_action=recommended_action(status),
                priority_score=priority,
            )
        )
    return rows


def get_publisher_volume_status(
    session: Session,
    *,
    publisher: str | None = None,
) -> list[VolumeGapRow]:
    """Classified gap rows for one publisher (or all major publishers)."""
    if publisher and publisher.strip():
        ids, _label, _entry = _resolve_publisher_ids(session, publisher)
        return _build_rows(session, publisher_ids=ids)
    # All major publishers.
    rows = _build_rows(session, publisher_ids=None)
    return [r for r in rows if major_publisher_for(r.publisher_normalized) is not None]


def get_publisher_gap_summary(
    session: Session,
    *,
    publisher: str | None = None,
) -> PublisherGapSummary:
    ids, label, _entry = _resolve_publisher_ids(session, publisher)
    if publisher and publisher.strip():
        rows = _build_rows(session, publisher_ids=ids)
    else:
        rows = get_publisher_volume_status(session, publisher=None)
        label = "(all major publishers)"

    summary = PublisherGapSummary(publisher=label)
    summary.universe_volumes = len(rows)
    for r in rows:
        summary.universe_issues += r.universe_issue_count
        summary.catalog_linked_issues += r.catalog_issue_count
        summary.expected_issues += r.expected_issue_count
        if r.status == STATUS_CATALOG_COMPLETE:
            summary.catalog_complete += 1
        elif r.status == STATUS_CATALOG_PARTIAL:
            summary.catalog_partial += 1
        elif r.status == STATUS_SHELL_ONLY:
            summary.shell_only += 1
        elif r.status == STATUS_VOLUME_ONLY:
            summary.volume_only += 1
        else:
            summary.unknown += 1
    summary.discovered_only_issues = max(summary.universe_issues - summary.catalog_linked_issues, 0)
    return summary


def get_priority_gap_volumes(
    session: Session,
    *,
    publisher: str | None = None,
    top: int | None = None,
    exclude_complete: bool = True,
) -> list[VolumeGapRow]:
    """Gap volumes sorted by descending priority score."""
    rows = get_publisher_volume_status(session, publisher=publisher)
    if exclude_complete:
        rows = [r for r in rows if r.status != STATUS_CATALOG_COMPLETE]
    rows.sort(key=lambda r: (r.priority_score, r.missing_issue_count), reverse=True)
    if top is not None and top > 0:
        return rows[:top]
    return rows


def build_action_queue(
    session: Session,
    *,
    publisher: str | None = None,
    top: int | None = None,
) -> list[dict]:
    """Planning-only action queue rows across major publishers, priority-desc.

    Includes every classified volume (complete volumes carry the READY action so
    the queue is a complete planning view). No DB writes occur here.
    """
    rows = get_publisher_volume_status(session, publisher=publisher)
    rows.sort(key=lambda r: (r.priority_score, r.missing_issue_count), reverse=True)
    if top is not None and top > 0:
        rows = rows[:top]
    return [r.as_dict() for r in rows]
