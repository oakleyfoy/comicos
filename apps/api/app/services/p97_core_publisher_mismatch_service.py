"""Core run publisher mismatch report."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlmodel import Session, select

from app.models.catalog_p97 import ComicVineVolumeUniverse
from app.services.p97_core_run_registry import (
    CORE_RUN_REPORT_LABELS,
    expected_publisher_for_report_label,
    pick_best_universe_match,
    publisher_matches_expected,
)
from app.services.p97_targeted_core_discovery import find_universe_matches_for_label

ACTION_TARGETED_DISCOVERY = "TARGETED_DISCOVERY_FOR_EXPECTED_PUBLISHER"
STATUS_WRONG_PUBLISHER_MATCH = "WRONG_PUBLISHER_MATCH"


@dataclass
class CorePublisherMismatchRow:
    core_title: str
    expected_publisher: str
    matched_publisher: str | None
    volume_id: int | None
    volume_name: str | None
    status: str
    recommended_action: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "core_title": self.core_title,
            "expected_publisher": self.expected_publisher,
            "matched_publisher": self.matched_publisher,
            "volume_id": self.volume_id,
            "volume_name": self.volume_name,
            "status": self.status,
            "recommended_action": self.recommended_action,
        }


def build_core_publisher_mismatch_report(session: Session) -> list[CorePublisherMismatchRow]:
    universes = list(session.exec(select(ComicVineVolumeUniverse)).all())
    rows: list[CorePublisherMismatchRow] = []
    for label in CORE_RUN_REPORT_LABELS:
        expected = expected_publisher_for_report_label(label)
        candidates = find_universe_matches_for_label(universes, label)
        best, pub_ok = pick_best_universe_match(
            candidates,
            label,
            name_getter=lambda u: u.name,
            publisher_getter=lambda u: u.publisher,
            issue_count_getter=lambda u: u.count_of_issues,
            start_year_getter=lambda u: u.start_year,
        )
        if best is None:
            continue
        if pub_ok or publisher_matches_expected(best.publisher, expected):
            continue
        rows.append(
            CorePublisherMismatchRow(
                core_title=label,
                expected_publisher=expected,
                matched_publisher=best.publisher,
                volume_id=int(best.volume_id),
                volume_name=best.name,
                status=STATUS_WRONG_PUBLISHER_MATCH,
                recommended_action=ACTION_TARGETED_DISCOVERY,
            )
        )
    return rows
