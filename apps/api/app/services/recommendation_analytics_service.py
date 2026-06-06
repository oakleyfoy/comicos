"""P73-02 recommendation performance analytics (P73-01 outcomes only; no ranking changes)."""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlmodel import Session, select

from app.models.recommendation_action_event import P73RecommendationActionEvent
from app.models.recommendation_category_performance import P73RecommendationCategoryPerformance
from app.models.recommendation_outcome import P73RecommendationOutcome
from app.models.recommendation_performance_snapshot import P73RecommendationPerformanceSnapshot
from app.models.recommendation_profitability_snapshot import P73RecommendationProfitabilitySnapshot
from app.schemas.recommendation_analytics import (
    P73RecommendationAccuracyMetricsRead,
    P73RecommendationAdoptionMetricsRead,
    P73RecommendationAnalyticsRead,
    P73RecommendationAttributionAnalyticsRead,
    P73RecommendationCategoryPerformanceRead,
    P73RecommendationFunnelCountsRead,
    P73RecommendationOutcomeHighlightRead,
    P73RecommendationPerformanceDashboardRead,
    P73RecommendationPerformanceRead,
    P73RecommendationProfitabilityBreakdownRowRead,
    P73RecommendationProfitabilityRead,
)

WATCH_TYPES = frozenset({"WATCH", "WATCHLIST", "WATCH_LIST"})
SUCCESS_STATUSES = frozenset({"PURCHASED", "GRADED", "SOLD", "LISTED"})
FAILURE_STATUSES = frozenset({"SKIPPED"})

ATTRIBUTION_CATEGORIES = (
    "FIRST_APPEARANCE",
    "VARIANT",
    "KEY_ISSUE",
    "PUBLISHER_EVENT",
    "CREATOR_EVENT",
    "GENERAL",
)


def _pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator * 100.0, 1)


def _decimal_or_zero(value: Decimal | None) -> Decimal:
    if value is None:
        return Decimal("0")
    return value


