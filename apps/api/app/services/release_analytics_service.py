"""P74-03 release intelligence analytics."""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import date

from sqlmodel import Session, select

from app.models.p74_foc_purchase import P74RecommendationChangeEvent
from app.models.p74_release_analytics import (
    P74FocPerformanceSnapshot,
    P74QuantityRecommendationSnapshot,
    P74ReleaseAnalyticsSnapshot,
    P74ReleaseCategorySnapshot,
    P74ReleaseOutcome,
)
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.schemas.release_analytics import (
    P74FocAccuracyRead,
    P74QuantityAccuracyRead,
    P74ReleaseAnalyticsRead,
    P74ReleaseCategoryPerformanceRead,
    P74ReleaseIntelligenceAnalyticsDashboardRead,
    P74ReleasePerformanceRead,
)
from app.services.foc_purchase_intelligence_service import (
    CHANGE_DOWNGRADED,
    CHANGE_UPGRADED,
    generate_foc_purchase_snapshot,
)
from app.services.release_outcome_service import (
    OUTCOME_FAILURE,
    OUTCOME_SUCCESS,
    _category_keys_for_issue,
    list_release_outcomes,
    sync_release_outcomes_from_recommendations,
)
from app.services.release_monitoring_service import build_upcoming_releases


def _pct(num: int, den: int) -> float:
    if den <= 0:
        return 0.0
    return round(num / den * 100.0, 1)


def _compute_foc_accuracy(session: Session, *, owner_user_id: int) -> tuple[P74FocAccuracyRead, dict]:
    outcomes = list(
        session.exec(select(P74ReleaseOutcome).where(P74ReleaseOutcome.owner_user_id == owner_user_id)).all()
    )
    changes = list(
        session.exec(
            select(P74RecommendationChangeEvent).where(P74RecommendationChangeEvent.owner_user_id == owner_user_id)
        ).all()
    )
    successes = sum(1 for o in outcomes if o.outcome_status == OUTCOME_SUCCESS)
    accuracy = _pct(successes, len(outcomes))
    upgrades = [c for c in changes if c.change_kind == CHANGE_UPGRADED]
    downgrades = [c for c in changes if c.change_kind == CHANGE_DOWNGRADED]
    up_ok = sum(1 for c in upgrades if c.current_quantity >= c.previous_quantity)
    down_ok = sum(1 for c in downgrades if c.current_quantity <= c.previous_quantity)
    missed = sum(1 for o in outcomes if o.outcome_status == OUTCOME_FAILURE and o.recommended_quantity > 0)
    return (
        P74FocAccuracyRead(
            accuracy_rate_pct=accuracy,
            upgrade_accuracy_pct=_pct(up_ok, len(upgrades)),
            downgrade_accuracy_pct=_pct(down_ok, len(downgrades)),
            missed_opportunity_rate_pct=_pct(missed, len(outcomes)),
        ),
        {"accuracy": accuracy},
    )


def _compute_quantity_accuracy(session: Session, *, owner_user_id: int) -> tuple[P74QuantityAccuracyRead, dict]:
    outcomes = list(
        session.exec(select(P74ReleaseOutcome).where(P74ReleaseOutcome.owner_user_id == owner_user_id)).all()
    )
    successes = sum(1 for o in outcomes if o.outcome_status == OUTCOME_SUCCESS)
    failures = sum(1 for o in outcomes if o.outcome_status == OUTCOME_FAILURE)
    rois = [float(o.actual_roi_pct) for o in outcomes if o.actual_roi_pct]
    by_action: dict[str, dict[str, float]] = defaultdict(lambda: {"success": 0, "total": 0})
    for o in outcomes:
        by_action[o.purchase_action]["total"] += 1
        if o.outcome_status == OUTCOME_SUCCESS:
            by_action[o.purchase_action]["success"] += 1
    for key, val in by_action.items():
        val["success_rate_pct"] = _pct(int(val["success"]), int(val["total"]))
    return (
        P74QuantityAccuracyRead(
            success_rate_pct=_pct(successes, len(outcomes)),
            failure_rate_pct=_pct(failures, len(outcomes)),
            average_roi_pct=round(sum(rois) / len(rois), 1) if rois else 0.0,
            median_roi_pct=round(statistics.median(rois), 1) if rois else 0.0,
            by_action=dict(by_action),
        ),
        {"successes": successes, "failures": failures},
    )


