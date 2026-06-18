"""P98 — Repair canonical US publisher matches for core series."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.models.catalog_p97 import ComicVineVolumeUniverse
from app.models.universe import UniverseVolume
from app.services.p97_core_run_registry import (
    CORE_RUN_REPORT_LABELS,
    expected_publisher_for_report_label,
    pick_best_universe_match,
    publisher_matches_expected,
    volume_title_matches_report_label,
)
from app.services.p97_targeted_core_discovery import find_universe_matches_for_label
from app.services.p98_publisher_match_service import (
    build_publisher_match_rule_analysis,
    is_foreign_market_publisher,
    publisher_match_type,
)

VOLUME_STATUS_FOREIGN_SUPERSEDED = "foreign_superseded"
REASON_FOREIGN_REPLACED = "FOREIGN_EDITION_REPLACED"
REASON_CANONICAL_OK = "CANONICAL_US_MATCH"

DEFAULT_RULE_ANALYSIS_REL = Path("data/p98/publisher_match_rule_analysis.json")


def _api_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_rule_analysis_path() -> Path:
    return _api_root() / DEFAULT_RULE_ANALYSIS_REL


def save_publisher_match_rule_analysis(path: Path | None = None) -> Path:
    out = path or default_rule_analysis_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build_publisher_match_rule_analysis(), indent=2), encoding="utf-8")
    return out


@dataclass
class PublisherMatchRepairRow:
    volume_name: str
    comicvine_volume_id: int
    current_publisher: str | None
    proposed_publisher: str | None
    proposed_volume_id: int | None
    reason: str
    core_label: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "volume": self.volume_name,
            "comicvine_volume_id": self.comicvine_volume_id,
            "current_publisher": self.current_publisher,
            "proposed_publisher": self.proposed_publisher,
            "proposed_volume_id": self.proposed_volume_id,
            "reason": self.reason,
            "core_label": self.core_label,
        }


@dataclass
class PublisherMatchRepairResult:
    dry_run: bool
    repairs: list[PublisherMatchRepairRow]
    superseded_universe_volumes: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "superseded_universe_volumes": self.superseded_universe_volumes,
            "repairs": [r.as_dict() for r in self.repairs],
        }


def canonical_core_label_for_volume(
    universes: list[ComicVineVolumeUniverse],
    universe: ComicVineVolumeUniverse,
) -> tuple[str, ComicVineVolumeUniverse] | None:
    for label in CORE_RUN_REPORT_LABELS:
        if not volume_title_matches_report_label(universe.name, label):
            continue
        matches = find_universe_matches_for_label(universes, label)
        best, _ = pick_best_universe_match(
            matches,
            label,
            name_getter=lambda u: u.name,
            publisher_getter=lambda u: u.publisher,
            issue_count_getter=lambda u: u.count_of_issues,
            start_year_getter=lambda u: u.start_year,
        )
        if best is not None:
            return label, best
    return None


def is_non_canonical_core_edition(
    session: Session,
    universe: ComicVineVolumeUniverse,
) -> bool:
    universes = list(session.exec(select(ComicVineVolumeUniverse)).all())
    pair = canonical_core_label_for_volume(universes, universe)
    if pair is None:
        return False
    _, best = pair
    return int(best.volume_id) != int(universe.volume_id)


def should_skip_discovered_not_queued_volume(
    session: Session,
    universe: ComicVineVolumeUniverse,
) -> bool:
    uv = session.exec(
        select(UniverseVolume).where(UniverseVolume.comicvine_volume_id == int(universe.volume_id))
    ).first()
    if uv is not None and (uv.volume_status or "").lower() == VOLUME_STATUS_FOREIGN_SUPERSEDED:
        return True
    if is_non_canonical_core_edition(session, universe):
        return True
    return False


def build_publisher_match_repairs(session: Session) -> list[PublisherMatchRepairRow]:
    universes = list(session.exec(select(ComicVineVolumeUniverse)).all())
    repairs: list[PublisherMatchRepairRow] = []
    seen_foreign: set[int] = set()

    for label in CORE_RUN_REPORT_LABELS:
        expected = expected_publisher_for_report_label(label)
        matches = find_universe_matches_for_label(universes, label)
        if not matches:
            continue
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
        for row in matches:
            vid = int(row.volume_id)
            if vid == int(best.volume_id):
                continue
            if not is_foreign_market_publisher(row.publisher) and publisher_matches_expected(
                row.publisher, expected
            ):
                continue
            if vid in seen_foreign:
                continue
            mtype = publisher_match_type(
                expected_publisher=expected,
                matched_publisher=row.publisher,
                volume_name=row.name,
            )
            if mtype not in ("FOREIGN_EDITION_MATCH", "WRONG_PUBLISHER_MATCH"):
                continue
            seen_foreign.add(vid)
            repairs.append(
                PublisherMatchRepairRow(
                    volume_name=row.name,
                    comicvine_volume_id=vid,
                    current_publisher=row.publisher,
                    proposed_publisher=best.publisher,
                    proposed_volume_id=int(best.volume_id),
                    reason=REASON_FOREIGN_REPLACED,
                    core_label=label,
                )
            )
        if not pub_ok and is_foreign_market_publisher(best.publisher):
            repairs.append(
                PublisherMatchRepairRow(
                    volume_name=best.name,
                    comicvine_volume_id=int(best.volume_id),
                    current_publisher=best.publisher,
                    proposed_publisher=expected,
                    proposed_volume_id=None,
                    reason=REASON_FOREIGN_REPLACED,
                    core_label=label,
                )
            )
    return repairs


def apply_publisher_match_repairs(
    session: Session,
    repairs: list[PublisherMatchRepairRow],
    *,
    dry_run: bool = True,
) -> PublisherMatchRepairResult:
    result = PublisherMatchRepairResult(dry_run=dry_run, repairs=repairs)
    for repair in repairs:
        if repair.reason != REASON_FOREIGN_REPLACED:
            continue
        uv = session.exec(
            select(UniverseVolume).where(
                UniverseVolume.comicvine_volume_id == repair.comicvine_volume_id
            )
        ).first()
        if uv is None:
            continue
        if dry_run:
            result.superseded_universe_volumes += 1
            continue
        uv.volume_status = VOLUME_STATUS_FOREIGN_SUPERSEDED
        session.add(uv)
        result.superseded_universe_volumes += 1
    if not dry_run and result.superseded_universe_volumes:
        session.commit()
    return result