def _float_roi(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _outcome_has_event(events_by_outcome: dict[int, set[str]], outcome_id: int, event_type: str) -> bool:
    return event_type in events_by_outcome.get(outcome_id, set())


def _load_owner_data(
    session: Session, owner_user_id: int
) -> tuple[list[P73RecommendationOutcome], dict[int, set[str]]]:
    outcomes = list(
        session.exec(
            select(P73RecommendationOutcome).where(P73RecommendationOutcome.owner_user_id == owner_user_id)
        ).all()
    )
    events = list(
        session.exec(
            select(P73RecommendationActionEvent).where(P73RecommendationActionEvent.owner_user_id == owner_user_id)
        ).all()
    )
    events_by_outcome: dict[int, set[str]] = defaultdict(set)
    for e in events:
        events_by_outcome[int(e.outcome_id)].add(e.event_type)
    return outcomes, events_by_outcome


def _funnel_counts(
    outcomes: list[P73RecommendationOutcome], events_by_outcome: dict[int, set[str]]
) -> P73RecommendationFunnelCountsRead:
    generated = len(outcomes)
    viewed = sum(1 for o in outcomes if _outcome_has_event(events_by_outcome, int(o.id or 0), "VIEWED"))
    purchased = sum(1 for o in outcomes if _outcome_has_event(events_by_outcome, int(o.id or 0), "PURCHASED"))
    skipped = sum(1 for o in outcomes if _outcome_has_event(events_by_outcome, int(o.id or 0), "SKIPPED"))
    held = sum(1 for o in outcomes if _outcome_has_event(events_by_outcome, int(o.id or 0), "HELD"))
    graded = sum(1 for o in outcomes if _outcome_has_event(events_by_outcome, int(o.id or 0), "GRADED"))
    sold = sum(1 for o in outcomes if _outcome_has_event(events_by_outcome, int(o.id or 0), "SOLD"))
    return P73RecommendationFunnelCountsRead(
        recommendations_generated=generated,
        viewed=viewed,
        purchased=purchased,
        skipped=skipped,
        held=held,
        graded=graded,
        sold=sold,
    )


def _adoption_metrics(
    funnel: P73RecommendationFunnelCountsRead,
    outcomes: list[P73RecommendationOutcome],
    events_by_outcome: dict[int, set[str]],
) -> P73RecommendationAdoptionMetricsRead:
    base = funnel.recommendations_generated
    watchlisted = sum(
        1 for o in outcomes if _outcome_has_event(events_by_outcome, int(o.id or 0), "WATCHLISTED")
    )
    return P73RecommendationAdoptionMetricsRead(
        view_rate_pct=_pct(funnel.viewed, base),
        purchase_rate_pct=_pct(funnel.purchased, base),
        watchlist_rate_pct=_pct(watchlisted, base),
        grade_rate_pct=_pct(funnel.graded, base),
        sell_rate_pct=_pct(funnel.sold, base),
    )


def _returns_for_outcomes(outcomes: list[P73RecommendationOutcome]) -> list[float]:
    returns: list[float] = []
    for o in outcomes:
        roi = _float_roi(o.actual_roi_pct)
        if roi is not None:
            returns.append(roi)
    return returns


def _accuracy_metrics(
    outcomes: list[P73RecommendationOutcome], events_by_outcome: dict[int, set[str]]
) -> P73RecommendationAccuracyMetricsRead:
    samples = [o for o in outcomes if o.attribution_accurate is not None]
    success = sum(1 for o in samples if o.attribution_accurate is True)
    failure = sum(1 for o in samples if o.attribution_accurate is False)
    denom = len(samples)
    returns = _returns_for_outcomes(outcomes)
    avg_ret = round(sum(returns) / len(returns), 1) if returns else 0.0
    med_ret = round(statistics.median(returns), 1) if returns else 0.0
    wins = sum(1 for r in returns if r > 0)
    losses = sum(1 for r in returns if r < 0)
    ret_denom = len(returns)
    closed_fail = sum(
        1
        for o in outcomes
        if o.current_status in FAILURE_STATUSES
        or _outcome_has_event(events_by_outcome, int(o.id or 0), "SKIPPED")
    )
    closed_success = sum(
        1
        for o in outcomes
        if o.attribution_accurate is True
        or o.current_status in SUCCESS_STATUSES
    )
    total_closed = max(len(outcomes), 1)
    return P73RecommendationAccuracyMetricsRead(
        success_rate_pct=_pct(success, denom) if denom else _pct(closed_success, total_closed),
        failure_rate_pct=_pct(failure, denom) if denom else _pct(closed_fail, total_closed),
        average_return_pct=avg_ret,
        median_return_pct=med_ret,
        win_rate_pct=_pct(wins, ret_denom),
        loss_rate_pct=_pct(losses, ret_denom),
    )


def _breakdown_rows(
    outcomes: list[P73RecommendationOutcome],
    key_fn,
) -> list[P73RecommendationProfitabilityBreakdownRowRead]:
    buckets: dict[str, list[P73RecommendationOutcome]] = defaultdict(list)
    for o in outcomes:
        key = key_fn(o) or "Unknown"
        buckets[key].append(o)
    rows: list[P73RecommendationProfitabilityBreakdownRowRead] = []
    for key, group in sorted(buckets.items(), key=lambda kv: kv[0]):
        exp_p = sum(_decimal_or_zero(o.expected_profit) for o in group)
        act_p = sum(_decimal_or_zero(o.actual_profit) for o in group)
        exp_rois = [_float_roi(o.expected_roi_pct) for o in group if o.expected_roi_pct is not None]
        act_rois = [_float_roi(o.actual_roi_pct) for o in group if o.actual_roi_pct is not None]
        rows.append(
            P73RecommendationProfitabilityBreakdownRowRead(
                key=key,
                expected_profit=exp_p,
                actual_profit=act_p,
                expected_roi_pct=round(sum(exp_rois) / len(exp_rois), 1) if exp_rois else 0.0,
                actual_roi_pct=round(sum(act_rois) / len(act_rois), 1) if act_rois else 0.0,
                sample_count=len(group),
            )
        )
    return rows


def build_profitability_read(
    outcomes: list[P73RecommendationOutcome],
) -> P73RecommendationProfitabilityRead:
    exp_p = sum(_decimal_or_zero(o.expected_profit) for o in outcomes)
    act_p = sum(_decimal_or_zero(o.actual_profit) for o in outcomes)
    exp_rois = [_float_roi(o.expected_roi_pct) for o in outcomes if o.expected_roi_pct is not None]
    act_rois = [_float_roi(o.actual_roi_pct) for o in outcomes if o.actual_roi_pct is not None]
    return P73RecommendationProfitabilityRead(
        expected_profit=exp_p,
        actual_profit=act_p,
        expected_roi_pct=round(sum(exp_rois) / len(exp_rois), 1) if exp_rois else 0.0,
        actual_roi_pct=round(sum(act_rois) / len(act_rois), 1) if act_rois else 0.0,
        by_publisher=_breakdown_rows(outcomes, lambda o: o.publisher.strip() or "Unknown"),
        by_series=_breakdown_rows(outcomes, lambda o: o.series.strip() or "Unknown"),
        by_character=_breakdown_rows(outcomes, lambda o: o.character.strip() or "Unknown"),
        by_creator=_breakdown_rows(outcomes, lambda o: o.creator.strip() or "Unknown"),
        by_recommendation_category=_breakdown_rows(
            outcomes, lambda o: o.recommendation_category.strip() or "GENERAL"
        ),
    )


def _normalize_rec_type(raw: str) -> str:
    t = raw.strip().upper().replace(" ", "_")
    if t in WATCH_TYPES or t.startswith("WATCH"):
        return "WATCH"
    if t.startswith("BUY"):
        return "BUY"
    if t.startswith("GRADE"):
        return "GRADE"
    if t in {"SELL", "SELL_NOW", "FLIP"}:
        return "SELL"
    return t or "OTHER"


def build_category_performance_read(
    outcomes: list[P73RecommendationOutcome],
) -> list[P73RecommendationCategoryPerformanceRead]:
    groups: dict[str, list[P73RecommendationOutcome]] = defaultdict(list)
    for o in outcomes:
        groups[_normalize_rec_type(o.recommendation_type)].append(o)
    result: list[P73RecommendationCategoryPerformanceRead] = []
    for rec_type in ("BUY", "GRADE", "SELL", "WATCH"):
        group = groups.get(rec_type, [])
        if not group:
            result.append(
                P73RecommendationCategoryPerformanceRead(
                    recommendation_type=rec_type,
                    recommendation_count=0,
                    success_rate_pct=0.0,
                    average_roi_pct=0.0,
                )
            )
            continue
        successes = sum(1 for o in group if o.attribution_accurate is True)
        samples = sum(1 for o in group if o.attribution_accurate is not None)
        rois = [_float_roi(o.actual_roi_pct) for o in group if o.actual_roi_pct is not None]
        result.append(
            P73RecommendationCategoryPerformanceRead(
                recommendation_type=rec_type,
                recommendation_count=len(group),
                success_rate_pct=_pct(successes, samples) if samples else 0.0,
                average_roi_pct=round(sum(r for r in rois if r is not None) / len(rois), 1) if rois else 0.0,
            )
        )
    return result


def build_attribution_analytics_read(
    outcomes: list[P73RecommendationOutcome],
    events_by_outcome: dict[int, set[str]],
) -> list[P73RecommendationAttributionAnalyticsRead]:
    by_cat: dict[str, list[P73RecommendationOutcome]] = defaultdict(list)
    for o in outcomes:
        cat = (o.recommendation_category or "GENERAL").strip().upper()
        if cat not in ATTRIBUTION_CATEGORIES:
            cat = "GENERAL"
        by_cat[cat].append(o)
    rows: list[P73RecommendationAttributionAnalyticsRead] = []
    for cat in ATTRIBUTION_CATEGORIES:
        group = by_cat.get(cat, [])
        if not group:
            continue
        oid = lambda o: int(o.id or 0)
        purchases = sum(1 for o in group if _outcome_has_event(events_by_outcome, oid(o), "PURCHASED"))
        gradings = sum(1 for o in group if _outcome_has_event(events_by_outcome, oid(o), "GRADED"))
        sales = sum(1 for o in group if _outcome_has_event(events_by_outcome, oid(o), "SOLD"))
        profit = sum(_decimal_or_zero(o.actual_profit) for o in group)
        rows.append(
            P73RecommendationAttributionAnalyticsRead(
                category=cat,
                outcomes=len(group),
                purchases=purchases,
                gradings=gradings,
                sales=sales,
                profit_total=profit,
            )
        )
    return rows


def _highlights(
    outcomes: list[P73RecommendationOutcome], *, best: bool, limit: int = 5
) -> list[P73RecommendationOutcomeHighlightRead]:
    with_roi = [o for o in outcomes if o.actual_roi_pct is not None]
    with_roi.sort(key=lambda o: float(o.actual_roi_pct or 0), reverse=best)
    picks = with_roi[:limit] if with_roi else outcomes[:limit]
    return [
        P73RecommendationOutcomeHighlightRead(
            outcome_id=int(o.id or 0),
            recommendation_id=o.recommendation_id,
            series=o.series,
            issue=o.issue,
            recommendation_type=o.recommendation_type,
            actual_roi_pct=_float_roi(o.actual_roi_pct),
            actual_profit=o.actual_profit,
            attribution_accurate=o.attribution_accurate,
        )
        for o in picks
    ]


def persist_performance_snapshot(
    session: Session,
    *,
    owner_user_id: int,
    funnel: P73RecommendationFunnelCountsRead,
    adoption: P73RecommendationAdoptionMetricsRead,
    accuracy: P73RecommendationAccuracyMetricsRead,
    profitability: P73RecommendationProfitabilityRead,
    categories: list[P73RecommendationCategoryPerformanceRead],
    attribution: list[P73RecommendationAttributionAnalyticsRead],
) -> P73RecommendationPerformanceSnapshot:
    snap = P73RecommendationPerformanceSnapshot(
        owner_user_id=owner_user_id,
        snapshot_date=date.today(),
        recommendations_generated=funnel.recommendations_generated,
        viewed=funnel.viewed,
        purchased=funnel.purchased,
        skipped=funnel.skipped,
        held=funnel.held,
        graded=funnel.graded,
        sold=funnel.sold,
        view_rate_pct=adoption.view_rate_pct,
        purchase_rate_pct=adoption.purchase_rate_pct,
        watchlist_rate_pct=adoption.watchlist_rate_pct,
        grade_rate_pct=adoption.grade_rate_pct,
        sell_rate_pct=adoption.sell_rate_pct,
        success_rate_pct=accuracy.success_rate_pct,
        failure_rate_pct=accuracy.failure_rate_pct,
        average_return_pct=accuracy.average_return_pct,
        median_return_pct=accuracy.median_return_pct,
        win_rate_pct=accuracy.win_rate_pct,
        loss_rate_pct=accuracy.loss_rate_pct,
        metadata_json={"attribution": [a.model_dump(mode="json") for a in attribution]},
    )
    session.add(snap)
    session.flush()
    profit_row = P73RecommendationProfitabilitySnapshot(
        owner_user_id=owner_user_id,
        performance_snapshot_id=int(snap.id or 0),
        expected_profit=profitability.expected_profit,
        actual_profit=profitability.actual_profit,
        expected_roi_pct=profitability.expected_roi_pct,
        actual_roi_pct=profitability.actual_roi_pct,
        breakdown_json={
            "by_publisher": [r.model_dump(mode="json") for r in profitability.by_publisher],
            "by_series": [r.model_dump(mode="json") for r in profitability.by_series],
            "by_character": [r.model_dump(mode="json") for r in profitability.by_character],
            "by_creator": [r.model_dump(mode="json") for r in profitability.by_creator],
            "by_recommendation_category": [
                r.model_dump(mode="json") for r in profitability.by_recommendation_category
            ],
        },
    )
    session.add(profit_row)
    for cat in categories:
        session.add(
            P73RecommendationCategoryPerformance(
                owner_user_id=owner_user_id,
                performance_snapshot_id=int(snap.id or 0),
                recommendation_type=cat.recommendation_type,
                recommendation_count=cat.recommendation_count,
                success_rate_pct=cat.success_rate_pct,
                average_roi_pct=cat.average_roi_pct,
            )
        )
    session.commit()
    session.refresh(snap)
    return snap


def build_recommendation_analytics(
    session: Session, *, owner_user_id: int, persist: bool = True
) -> P73RecommendationAnalyticsRead:
    outcomes, events_by_outcome = _load_owner_data(session, owner_user_id)
    funnel = _funnel_counts(outcomes, events_by_outcome)
    adoption = _adoption_metrics(funnel, outcomes, events_by_outcome)
    accuracy = _accuracy_metrics(outcomes, events_by_outcome)
    profitability = build_profitability_read(outcomes)
    categories = build_category_performance_read(outcomes)
    attribution = build_attribution_analytics_read(outcomes, events_by_outcome)
    snap_id = 0
    generated_at = datetime.now(timezone.utc)
    if persist:
        snap = persist_performance_snapshot(
            session,
            owner_user_id=owner_user_id,
            funnel=funnel,
            adoption=adoption,
            accuracy=accuracy,
            profitability=profitability,
            categories=categories,
            attribution=attribution,
        )
        snap_id = int(snap.id or 0)
        generated_at = snap.generated_at
    return P73RecommendationAnalyticsRead(
        snapshot_id=snap_id,
        snapshot_date=date.today(),
        generated_at=generated_at,
        funnel=funnel,
        adoption=adoption,
        accuracy=accuracy,
    )


def build_recommendation_performance(
    session: Session, *, owner_user_id: int
) -> P73RecommendationPerformanceRead:
    analytics = build_recommendation_analytics(session, owner_user_id=owner_user_id, persist=True)
    return P73RecommendationPerformanceRead(
        snapshot_id=analytics.snapshot_id,
        generated_at=analytics.generated_at,
        funnel=analytics.funnel,
        adoption=analytics.adoption,
        accuracy=analytics.accuracy,
    )


def build_recommendation_profitability(
    session: Session, *, owner_user_id: int
) -> P73RecommendationProfitabilityRead:
    outcomes, _ = _load_owner_data(session, owner_user_id)
    return build_profitability_read(outcomes)


def build_recommendation_categories(
    session: Session, *, owner_user_id: int
) -> list[P73RecommendationCategoryPerformanceRead]:
    outcomes, _ = _load_owner_data(session, owner_user_id)
    return build_category_performance_read(outcomes)


def build_recommendation_performance_dashboard(
    session: Session, *, owner_user_id: int
) -> P73RecommendationPerformanceDashboardRead:
    outcomes, events_by_outcome = _load_owner_data(session, owner_user_id)
    funnel = _funnel_counts(outcomes, events_by_outcome)
    adoption = _adoption_metrics(funnel, outcomes, events_by_outcome)
    accuracy = _accuracy_metrics(outcomes, events_by_outcome)
    profitability = build_profitability_read(outcomes)
    categories = build_category_performance_read(outcomes)
    attribution = build_attribution_analytics_read(outcomes, events_by_outcome)
    snap = persist_performance_snapshot(
        session,
        owner_user_id=owner_user_id,
        funnel=funnel,
        adoption=adoption,
        accuracy=accuracy,
        profitability=profitability,
        categories=categories,
        attribution=attribution,
    )
    performance = P73RecommendationPerformanceRead(
        snapshot_id=int(snap.id or 0),
        generated_at=snap.generated_at,
        funnel=funnel,
        adoption=adoption,
        accuracy=accuracy,
    )
    return P73RecommendationPerformanceDashboardRead(
        performance_summary=performance,
        adoption_metrics=adoption,
        profitability_metrics=profitability,
        category_performance=categories,
        attribution_analytics=attribution,
        top_wins=_highlights(outcomes, best=True),
        worst_outcomes=_highlights(outcomes, best=False),
    )
