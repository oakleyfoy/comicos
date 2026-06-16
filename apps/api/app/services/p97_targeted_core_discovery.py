"""Publisher-aware core run discovery gap analysis and targeted ComicVine search."""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, select

from app.models.catalog_p97 import ComicVineVolumeUniverse
from app.services.comicvine_api_response import payload_results
from app.services.p97_comicvine_universe_discovery_service import (
    ComicVineUniverseDiscoveryClient,
    upsert_universe_volume,
)
from app.services.p97_manual_volume_request_service import (
    VolumeSearchCandidate,
    search_comicvine_volumes_for_request,
    volume_payload_from_detail,
)
from app.services.p97_core_run_registry import (
    CORE_RUN_REPORT_LABELS,
    expected_publisher_for_report_label,
    pick_best_universe_match,
    publisher_matches_expected,
    registry_keys_for_report_label,
    volume_title_matches_report_label,
)


@dataclass(frozen=True)
class CoreDiscoveryStatusRow:
    report_label: str
    expected_publisher: str
    discovered: bool
    publisher_match: bool
    volume_id: int | None
    volume_name: str | None
    matched_publisher: str | None
    issue_count: int | None
    start_year: int | None


@dataclass(frozen=True)
class CoreDiscoverySummary:
    core_runs_total: int
    core_runs_discovered: int
    core_runs_missing: int
    discovery_coverage_percent: float


@dataclass(frozen=True)
class TargetedCoreDiscoveryCandidate:
    report_label: str
    expected_publisher: str
    volume_id: int
    name: str
    publisher: str | None
    count_of_issues: int | None
    start_year: int | None
    publisher_match: bool
    rank_score: tuple[int, int, int]


@dataclass(frozen=True)
class TargetedCoreDiscoveryPlan:
    report_label: str
    expected_publisher: str
    missing_from_universe: bool
    selected: TargetedCoreDiscoveryCandidate | None
    candidates: tuple[TargetedCoreDiscoveryCandidate, ...]


@dataclass(frozen=True)
class TargetedCoreApplyResult:
    report_label: str
    volume_id: int
    action: str
    inserted: bool


def _universe_getters():
    return (
        lambda u: u.name,
        lambda u: u.publisher,
        lambda u: u.count_of_issues,
        lambda u: u.start_year,
    )


def find_universe_matches_for_label(
    universes: list[ComicVineVolumeUniverse],
    report_label: str,
) -> list[ComicVineVolumeUniverse]:
    return [
        row
        for row in universes
        if volume_title_matches_report_label(row.name, report_label)
    ]


def build_core_discovery_status(session: Session) -> tuple[list[CoreDiscoveryStatusRow], CoreDiscoverySummary]:
    universes = list(session.exec(select(ComicVineVolumeUniverse)).all())
    rows: list[CoreDiscoveryStatusRow] = []
    discovered_count = 0

    name_g, pub_g, iss_g, sy_g = _universe_getters()
    for label in CORE_RUN_REPORT_LABELS:
        expected = expected_publisher_for_report_label(label)
        matches = find_universe_matches_for_label(universes, label)
        best, pub_ok = pick_best_universe_match(
            matches,
            label,
            name_getter=name_g,
            publisher_getter=pub_g,
            issue_count_getter=iss_g,
            start_year_getter=sy_g,
        )
        discovered = best is not None
        if discovered:
            discovered_count += 1
        rows.append(
            CoreDiscoveryStatusRow(
                report_label=label,
                expected_publisher=expected,
                discovered=discovered,
                publisher_match=pub_ok if discovered else False,
                volume_id=int(best.volume_id) if best is not None else None,
                volume_name=best.name if best is not None else None,
                matched_publisher=best.publisher if best is not None else None,
                issue_count=int(best.count_of_issues or 0) if best else None,
                start_year=best.start_year if best is not None else None,
            )
        )

    total = len(CORE_RUN_REPORT_LABELS)
    missing = total - discovered_count
    coverage = (discovered_count / total * 100.0) if total else 0.0
    summary = CoreDiscoverySummary(
        core_runs_total=total,
        core_runs_discovered=discovered_count,
        core_runs_missing=missing,
        discovery_coverage_percent=round(coverage, 2),
    )
    return rows, summary


def has_publisher_correct_universe_match(
    universes: list[ComicVineVolumeUniverse],
    report_label: str,
) -> bool:
    expected = expected_publisher_for_report_label(report_label)
    for row in find_universe_matches_for_label(universes, report_label):
        if publisher_matches_expected(row.publisher, expected):
            return True
    return False


