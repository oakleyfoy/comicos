"""P98 — Publisher match audit for core runs and DC queue volumes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlmodel import Session, select

from app.models.catalog_p97 import ComicVineVolumeUniverse, P97VolumeIssueImportQueue
from app.services.p97_comicvine_universe_analytics_service import (
    build_catalog_coverage_indexes,
    existing_issue_count_for_volume,
)
from app.services.p97_core_run_registry import (
    expected_publisher_for_report_label,
    pick_best_universe_match,
    volume_title_matches_report_label,
)
from app.services.p97_targeted_core_discovery import find_universe_matches_for_label
from app.services.p97_volume_issue_import_queue_service import STATUS_PENDING
from app.services.p98_publisher_match_service import (
    MATCH_UNKNOWN,
    publisher_match_type,
)

INITIAL_AUDIT_LABELS: tuple[str, ...] = (
    "Flash",
    "Batman",
    "Detective Comics",
    "Action Comics",
    "Superman",
    "Wonder Woman",
    "Green Lantern",
    "Justice League",
    "Teenage Mutant Ninja Turtles",
)

ACTION_TARGETED_US_DISCOVERY = "TARGETED_DISCOVERY_FOR_EXPECTED_PUBLISHER"
ACTION_ADD_QUEUE = "ADD_TO_P97_QUEUE"
ACTION_OK = "OK"
ACTION_REVIEW_COLLECTED = "REVIEW_COLLECTED_EDITION"


@dataclass
class PublisherMatchAuditRow:
    volume_id: int
    volume_name: str
    expected_publisher: str | None
    matched_publisher: str | None
    publisher_match_type: str
    missing_issues: int
    catalog_issue_count: int
    comicvine_issue_count: int
    suggested_action: str
    core_label: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "volume_id": self.volume_id,
            "volume_name": self.volume_name,
            "expected_publisher": self.expected_publisher,
            "matched_publisher": self.matched_publisher,
            "publisher_match_type": self.publisher_match_type,
            "missing_issues": self.missing_issues,
            "catalog_issue_count": self.catalog_issue_count,
            "comicvine_issue_count": self.comicvine_issue_count,
            "suggested_action": self.suggested_action,
            "core_label": self.core_label,
        }


def _coverage_row(
    session: Session,
    universe: ComicVineVolumeUniverse,
    *,
    expected: str | None,
    core_label: str | None,
    indexes,
) -> PublisherMatchAuditRow:
    volume_id = int(universe.volume_id)
    cv_count = int(universe.count_of_issues or 0)
    catalog = existing_issue_count_for_volume(
        volume_id=volume_id,
        name=universe.name,
        publisher=universe.publisher,
        indexes=indexes,
    )
    missing = max(cv_count - catalog, 0)
    match_type = publisher_match_type(
        expected_publisher=expected,
        matched_publisher=universe.publisher,
        volume_name=universe.name,
    )
    action = ACTION_OK
    if match_type in ("WRONG_PUBLISHER_MATCH", "FOREIGN_EDITION_MATCH"):
        action = ACTION_TARGETED_US_DISCOVERY
    elif match_type == "COLLECTED_EDITION_MATCH":
        action = ACTION_REVIEW_COLLECTED
    elif missing > 0 and match_type == "EXACT_MATCH":
        action = ACTION_ADD_QUEUE
    return PublisherMatchAuditRow(
        volume_id=volume_id,
        volume_name=universe.name,
        expected_publisher=expected,
        matched_publisher=universe.publisher,
        publisher_match_type=match_type,
        missing_issues=missing,
        catalog_issue_count=catalog,
        comicvine_issue_count=cv_count,
        suggested_action=action,
        core_label=core_label,
    )


def _core_label_for_volume(
    universes: list[ComicVineVolumeUniverse],
    universe: ComicVineVolumeUniverse,
) -> str | None:
    for label in INITIAL_AUDIT_LABELS:
        if volume_title_matches_report_label(universe.name, label):
            matches = find_universe_matches_for_label(universes, label)
            best, _ = pick_best_universe_match(
                matches,
                label,
                name_getter=lambda u: u.name,
                publisher_getter=lambda u: u.publisher,
                issue_count_getter=lambda u: u.count_of_issues,
                start_year_getter=lambda u: u.start_year,
            )
            if best is not None and int(best.volume_id) == int(universe.volume_id):
                return label
    return None


def build_publisher_match_audit(
    session: Session,
    *,
    dc_queue_limit: int = 100,
) -> list[PublisherMatchAuditRow]:
    universes = list(session.exec(select(ComicVineVolumeUniverse)).all())
    indexes = build_catalog_coverage_indexes(session)
    seen: set[int] = set()
    rows: list[PublisherMatchAuditRow] = []

    for label in INITIAL_AUDIT_LABELS:
        expected = expected_publisher_for_report_label(label)
        matches = find_universe_matches_for_label(universes, label)
        best, pub_ok = pick_best_universe_match(
            matches,
            label,
            name_getter=lambda u: u.name,
            publisher_getter=lambda u: u.publisher,
            issue_count_getter=lambda u: u.count_of_issues,
            start_year_getter=lambda u: u.start_year,
        )
        if best is None:
            continue
        vid = int(best.volume_id)
        if vid in seen:
            continue
        seen.add(vid)
        match_type = publisher_match_type(
            expected_publisher=expected,
            matched_publisher=best.publisher,
            volume_name=best.name,
        )
        if pub_ok:
            match_type = "EXACT_MATCH"
        rows.append(
            _coverage_row(
                session,
                best,
                expected=expected,
                core_label=label,
                indexes=indexes,
            )
        )
        rows[-1].publisher_match_type = match_type

    dc_pending = session.exec(
        select(P97VolumeIssueImportQueue)
        .where(P97VolumeIssueImportQueue.status == STATUS_PENDING)
        .order_by(P97VolumeIssueImportQueue.priority_score.desc())
    ).all()
    dc_count = 0
    for q in dc_pending:
        if dc_count >= int(dc_queue_limit):
            break
        pub = (q.publisher or "").lower()
        if "dc" not in pub:
            continue
        vid = int(q.comicvine_volume_id)
        if vid in seen:
            continue
        uni = session.exec(
            select(ComicVineVolumeUniverse).where(ComicVineVolumeUniverse.volume_id == vid)
        ).first()
        if uni is None:
            continue
        seen.add(vid)
        dc_count += 1
        label = _core_label_for_volume(universes, uni)
        expected = expected_publisher_for_report_label(label) if label else "DC Comics"
        rows.append(
            _coverage_row(
                session,
                uni,
                expected=expected if label else "DC Comics",
                core_label=label,
                indexes=indexes,
            )
        )

    return rows
