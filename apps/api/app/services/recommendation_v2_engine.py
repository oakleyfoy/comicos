from __future__ import annotations

import time
from collections.abc import Callable
from datetime import date, timedelta

from sqlmodel import Session, select

from app.services.recommendation_forward_window import (
    FORWARD_RECOMMENDATION_WINDOW_DAYS,
    issue_in_forward_recommendation_window,
)
from app.services.foc_dates import utc_today
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
from app.services.recommendation_v2_scoring_context import build_recommendation_v2_scoring_context
from app.services.user_preference_engine import refresh_user_preferences

PROGRESS_EVERY_ISSUES = 50
COMMIT_BATCH_SIZE = 100
SLOW_STEP_SECONDS = 60.0


def score_release_issue_v2(
    session: Session,
    *,
    owner_user_id: int,
    run_id: int,
    issue: ReleaseIssue,
    series: ReleaseSeries,
    scoring_ctx=None,
) -> RecommendationScoreV2:
    bundle = score_issue_components_v2(
        session,
        owner_user_id=owner_user_id,
        issue=issue,
        series=series,
        ctx=scoring_ctx,
    )
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
    scoring_ctx=None,
) -> RecommendationScoreV2:
    bundle = score_issue_components_v2(
        session,
        owner_user_id=owner_user_id,
        issue=issue,
        series=series,
        variant=variant,
        ctx=scoring_ctx,
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


def generate_recommendations_v2(
    session: Session,
    *,
    owner_user_id: int,
    progress_callback: Callable[[str], None] | None = None,
) -> RecommendationRunV2:
    def _progress(message: str) -> None:
        if progress_callback is not None:
            progress_callback(message)

    def _timed_step(label: str, fn: Callable[[], None]) -> None:
        started = time.monotonic()
        _progress(f"{label} start")
        fn()
        elapsed = time.monotonic() - started
        _progress(f"{label} done secs={elapsed:.1f}")
        if elapsed >= SLOW_STEP_SECONDS:
            _progress(f"SLOW STEP (>{int(SLOW_STEP_SECONDS)}s): {label} took {elapsed:.1f}s")

    def _timed_step_value(label: str, fn: Callable[[], object]) -> object:
        started = time.monotonic()
        _progress(f"{label} start")
        result = fn()
        elapsed = time.monotonic() - started
        _progress(f"{label} done secs={elapsed:.1f}")
        if elapsed >= SLOW_STEP_SECONDS:
            _progress(f"SLOW STEP (>{int(SLOW_STEP_SECONDS)}s): {label} took {elapsed:.1f}s")
        return result

    _timed_step("refresh_market_demand", lambda: refresh_market_demand(session))
    _timed_step(
        "refresh_user_preferences",
        lambda: refresh_user_preferences(session, owner_user_id=owner_user_id),
    )

    run = RecommendationRunV2(owner_user_id=owner_user_id, status="RUNNING")
    session.add(run)
    session.commit()
    session.refresh(run)
    run_id = int(run.id or 0)

    issues_scored = 0
    variants_scored = 0
    created = 0

    load_started = time.monotonic()
    catalog_rows = session.exec(
        select(ReleaseIssue, ReleaseSeries)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .order_by(ReleaseIssue.release_date.asc(), ReleaseIssue.id.asc())
    ).all()
    load_elapsed = time.monotonic() - load_started
    _progress(f"load_release_issues rows={len(catalog_rows)} secs={load_elapsed:.1f}")
    if load_elapsed >= SLOW_STEP_SECONDS:
        _progress(f"SLOW QUERY (>{int(SLOW_STEP_SECONDS)}s): load_release_issues took {load_elapsed:.1f}s")

    _progress(
        f"filter_forward_window start window_days={FORWARD_RECOMMENDATION_WINDOW_DAYS} "
        f"catalog_rows={len(catalog_rows)}"
    )
    filter_started = time.monotonic()
    ref_today = utc_today()
    rows = [
        (issue, series)
        for issue, series in catalog_rows
        if issue_in_forward_recommendation_window(issue, today=ref_today)
    ]
    filter_elapsed = time.monotonic() - filter_started
    _progress(
        f"filter_forward_window done forward_rows={len(rows)} "
        f"catalog_rows={len(catalog_rows)} secs={filter_elapsed:.1f}"
    )
    if not rows:
        _progress("score_loop skipped no issues in forward window")
        run.issues_scored = 0
        run.variants_scored = 0
        run.recommendations_created = 0
        run.status = "COMPLETED"
        run.completed_at = utc_now()
        session.add(run)
        session.commit()
        session.refresh(run)
        return run

    issue_ids = [int(issue.id or 0) for issue, _ in rows if issue.id is not None]
    scoring_ctx = _timed_step_value(
        "preload_scoring_context",
        lambda: build_recommendation_v2_scoring_context(
            session,
            owner_user_id=owner_user_id,
            issue_ids=issue_ids,
        ),
    )
    _progress(
        f"score_loop start forward_issues={len(rows)} "
        f"variants_preloaded={sum(len(v) for v in scoring_ctx.variants_by_issue.values())} "
        f"progress_every={PROGRESS_EVERY_ISSUES}"
    )

    batch_started = time.monotonic()
    since_commit = 0
    for issue, series in rows:
        score_release_issue_v2(
            session,
            owner_user_id=owner_user_id,
            run_id=run_id,
            issue=issue,
            series=series,
            scoring_ctx=scoring_ctx,
        )
        issues_scored += 1
        created += 1
        since_commit += 1
        for variant in scoring_ctx.variants_for(int(issue.id or 0)):
            if variant.ratio_value or variant.is_incentive_variant:
                score_release_variant_v2(
                    session,
                    owner_user_id=owner_user_id,
                    run_id=run_id,
                    issue=issue,
                    series=series,
                    variant=variant,
                    scoring_ctx=scoring_ctx,
                )
                variants_scored += 1
                created += 1
                since_commit += 1
        if issues_scored % PROGRESS_EVERY_ISSUES == 0 or issues_scored == len(rows):
            batch_elapsed = time.monotonic() - batch_started
            _progress(
                f"score_progress issues={issues_scored}/{len(rows)} "
                f"variants={variants_scored} batch_secs={batch_elapsed:.1f}"
            )
            if batch_elapsed >= SLOW_STEP_SECONDS:
                _progress(
                    f"SLOW BATCH (>{int(SLOW_STEP_SECONDS)}s): scored {PROGRESS_EVERY_ISSUES} issues "
                    f"in {batch_elapsed:.1f}s (total issues={issues_scored}/{len(rows)})"
                )
            batch_started = time.monotonic()
        if since_commit >= COMMIT_BATCH_SIZE:
            session.commit()
            since_commit = 0

    if since_commit:
        session.commit()

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
    horizon = date.today() + timedelta(days=FORWARD_RECOMMENDATION_WINDOW_DAYS)
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
