"""P61-03 Spec Opportunity Engine."""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.demand_intelligence import (
    P61_ENGINE_EPOCH,
    P61_SOURCE_VERSION,
    DemandVelocitySnapshot,
    IssueDemandSnapshot,
    SpecOpportunityRow,
    SpecOpportunitySnapshot,
    utc_now,
)
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.models.spec_baseline_score import SpecBaselineScore
from app.services.foc_dates import days_until_foc, utc_today
from app.services.recommendation_forward_window import (
    FORWARD_RECOMMENDATION_WINDOW_DAYS,
    issue_in_forward_recommendation_window,
)


def _horizon_bucket(issue: ReleaseIssue) -> str:
    foc_days = days_until_foc(issue.foc_date, today=utc_today())
    if foc_days is not None and foc_days <= 7:
        return "FOC_URGENT"
    if foc_days is not None and foc_days <= 21:
        return "FOC_NEAR"
    return "FORWARD"


def _latest_baseline_for_owner(session: Session, *, owner_user_id: int) -> float:
    row = session.exec(
        select(SpecBaselineScore)
        .where(SpecBaselineScore.owner_user_id == owner_user_id)
        .order_by(SpecBaselineScore.id.desc())
    ).first()
    return float(row.baseline_score) if row else 50.0


def build_spec_opportunities(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
) -> SpecOpportunitySnapshot:
    issues = session.exec(
        select(ReleaseIssue, ReleaseSeries)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
    ).all()
    candidates: list[tuple[float, ReleaseIssue, ReleaseSeries, dict]] = []
    owner_baseline = _latest_baseline_for_owner(session, owner_user_id=owner_user_id)

    for issue, series in issues:
        if issue.id is None:
            continue
        if not issue_in_forward_recommendation_window(issue):
            continue
        demand_row = session.exec(
            select(IssueDemandSnapshot).where(IssueDemandSnapshot.release_issue_id == int(issue.id))
        ).first()
        demand_score = float(demand_row.combined_demand_score) if demand_row else 50.0
        velocity_row = None
        if demand_row:
            velocity_row = session.exec(
                select(DemandVelocitySnapshot)
                .where(DemandVelocitySnapshot.external_issue_id == demand_row.external_issue_id)
                .order_by(DemandVelocitySnapshot.window_days.asc())
            ).first()
        velocity_score = float(velocity_row.velocity_score) if velocity_row else 50.0
        preference_fit = 50.0
        opportunity = round(
            demand_score * 0.42 + velocity_score * 0.28 + owner_baseline * 0.2 + preference_fit * 0.1,
            2,
        )
        title = f"{series.series_name} {issue.issue_number or ''}".strip() or issue.title
        rationale = {
            "demand_score": demand_score,
            "velocity_score": velocity_score,
            "spec_baseline_score": owner_baseline,
            "horizon_bucket": _horizon_bucket(issue),
            "series": series.series_name,
        }
        candidates.append((opportunity, issue, series, rationale))

    candidates.sort(key=lambda x: (-x[0], x[1].title or ""))
    top = candidates[: max(1, limit)]

    snapshot = SpecOpportunitySnapshot(
        owner_user_id=owner_user_id,
        snapshot_at=utc_now(),
        engine_epoch=P61_ENGINE_EPOCH,
        row_count=len(top),
        source_version=P61_SOURCE_VERSION,
    )
    session.add(snapshot)
    session.flush()

    for rank, (score, issue, _series, rationale) in enumerate(top, start=1):
        session.add(
            SpecOpportunityRow(
                snapshot_id=int(snapshot.id or 0),
                owner_user_id=owner_user_id,
                release_issue_id=int(issue.id or 0),
                title=rationale.get("series", issue.title) or issue.title,
                opportunity_score=score,
                spec_baseline_score=owner_baseline,
                demand_score=float(rationale["demand_score"]),
                velocity_score=float(rationale["velocity_score"]),
                preference_fit_score=50.0,
                horizon_bucket=str(rationale["horizon_bucket"]),
                rationale_json=rationale,
                rank=rank,
            )
        )
    session.commit()
    session.refresh(snapshot)
    return snapshot


def get_latest_spec_snapshot(session: Session, *, owner_user_id: int) -> SpecOpportunitySnapshot | None:
    return session.exec(
        select(SpecOpportunitySnapshot)
        .where(SpecOpportunitySnapshot.owner_user_id == owner_user_id)
        .order_by(SpecOpportunitySnapshot.id.desc())
    ).first()


def list_spec_opportunity_rows(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[SpecOpportunityRow], SpecOpportunitySnapshot | None]:
    snapshot = get_latest_spec_snapshot(session, owner_user_id=owner_user_id)
    if snapshot is None or snapshot.id is None:
        return [], None
    rows = session.exec(
        select(SpecOpportunityRow)
        .where(SpecOpportunityRow.snapshot_id == int(snapshot.id))
        .order_by(SpecOpportunityRow.rank.asc())
    ).all()
    page = rows[offset : offset + limit]
    return page, snapshot
