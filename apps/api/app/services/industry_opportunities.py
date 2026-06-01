from __future__ import annotations

from sqlmodel import Session, select

from app.models.asset_ledger import utc_now
from app.models.industry_opportunity import IndustryOpportunityScore
from app.models.industry_release_scan import IndustryReleaseCandidate
from app.models.industry_release_signal import IndustryReleaseSignal
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries, ReleaseVariant
from app.schemas.industry_opportunity import (
    IndustryOpportunityLatestRead,
    IndustryOpportunityRead,
    IndustryOpportunitySummaryRead,
)
from app.services.industry_opportunity_engine import compute_industry_opportunity_score
from app.services.industry_release_scans import latest_scan_run_id
from app.services.industry_release_scanner import scan_industry_releases
from app.services.industry_release_signals import classify_latest_industry_release_signals


def _to_read(row: IndustryOpportunityScore) -> IndustryOpportunityRead:
    return IndustryOpportunityRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        candidate_id=int(row.candidate_id),
        scan_run_id=int(row.scan_run_id),
        release_id=int(row.release_id),
        publisher_code=row.publisher_code,
        publisher_name=row.publisher_name,
        series_name=row.series_name,
        issue_number=row.issue_number,
        opportunity_score=float(row.opportunity_score),
        confidence_score=float(row.confidence_score),
        risk_level=row.risk_level,
        rationale=row.rationale,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


def _upsert_score(
    session: Session,
    *,
    owner_user_id: int,
    candidate: IndustryReleaseCandidate,
    opportunity_score: float,
    confidence_score: float,
    risk_level: str,
    rationale: str,
) -> tuple[IndustryOpportunityScore, bool]:
    row = session.exec(
        select(IndustryOpportunityScore)
        .where(IndustryOpportunityScore.owner_user_id == owner_user_id)
        .where(IndustryOpportunityScore.candidate_id == int(candidate.id or 0))
    ).first()
    if row is None:
        row = IndustryOpportunityScore(
            owner_user_id=owner_user_id,
            candidate_id=int(candidate.id or 0),
            scan_run_id=int(candidate.scan_run_id),
            release_id=int(candidate.release_id),
            publisher_code=candidate.publisher_code,
            publisher_name=candidate.publisher_name,
            series_name=candidate.series_name,
            issue_number=candidate.issue_number,
            opportunity_score=opportunity_score,
            confidence_score=confidence_score,
            risk_level=risk_level,
            rationale=rationale,
        )
        session.add(row)
        return row, True
    unchanged = (
        int(row.scan_run_id) == int(candidate.scan_run_id)
        and float(row.opportunity_score) == float(opportunity_score)
        and float(row.confidence_score) == float(confidence_score)
        and row.risk_level == risk_level
        and row.rationale == rationale
    )
    if unchanged:
        return row, False
    row.scan_run_id = int(candidate.scan_run_id)
    row.opportunity_score = opportunity_score
    row.confidence_score = confidence_score
    row.risk_level = risk_level
    row.rationale = rationale
    row.updated_at = utc_now()
    session.add(row)
    return row, True


def synchronize_industry_opportunity_scores(session: Session, *, owner_user_id: int, scan_run_id: int) -> int:
    candidates = session.exec(
        select(IndustryReleaseCandidate)
        .where(IndustryReleaseCandidate.owner_user_id == owner_user_id)
        .where(IndustryReleaseCandidate.scan_run_id == scan_run_id)
    ).all()
    if not candidates:
        return 0

    candidate_ids = [int(c.id or 0) for c in candidates]
    release_ids = [int(c.release_id) for c in candidates]
    signals_by_candidate: dict[int, list[IndustryReleaseSignal]] = {}
    for signal in session.exec(
        select(IndustryReleaseSignal).where(IndustryReleaseSignal.candidate_id.in_(candidate_ids))
    ).all():
        signals_by_candidate.setdefault(int(signal.candidate_id), []).append(signal)

    issues = {
        int(row.id or 0): row
        for row in session.exec(select(ReleaseIssue).where(ReleaseIssue.id.in_(release_ids))).all()
    }
    series_ids = {int(issues[rid].series_id) for rid in release_ids if rid in issues}
    series_map = {
        int(row.id or 0): row
        for row in session.exec(select(ReleaseSeries).where(ReleaseSeries.id.in_(series_ids))).all()
    }
    variant_rows = session.exec(select(ReleaseVariant).where(ReleaseVariant.issue_id.in_(release_ids))).all()
    variants_by_issue: dict[int, list[ReleaseVariant]] = {}
    for variant in variant_rows:
        variants_by_issue.setdefault(int(variant.issue_id), []).append(variant)

    updated = 0
    for candidate in candidates:
        issue = issues.get(int(candidate.release_id))
        if issue is None:
            continue
        series = series_map.get(int(issue.series_id))
        if series is None:
            continue
        result = compute_industry_opportunity_score(
            session,
            owner_user_id=owner_user_id,
            candidate=candidate,
            issue=issue,
            series=series,
            variants=variants_by_issue.get(int(candidate.release_id), []),
            signals=signals_by_candidate.get(int(candidate.id or 0), []),
        )
        _, changed = _upsert_score(
            session,
            owner_user_id=owner_user_id,
            candidate=candidate,
            opportunity_score=result.opportunity_score,
            confidence_score=result.confidence_score,
            risk_level=result.risk_level,
            rationale=result.rationale,
        )
        if changed:
            updated += 1
    session.commit()
    return updated