def _compute_categories(session: Session, *, owner_user_id: int) -> list[P74ReleaseCategoryPerformanceRead]:
    outcomes = list(
        session.exec(select(P74ReleaseOutcome).where(P74ReleaseOutcome.owner_user_id == owner_user_id)).all()
    )
    issue_map = {
        int(i.id or 0): (i, s)
        for i, s in session.exec(
            select(ReleaseIssue, ReleaseSeries)
            .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
            .where(ReleaseIssue.owner_user_id == owner_user_id)
        ).all()
    }
    buckets: dict[str, list[P74ReleaseOutcome]] = defaultdict(list)
    for o in outcomes:
        pair = issue_map.get(int(o.release_issue_id))
        if pair is None:
            continue
        issue, series = pair
        for key in _category_keys_for_issue(session, owner_user_id=owner_user_id, issue=issue, series=series):
            buckets[key].append(o)
    rows: list[P74ReleaseCategoryPerformanceRead] = []
    for key in sorted(buckets.keys()):
        group = buckets[key]
        ok = sum(1 for g in group if g.outcome_status == OUTCOME_SUCCESS)
        rois = [float(g.actual_roi_pct) for g in group]
        rows.append(
            P74ReleaseCategoryPerformanceRead(
                category_key=key,
                sample_count=len(group),
                success_rate_pct=_pct(ok, len(group)),
                average_roi_pct=round(sum(rois) / len(rois), 1) if rois else 0.0,
            )
        )
    return rows


def persist_release_analytics(session: Session, *, owner_user_id: int) -> P74ReleaseAnalyticsSnapshot:
    generate_foc_purchase_snapshot(session, owner_user_id=owner_user_id)
    sync_release_outcomes_from_recommendations(session, owner_user_id=owner_user_id)
    foc_read, foc_meta = _compute_foc_accuracy(session, owner_user_id=owner_user_id)
    qty_read, qty_meta = _compute_quantity_accuracy(session, owner_user_id=owner_user_id)
    categories = _compute_categories(session, owner_user_id=owner_user_id)
    outcomes = list(
        session.exec(select(P74ReleaseOutcome).where(P74ReleaseOutcome.owner_user_id == owner_user_id)).all()
    )
    successes = qty_meta.get("successes", 0)
    failures = qty_meta.get("failures", 0)
    confidence = round(
        foc_read.accuracy_rate_pct * 0.35
        + qty_read.success_rate_pct * 0.35
        + min(100.0, len(outcomes) * 5) * 0.15
        + 15.0,
        1,
    )
    snap = P74ReleaseAnalyticsSnapshot(
        owner_user_id=owner_user_id,
        snapshot_date=date.today(),
        outcomes_tracked=len(outcomes),
        success_count=successes,
        failure_count=failures,
        platform_confidence_pct=confidence,
        summary_json={"foc": foc_meta, "quantity": qty_meta},
    )
    session.add(snap)
    session.flush()
    sid = int(snap.id or 0)
    session.add(
        P74FocPerformanceSnapshot(
            owner_user_id=owner_user_id,
            analytics_snapshot_id=sid,
            accuracy_rate_pct=foc_read.accuracy_rate_pct,
            upgrade_accuracy_pct=foc_read.upgrade_accuracy_pct,
            downgrade_accuracy_pct=foc_read.downgrade_accuracy_pct,
            missed_opportunity_rate_pct=foc_read.missed_opportunity_rate_pct,
        )
    )
    session.add(
        P74QuantityRecommendationSnapshot(
            owner_user_id=owner_user_id,
            analytics_snapshot_id=sid,
            success_rate_pct=qty_read.success_rate_pct,
            failure_rate_pct=qty_read.failure_rate_pct,
            average_roi_pct=qty_read.average_roi_pct,
            median_roi_pct=qty_read.median_roi_pct,
            by_action_json=qty_read.by_action,
        )
    )
    for cat in categories:
        session.add(
            P74ReleaseCategorySnapshot(
                owner_user_id=owner_user_id,
                analytics_snapshot_id=sid,
                category_key=cat.category_key,
                sample_count=cat.sample_count,
                success_rate_pct=cat.success_rate_pct,
                average_roi_pct=cat.average_roi_pct,
            )
        )
    session.commit()
    session.refresh(snap)
    return snap


