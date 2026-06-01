from __future__ import annotations

from sqlmodel import Session, select

from app.models.industry_opportunity import IndustryOpportunityScore
from app.models.industry_release_scan import IndustryReleaseCandidate, IndustryReleaseScanRun
from app.models.industry_release_signal import IndustryReleaseSignal
from app.schemas.industry_opportunity import IndustryOpportunityRead
from app.schemas.industry_scanner_dashboard import (
    IndustryScannerDashboardItemRead,
    IndustryScannerDashboardRead,
    IndustryScannerDashboardSummaryRead,
)
from app.services.industry_opportunities import list_industry_opportunities, refresh_latest_industry_opportunities
from app.services.industry_release_scans import latest_scan_run_id

SECTION_LIMIT = 25
HIGH_SCORE_THRESHOLD = 70.0
WATCHLIST_MIN_SCORE = 35.0


def _ensure_pipeline(session: Session, *, owner_user_id: int, refresh: bool) -> None:
    if refresh:
        refresh_latest_industry_opportunities(session, owner_user_id=owner_user_id)


def _signals_by_candidate(session: Session, *, owner_user_id: int, scan_run_id: int) -> dict[int, list[str]]:
    rows = session.exec(
        select(IndustryReleaseSignal)
        .where(IndustryReleaseSignal.owner_user_id == owner_user_id)
        .where(IndustryReleaseSignal.scan_run_id == scan_run_id)
    ).all()
    grouped: dict[int, list[str]] = {}
    for row in rows:
        grouped.setdefault(int(row.candidate_id), []).append(row.signal_type)
    for candidate_id, types in grouped.items():
        grouped[candidate_id] = sorted(set(types))
    return grouped


def _candidates_by_id(session: Session, *, owner_user_id: int, scan_run_id: int) -> dict[int, IndustryReleaseCandidate]:
    rows = session.exec(
        select(IndustryReleaseCandidate)
        .where(IndustryReleaseCandidate.owner_user_id == owner_user_id)
        .where(IndustryReleaseCandidate.scan_run_id == scan_run_id)
    ).all()
    return {int(row.id or 0): row for row in rows}


def _to_dashboard_item(
    opportunity: IndustryOpportunityRead,
    *,
    signal_types: list[str],
    candidate: IndustryReleaseCandidate | None,
) -> IndustryScannerDashboardItemRead:
    foc = candidate.foc_date.isoformat() if candidate and candidate.foc_date else None
    release = candidate.release_date.isoformat() if candidate and candidate.release_date else None
    monitoring = candidate.monitoring_status if candidate else "MONITOR"
    return IndustryScannerDashboardItemRead(
        **opportunity.model_dump(),
        signal_types=signal_types,
        foc_date=foc,
        release_date=release,
        monitoring_status=monitoring,
    )


def _has_signal(signal_types: list[str], target: str) -> bool:
    return target in signal_types


def _has_any_signal(signal_types: list[str], targets: set[str]) -> bool:
    return bool(set(signal_types).intersection(targets))


def build_industry_scanner_dashboard_summary(
    session: Session,
    *,
    owner_user_id: int,
    refresh: bool = False,
) -> IndustryScannerDashboardSummaryRead:
    _ensure_pipeline(session, owner_user_id=owner_user_id, refresh=refresh)
    run_id = latest_scan_run_id(session, owner_user_id=owner_user_id)
    if run_id is None:
        return IndustryScannerDashboardSummaryRead()

    scan_run = session.get(IndustryReleaseScanRun, run_id)
    releases_scanned = int(scan_run.releases_scanned) if scan_run else 0

    signal_rows = session.exec(
        select(IndustryReleaseSignal)
        .where(IndustryReleaseSignal.owner_user_id == owner_user_id)
        .where(IndustryReleaseSignal.scan_run_id == run_id)
    ).all()
    signals_by_candidate = _signals_by_candidate(session, owner_user_id=owner_user_id, scan_run_id=run_id)

    opportunities = session.exec(
        select(IndustryOpportunityScore)
        .where(IndustryOpportunityScore.owner_user_id == owner_user_id)
        .where(IndustryOpportunityScore.scan_run_id == run_id)
    ).all()

    high_score = sum(1 for row in opportunities if float(row.opportunity_score) >= HIGH_SCORE_THRESHOLD)
    number_one = sum(1 for types in signals_by_candidate.values() if "NUMBER_ONE" in types)
    ratio_variants = sum(1 for types in signals_by_candidate.values() if "RATIO_VARIANT" in types)
    key_events = sum(
        1 for types in signals_by_candidate.values() if "KEY_EVENT" in types or "CROSSOVER" in types
    )

    return IndustryScannerDashboardSummaryRead(
        releases_scanned=releases_scanned,
        signals_detected=len(signal_rows),
        high_score_opportunities=high_score,
        number_one_issues=number_one,
        ratio_variants=ratio_variants,
        key_events=key_events,
    )


def build_industry_scanner_dashboard(
    session: Session,
    *,
    owner_user_id: int,
    refresh: bool = False,
) -> IndustryScannerDashboardRead:
    _ensure_pipeline(session, owner_user_id=owner_user_id, refresh=refresh)
    summary = build_industry_scanner_dashboard_summary(session, owner_user_id=owner_user_id, refresh=False)
    run_id = latest_scan_run_id(session, owner_user_id=owner_user_id)
    if run_id is None:
        return IndustryScannerDashboardRead(summary=summary, scan_run_id=None)

    items, _ = list_industry_opportunities(
        session,
        owner_user_id=owner_user_id,
        scan_run_id=run_id,
        limit=500,
        offset=0,
    )
    signals_by_candidate = _signals_by_candidate(session, owner_user_id=owner_user_id, scan_run_id=run_id)
    candidates = _candidates_by_id(session, owner_user_id=owner_user_id, scan_run_id=run_id)

    dashboard_items = [
        _to_dashboard_item(
            row,
            signal_types=signals_by_candidate.get(row.candidate_id, []),
            candidate=candidates.get(row.candidate_id),
        )
        for row in items
    ]

    def _filter_section(predicate) -> list[IndustryScannerDashboardItemRead]:
        return [row for row in dashboard_items if predicate(row)][:SECTION_LIMIT]

    top_number_one = _filter_section(lambda row: _has_signal(row.signal_types, "NUMBER_ONE"))
    ratio_section = _filter_section(lambda row: _has_signal(row.signal_types, "RATIO_VARIANT"))
    facsimiles = _filter_section(lambda row: _has_signal(row.signal_types, "FACSIMILE"))
    anniversary_milestone = _filter_section(
        lambda row: _has_any_signal(row.signal_types, {"ANNIVERSARY", "MILESTONE"}),
    )
    key_events = _filter_section(lambda row: _has_any_signal(row.signal_types, {"KEY_EVENT", "CROSSOVER"}))
    high_opportunity = _filter_section(lambda row: row.opportunity_score >= HIGH_SCORE_THRESHOLD)
    watchlist = _filter_section(
        lambda row: WATCHLIST_MIN_SCORE <= row.opportunity_score < HIGH_SCORE_THRESHOLD and row.risk_level != "HIGH",
    )

    return IndustryScannerDashboardRead(
        summary=summary,
        scan_run_id=run_id,
        top_number_one_issues=top_number_one,
        ratio_variants=ratio_section,
        facsimiles=facsimiles,
        anniversary_milestone_books=anniversary_milestone,
        key_events=key_events,
        high_opportunity_score=high_opportunity,
        watchlist=watchlist,
    )
