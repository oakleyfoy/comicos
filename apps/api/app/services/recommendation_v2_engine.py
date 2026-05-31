from __future__ import annotations

from datetime import date, timedelta

from sqlmodel import Session, select

from app.models.recommendation_v2 import (
    RecommendationDecisionV2,
    RecommendationRunV2,
    RecommendationScoreComponentV2,
    RecommendationScoreV2,
    utc_now,
)
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries, ReleaseVariant
from app.services.market_demand_engine import refresh_market_demand
from app.services.recommendation_v2_components import score_issue_components_v2
from app.services.recommendation_v2_explanations import build_recommendation_decision
from app.services.user_preference_engine import refresh_user_preferences


def score_release_issue_v2(
    session: Session,
    *,
    owner_user_id: int,
    run_id: int,
    issue: ReleaseIssue,
    series: ReleaseSeries,
) -> RecommendationScoreV2:
    bundle = score_issue_components_v2(session, owner_user_id=owner_user_id, issue=issue, series=series)
    row = RecommendationScoreV2(
        owner_user_id=owner_user_id,
        recommendation_run_id=run_id,
        release_issue_id=int(issue.id or 0),
        release_variant_id=None,
        total_score=bundle.total_score,
        recommendation_tier=bundle.recommendation_tier,
        recommendation_type=bundle.recommendation_type,
        confidence_score=bundle.confidence_score,
    )
    session.add(row)
    session.flush()
    for comp in bundle.components:
        session.add(
            RecommendationScoreComponentV2(
                recommendation_score_id=int(row.id or 0),
                component_name=comp.component_name,
                component_score=comp.component_score,
                component_weight=comp.component_weight,
                explanation=comp.explanation,
            )
        )
    decision = build_recommendation_decision(
        bundle=bundle,
        series_name=series.series_name,
        issue_number=issue.issue_number,
        publisher=series.publisher,
    )
    decision.recommendation_score_id = int(row.id or 0)
    session.add(decision)
    return row


def score_release_variant_v2(
    session: Session,
    *,
    owner_user_id: int,
    run_id: int,
    issue: ReleaseIssue,
    series: ReleaseSeries,
    variant: ReleaseVariant,
) -> RecommendationScoreV2:
    bundle = score_issue_components_v2(
        session, owner_user_id=owner_user_id, issue=issue, series=series, variant=variant
    )
    if variant.ratio_value and bundle.recommendation_type == "NEW_OPPORTUNITY":
        rec_type = "RATIO_VARIANT"
    else:
        rec_type = bundle.recommendation_type
    row = RecommendationScoreV2(
        owner_user_id=owner_user_id,
        recommendation_run_id=run_id,
        release_issue_id=int(issue.id or 0),
        release_variant_id=int(variant.id or 0),
        total_score=bundle.total_score,
        recommendation_tier=bundle.recommendation_tier,
        recommendation_type=rec_type,
        confidence_score=bundle.confidence_score,
    )
    session.add(row)
    session.flush()
    for comp in bundle.components:
        session.add(
            RecommendationScoreComponentV2(
                recommendation_score_id=int(row.id or 0),
                component_name=comp.component_name,
                component_score=comp.component_score,
                component_weight=comp.component_weight,
                explanation=comp.explanation,
            )
        )
    decision = build_recommendation_decision(
        bundle=bundle,
        series_name=f"{series.series_name} ({variant.variant_name})",
        issue_number=issue.issue_number,
        publisher=series.publisher,
    )
    decision.recommendation_score_id = int(row.id or 0)
    session.add(decision)
    return row


def generate_recommendations_v2(session: Session, *, owner_user_id: int) -> RecommendationRunV2:
    refresh_market_demand(session)
    refresh_user_preferences(session, owner_user_id=owner_user_id)

    run = RecommendationRunV2(owner_user_id=owner_user_id, status="RUNNING")
    session.add(run)
    session.commit()
    session.refresh(run)
    run_id = int(run.id or 0)

    issues_scored = 0
    variants_scored = 0
    created = 0

    rows = session.exec(
        select(ReleaseIssue, ReleaseSeries)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .order_by(ReleaseIssue.release_date.asc(), ReleaseIssue.id.asc())
    ).all()

    for issue, series in rows:
        score_release_issue_v2(session, owner_user_id=owner_user_id, run_id=run_id, issue=issue, series=series)
        issues_scored += 1
        created += 1
        variants = session.exec(select(ReleaseVariant).where(ReleaseVariant.issue_id == int(issue.id or 0))).all()
        for variant in variants:
            if variant.ratio_value or variant.is_incentive_variant:
                score_release_variant_v2(
                    session,
                    owner_user_id=owner_user_id,
                    run_id=run_id,
                    issue=issue,
                    series=series,
                    variant=variant,
                )
                variants_scored += 1
                created += 1

    run.issues_scored = issues_scored
    run.variants_scored = variants_scored
    run.recommendations_created = created
    run.status = "COMPLETED"
    run.completed_at = utc_now()
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def _latest_scores_by_issue(session: Session, *, owner_user_id: int) -> dict[int, RecommendationScoreV2]:
    rows = session.exec(
        select(RecommendationScoreV2)
        .where(RecommendationScoreV2.owner_user_id == owner_user_id)
        .where(RecommendationScoreV2.release_variant_id.is_(None))
        .order_by(RecommendationScoreV2.created_at.desc(), RecommendationScoreV2.id.desc())
    ).all()
    latest: dict[int, RecommendationScoreV2] = {}
    for row in rows:
        if row.release_issue_id not in latest:
            latest[row.release_issue_id] = row
    return latest


def generate_weekly_buy_list_v2(session: Session, *, owner_user_id: int, limit: int = 50) -> list[RecommendationScoreV2]:
    latest = _latest_scores_by_issue(session, owner_user_id=owner_user_id)
    horizon = date.today() + timedelta(days=45)
    ranked: list[RecommendationScoreV2] = []
    for score in latest.values():
        issue = session.get(ReleaseIssue, score.release_issue_id)
        if issue and issue.release_date and issue.release_date <= horizon:
            ranked.append(score)
    ranked.sort(key=lambda s: s.total_score, reverse=True)
    return ranked[:limit]


def get_recommendation_detail(session: Session, *, owner_user_id: int, score_id: int) -> tuple[
    RecommendationScoreV2,
    list[RecommendationScoreComponentV2],
    RecommendationDecisionV2 | None,
    ReleaseIssue,
    ReleaseSeries,
]:
    row = session.exec(
        select(RecommendationScoreV2).where(
            RecommendationScoreV2.id == score_id,
            RecommendationScoreV2.owner_user_id == owner_user_id,
        )
    ).first()
    if row is None:
        raise ValueError("Recommendation not found")
    components = session.exec(
        select(RecommendationScoreComponentV2)
        .where(RecommendationScoreComponentV2.recommendation_score_id == score_id)
        .order_by(RecommendationScoreComponentV2.id.asc())
    ).all()
    decision = session.exec(
        select(RecommendationDecisionV2).where(RecommendationDecisionV2.recommendation_score_id == score_id)
    ).first()
    issue = session.exec(select(ReleaseIssue).where(ReleaseIssue.id == row.release_issue_id)).first()
    if issue is None:
        raise ValueError("Issue not found")
    series = session.exec(select(ReleaseSeries).where(ReleaseSeries.id == issue.series_id)).first()
    if series is None:
        raise ValueError("Series not found")
    return row, list(components), decision, issue, series