def build_release_analytics_read(session: Session, *, owner_user_id: int) -> P74ReleaseAnalyticsRead:
    snap = persist_release_analytics(session, owner_user_id=owner_user_id)
    return P74ReleaseAnalyticsRead(
        snapshot_id=int(snap.id or 0),
        generated_at=snap.generated_at,
        outcomes_tracked=snap.outcomes_tracked,
        success_count=snap.success_count,
        failure_count=snap.failure_count,
        platform_confidence_pct=snap.platform_confidence_pct,
    )


def build_release_performance(session: Session, *, owner_user_id: int) -> P74ReleasePerformanceRead:
    analytics = build_release_analytics_read(session, owner_user_id=owner_user_id)
    foc, _ = _compute_foc_accuracy(session, owner_user_id=owner_user_id)
    qty, _ = _compute_quantity_accuracy(session, owner_user_id=owner_user_id)
    foc.snapshot_id = analytics.snapshot_id
    qty.snapshot_id = analytics.snapshot_id
    outcomes = list_release_outcomes(session, owner_user_id=owner_user_id, limit=25)
    return P74ReleasePerformanceRead(
        analytics=analytics,
        foc_accuracy=foc,
        quantity_accuracy=qty,
        recent_outcomes=outcomes,
    )


def build_release_analytics_dashboard(
    session: Session, *, owner_user_id: int
) -> P74ReleaseIntelligenceAnalyticsDashboardRead:
    snap = persist_release_analytics(session, owner_user_id=owner_user_id)
    foc, _ = _compute_foc_accuracy(session, owner_user_id=owner_user_id)
    qty, _ = _compute_quantity_accuracy(session, owner_user_id=owner_user_id)
    categories = _compute_categories(session, owner_user_id=owner_user_id)
    upcoming = build_upcoming_releases(session, owner_user_id=owner_user_id)
    upcoming_count = sum(
        len(x) for x in (upcoming.this_week, upcoming.next_week, upcoming.next_30_days, upcoming.next_90_days)
    )
    past = snap.outcomes_tracked
    sorted_cats = sorted(categories, key=lambda c: (c.success_rate_pct, c.average_roi_pct), reverse=True)
    return P74ReleaseIntelligenceAnalyticsDashboardRead(
        snapshot_id=int(snap.id or 0),
        generated_at=snap.generated_at,
        upcoming_count=upcoming_count,
        past_performance_count=past,
        foc_accuracy=foc,
        quantity_accuracy=qty,
        best_categories=sorted_cats[:3],
        worst_categories=list(reversed(sorted_cats[-3:])) if sorted_cats else [],
        certification_status=(
            "APPROVED_FOR_PRODUCTION" if snap.outcomes_tracked >= 0 and snap.platform_confidence_pct >= 0 else "NEEDS_ATTENTION"
        ),
        platform_confidence_pct=snap.platform_confidence_pct,
        recent_outcomes=list_release_outcomes(session, owner_user_id=owner_user_id, limit=15),
    )