def get_latest_industry_opportunities_read(session: Session, *, owner_user_id: int) -> IndustryOpportunityLatestRead:
    run_id = latest_scan_run_id(session, owner_user_id=owner_user_id)
    if run_id is None:
        return IndustryOpportunityLatestRead(scan_run_id=None, scores_computed=0, items=[])
    items, _ = list_industry_opportunities(
        session,
        owner_user_id=owner_user_id,
        scan_run_id=run_id,
        limit=200,
        offset=0,
    )
    return IndustryOpportunityLatestRead(scan_run_id=run_id, scores_computed=0, items=items)


def refresh_latest_industry_opportunities(session: Session, *, owner_user_id: int) -> IndustryOpportunityLatestRead:
    run_id = latest_scan_run_id(session, owner_user_id=owner_user_id)
    if run_id is None:
        scan_industry_releases(session, owner_user_id=owner_user_id)
        run_id = latest_scan_run_id(session, owner_user_id=owner_user_id)
    classify_latest_industry_release_signals(session, owner_user_id=owner_user_id)
    if run_id is None:
        return IndustryOpportunityLatestRead(scan_run_id=None, scores_computed=0, items=[])

    computed = synchronize_industry_opportunity_scores(session, owner_user_id=owner_user_id, scan_run_id=run_id)
    items, _ = list_industry_opportunities(
        session,
        owner_user_id=owner_user_id,
        scan_run_id=run_id,
        limit=200,
        offset=0,
    )
    return IndustryOpportunityLatestRead(scan_run_id=run_id, scores_computed=computed, items=items)


def list_industry_opportunities(
    session: Session,
    *,
    owner_user_id: int,
    scan_run_id: int | None = None,
    risk_level: str | None = None,
    opportunity_score_min: float | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[IndustryOpportunityRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    run_id = scan_run_id or latest_scan_run_id(session, owner_user_id=owner_user_id)
    if run_id is None:
        return [], 0

    statement = (
        select(IndustryOpportunityScore)
        .where(IndustryOpportunityScore.owner_user_id == owner_user_id)
        .where(IndustryOpportunityScore.scan_run_id == run_id)
    )
    if risk_level:
        statement = statement.where(IndustryOpportunityScore.risk_level == risk_level.strip().upper())
    if opportunity_score_min is not None:
        statement = statement.where(IndustryOpportunityScore.opportunity_score >= float(opportunity_score_min))

    rows = session.exec(
        statement.order_by(
            IndustryOpportunityScore.opportunity_score.desc(),
            IndustryOpportunityScore.confidence_score.desc(),
            IndustryOpportunityScore.series_name.asc(),
        )
    ).all()
    total = len(rows)
    page = rows[offset : offset + limit]
    return [_to_read(row) for row in page], total


def build_industry_opportunity_summary(session: Session, *, owner_user_id: int) -> IndustryOpportunitySummaryRead:
    run_id = latest_scan_run_id(session, owner_user_id=owner_user_id)
    if run_id is None:
        return IndustryOpportunitySummaryRead(scan_run_id=None)

    rows = session.exec(
        select(IndustryOpportunityScore)
        .where(IndustryOpportunityScore.owner_user_id == owner_user_id)
        .where(IndustryOpportunityScore.scan_run_id == run_id)
    ).all()
    if not rows:
        return IndustryOpportunitySummaryRead(scan_run_id=run_id)

    total = len(rows)
    average = round(sum(float(row.opportunity_score) for row in rows) / total, 2)
    high_count = sum(1 for row in rows if float(row.opportunity_score) >= 70.0)
    low_risk = sum(1 for row in rows if row.risk_level == "LOW")
    medium_risk = sum(1 for row in rows if row.risk_level == "MEDIUM")
    high_risk = sum(1 for row in rows if row.risk_level == "HIGH")

    return IndustryOpportunitySummaryRead(
        scan_run_id=run_id,
        total_opportunities=total,
        average_opportunity_score=average,
        high_opportunity_count=high_count,
        low_risk_count=low_risk,
        medium_risk_count=medium_risk,
        high_risk_count=high_risk,
    )
