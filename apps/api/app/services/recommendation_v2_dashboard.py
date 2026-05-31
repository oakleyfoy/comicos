from __future__ import annotations

from sqlmodel import Session, select

from app.models.recommendation_v2 import RecommendationScoreV2
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.schemas.recommendation_v2 import RecommendationV2DashboardRead, RecommendationV2Read
from app.services.recommendation_v2_engine import _latest_scores_by_issue


def _read(session: Session, score: RecommendationScoreV2) -> RecommendationV2Read:
    issue = session.get(ReleaseIssue, score.release_issue_id)
    series = session.get(ReleaseSeries, issue.series_id) if issue else None
    return RecommendationV2Read(
        id=int(score.id or 0),
        release_issue_id=score.release_issue_id,
        release_variant_id=score.release_variant_id,
        series_name=series.series_name if series else "",
        issue_number=issue.issue_number if issue else "",
        title=issue.title if issue else "",
        publisher=series.publisher if series else "",
        total_score=float(score.total_score),
        recommendation_tier=score.recommendation_tier,
        recommendation_type=score.recommendation_type,
        confidence_score=float(score.confidence_score),
    )


def list_latest_recommendations_v2(
    session: Session,
    *,
    owner_user_id: int,
    limit: int,
    offset: int,
) -> tuple[list[RecommendationV2Read], int]:
    latest = _latest_scores_by_issue(session, owner_user_id=owner_user_id)
    ranked = sorted(latest.values(), key=lambda s: s.total_score, reverse=True)
    total = len(ranked)
    page = ranked[offset : offset + limit]
    return [_read(session, row) for row in page], total


def build_recommendations_v2_dashboard(session: Session, *, owner_user_id: int, limit: int = 25) -> RecommendationV2DashboardRead:
    rows = session.exec(
        select(RecommendationScoreV2)
        .where(RecommendationScoreV2.owner_user_id == owner_user_id)
        .order_by(RecommendationScoreV2.created_at.desc(), RecommendationScoreV2.id.desc())
    ).all()
    latest_issue = _latest_scores_by_issue(session, owner_user_id=owner_user_id)
    reads = [_read(session, s) for s in latest_issue.values()]

    def by_tier(tier: str) -> list[RecommendationV2Read]:
        return sorted([r for r in reads if r.recommendation_tier == tier], key=lambda r: r.total_score, reverse=True)[:limit]

    def by_type(rec_type: str) -> list[RecommendationV2Read]:
        return sorted([r for r in reads if r.recommendation_type == rec_type], key=lambda r: r.total_score, reverse=True)[:limit]

    variant_reads: list[RecommendationV2Read] = []
    seen_variant_issue: set[int] = set()
    for score in rows:
        if score.release_variant_id and score.release_issue_id not in seen_variant_issue:
            variant_reads.append(_read(session, score))
            seen_variant_issue.add(score.release_issue_id)
        if len(variant_reads) >= limit:
            break

    return RecommendationV2DashboardRead(
        must_buy=by_tier("MUST_BUY"),
        strong_buy=by_tier("STRONG_BUY"),
        buy=by_tier("BUY"),
        watch=by_tier("WATCH"),
        pass_tier=by_tier("PASS"),
        investment_number_ones=by_type("INVESTMENT_NUMBER_ONE"),
        start_run=by_type("START_RUN"),
        key_issues=by_type("KEY_ISSUE"),
        ratio_variants=by_type("RATIO_VARIANT") or variant_reads[:limit],
        user_preference_matches=by_type("USER_PREFERENCE_MATCH"),
    )