def missing_core_report_labels(session: Session) -> list[str]:
    universes = list(session.exec(select(ComicVineVolumeUniverse)).all())
    return [
        label
        for label in CORE_RUN_REPORT_LABELS
        if not has_publisher_correct_universe_match(universes, label)
    ]


def _candidate_rank(
    candidate: VolumeSearchCandidate,
    *,
    expected_publisher: str,
) -> tuple[int, int, int]:
    pub_ok = publisher_matches_expected(candidate.publisher, expected_publisher)
    issues = int(candidate.count_of_issues or 0)
    start = candidate.start_year if candidate.start_year is not None else 9999
    return (1 if pub_ok else 0, issues, -int(start))


def search_core_run_candidates(
    client: ComicVineUniverseDiscoveryClient,
    report_label: str,
    *,
    search_limit: int = 30,
) -> list[TargetedCoreDiscoveryCandidate]:
    expected = expected_publisher_for_report_label(report_label)
    keys = registry_keys_for_report_label(report_label)
    seen: dict[int, VolumeSearchCandidate] = {}
    for key in keys:
        for candidate in search_comicvine_volumes_for_request(
            client,
            query=key,
            publisher=None,
            limit=search_limit,
        ):
            if not volume_title_matches_report_label(candidate.name, report_label):
                continue
            seen[int(candidate.volume_id)] = candidate

    ranked: list[TargetedCoreDiscoveryCandidate] = []
    for candidate in seen.values():
        rank = _candidate_rank(candidate, expected_publisher=expected)
        ranked.append(
            TargetedCoreDiscoveryCandidate(
                report_label=report_label,
                expected_publisher=expected,
                volume_id=int(candidate.volume_id),
                name=candidate.name,
                publisher=candidate.publisher,
                count_of_issues=candidate.count_of_issues,
                start_year=candidate.start_year,
                publisher_match=publisher_matches_expected(candidate.publisher, expected),
                rank_score=rank,
            )
        )
    ranked.sort(key=lambda c: c.rank_score, reverse=True)
    return ranked


def build_targeted_discovery_plans(
    session: Session,
    client: ComicVineUniverseDiscoveryClient,
    *,
    labels: list[str] | None = None,
    search_limit: int = 30,
) -> list[TargetedCoreDiscoveryPlan]:
    target_labels = labels or missing_core_report_labels(session)
    plans: list[TargetedCoreDiscoveryPlan] = []
    for label in target_labels:
        expected = expected_publisher_for_report_label(label)
        all_universes = list(session.exec(select(ComicVineVolumeUniverse)).all())
        publisher_ok = has_publisher_correct_universe_match(all_universes, label)
        missing = not publisher_ok
        candidates = (
            search_core_run_candidates(client, label, search_limit=search_limit)
            if missing
            else []
        )
        selected = None
        if candidates:
            for candidate in candidates:
                if candidate.publisher_match:
                    selected = candidate
                    break
            if selected is None:
                selected = candidates[0]
        plans.append(
            TargetedCoreDiscoveryPlan(
                report_label=label,
                expected_publisher=expected,
                missing_from_universe=missing,
                selected=selected,
                candidates=tuple(candidates),
            )
        )
    return plans


def apply_universe_discovery_candidate(
    session: Session,
    client: ComicVineUniverseDiscoveryClient,
    *,
    volume_id: int,
) -> str:
    """Insert or update comicvine_volume_universe only (no queue, no issue import)."""
    detail_payload = client.fetch_volume_detail(volume_id=int(volume_id))
    results = detail_payload.get("results")
    if isinstance(results, dict):
        detail = results
    else:
        rows = payload_results(detail_payload)
        if not rows:
            raise ValueError(f"ComicVine volume detail missing results for {volume_id}")
        detail = rows[0]
    parsed = volume_payload_from_detail(detail, volume_id=int(volume_id))
    return upsert_universe_volume(session, parsed)


def apply_targeted_core_discoveries(
    session: Session,
    client: ComicVineUniverseDiscoveryClient,
    plans: list[TargetedCoreDiscoveryPlan],
) -> list[TargetedCoreApplyResult]:
    results: list[TargetedCoreApplyResult] = []
    for plan in plans:
        if not plan.missing_from_universe or plan.selected is None:
            continue
        existing = session.exec(
            select(ComicVineVolumeUniverse).where(
                ComicVineVolumeUniverse.volume_id == plan.selected.volume_id
            )
        ).first()
        if existing is not None:
            continue
        action = apply_universe_discovery_candidate(
            session,
            client,
            volume_id=plan.selected.volume_id,
        )
        results.append(
            TargetedCoreApplyResult(
                report_label=plan.report_label,
                volume_id=plan.selected.volume_id,
                action=action,
                inserted=action == "inserted",
            )
        )
    return results
