"""P37-08 deterministic dealer grading dashboard aggregation."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Callable, TypeVar

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.models import (
    DealerGradingDashboardAlert,
    DealerGradingDashboardFeedEvent,
    DealerGradingDashboardMetric,
    DealerGradingDashboardSnapshot,
    GraderPerformanceSnapshot,
    GradingCandidate,
    GradingReconciliationRecord,
    GradingRecommendation,
    GradingRiskSnapshot,
    GradingSubmissionBatch,
    GradingSubmissionLifecycleEvent,
    InventoryLiquiditySnapshot,
)
from app.schemas.dealer_grading_dashboard import (
    DealerGradingDashboardAlertListResponse,
    DealerGradingDashboardAlertRead,
    DealerGradingDashboardFeedEventRead,
    DealerGradingDashboardFeedListResponse,
    DealerGradingDashboardGeneratePayload,
    DealerGradingDashboardGenerateResponse,
    DealerGradingDashboardGetResponse,
    DealerGradingDashboardMetricListResponse,
    DealerGradingDashboardMetricRead,
    DealerGradingDashboardSnapshotRead,
)

AGGREGATION_VERSION = "p37-08:v1"
MONEY_QUANT = Decimal("0.01")
ROI_QUANT = Decimal("0.00000001")
ZERO = Decimal("0.00")
ACTIVE_BATCH_STATUSES = {"DRAFT", "READY", "SHIPPED", "RECEIVED_BY_GRADER", "GRADING", "RETURN_SHIPPED"}
TERMINAL_CANDIDATE_STATUSES = {"GRADED", "ARCHIVED", "CANCELLED"}

T = TypeVar("T")


def clamp_dealer_grading_dashboard_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 500), max(offset, 0)


def _decimal(value: Any | None) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _money(value: Any | None) -> Decimal:
    return _decimal(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _pct(value: Any | None) -> Decimal:
    return _decimal(value).quantize(ROI_QUANT, rounding=ROUND_HALF_UP)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        quant = MONEY_QUANT if value == value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP) else ROI_QUANT
        return str(value.quantize(quant, rounding=ROUND_HALF_UP))
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _hash_payload(payload: dict[str, Any]) -> str:
    raw = json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


def _snapshot_read(row: DealerGradingDashboardSnapshot) -> DealerGradingDashboardSnapshotRead:
    return DealerGradingDashboardSnapshotRead.model_validate(row, from_attributes=True)


def _latest_rows(
    rows: list[T],
    *,
    key_fn: Callable[[T], Any],
    sort_key_fn: Callable[[T], tuple[Any, ...]],
) -> list[T]:
    latest: dict[Any, T] = {}
    for row in sorted(rows, key=sort_key_fn, reverse=True):
        latest.setdefault(key_fn(row), row)
    return sorted(latest.values(), key=sort_key_fn)


def _scoped_key(*values: Any) -> tuple[str, ...]:
    normalized = ["" if value is None else str(value) for value in values]
    return tuple(normalized)


def _recommendation_scope(row: GradingRecommendation) -> tuple[str, ...]:
    return _scoped_key(row.grading_candidate_id, row.inventory_item_id, row.canonical_comic_issue_id)


def _risk_scope(row: GradingRiskSnapshot) -> tuple[str, ...]:
    return _scoped_key(row.grading_candidate_id, row.inventory_item_id, row.canonical_comic_issue_id, row.recommendation_id)


def _liquidity_scope(row: InventoryLiquiditySnapshot) -> tuple[str, ...]:
    return _scoped_key(row.inventory_item_id, row.canonical_comic_issue_id, row.channel)


def latest_snapshot_for_owner(session: Session, *, owner_user_id: int) -> DealerGradingDashboardSnapshot | None:
    return session.exec(
        select(DealerGradingDashboardSnapshot)
        .where(DealerGradingDashboardSnapshot.owner_user_id == owner_user_id)
        .order_by(col(DealerGradingDashboardSnapshot.snapshot_date).desc())
        .order_by(col(DealerGradingDashboardSnapshot.created_at).desc())
        .order_by(col(DealerGradingDashboardSnapshot.id).desc())
    ).first()


def latest_snapshot_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
) -> DealerGradingDashboardSnapshot | None:
    stmt = select(DealerGradingDashboardSnapshot).order_by(
        col(DealerGradingDashboardSnapshot.snapshot_date).desc(),
        col(DealerGradingDashboardSnapshot.created_at).desc(),
        col(DealerGradingDashboardSnapshot.id).desc(),
    )
    if owner_user_id is not None:
        stmt = stmt.where(DealerGradingDashboardSnapshot.owner_user_id == owner_user_id)
    return session.exec(stmt).first()


def get_dashboard_owner(session: Session, *, owner_user_id: int) -> DealerGradingDashboardGetResponse:
    row = latest_snapshot_for_owner(session, owner_user_id=owner_user_id)
    return DealerGradingDashboardGetResponse(snapshot=_snapshot_read(row) if row else None)


def get_dashboard_ops(session: Session, *, owner_user_id: int | None = None) -> DealerGradingDashboardGetResponse:
    row = latest_snapshot_ops(session, owner_user_id=owner_user_id)
    return DealerGradingDashboardGetResponse(snapshot=_snapshot_read(row) if row else None)


def _compute_payload(
    session: Session,
    *,
    owner_user_id: int,
    snapshot_date: date,
) -> dict[str, Any]:
    candidates = list(
        session.exec(select(GradingCandidate).where(GradingCandidate.owner_user_id == owner_user_id)).all(),
    )
    active_candidates = [row for row in candidates if row.status not in TERMINAL_CANDIDATE_STATUSES]
    ready_candidates = [row for row in candidates if row.status == "READY_FOR_SUBMISSION"]
    submitted_candidates = [row for row in candidates if row.status == "SUBMITTED"]
    graded_candidates = [row for row in candidates if row.status == "GRADED"]
    candidate_by_inventory = {int(row.inventory_item_id): row for row in sorted(candidates, key=lambda item: int(item.id or 0), reverse=True)}

    recommendation_rows = [
        row
        for row in session.exec(select(GradingRecommendation).where(GradingRecommendation.owner_user_id == owner_user_id)).all()
        if row.snapshot_date <= snapshot_date
    ]
    latest_recommendations = _latest_rows(
        recommendation_rows,
        key_fn=_recommendation_scope,
        sort_key_fn=lambda row: (row.snapshot_date, row.created_at, int(row.id or 0)),
    )
    active_recommendations = [row for row in latest_recommendations if row.recommendation_status == "ACTIVE"]

    risk_rows = [
        row
        for row in session.exec(select(GradingRiskSnapshot).where(GradingRiskSnapshot.owner_user_id == owner_user_id)).all()
        if row.snapshot_date <= snapshot_date
    ]
    latest_risks = _latest_rows(
        risk_rows,
        key_fn=_risk_scope,
        sort_key_fn=lambda row: (row.snapshot_date, row.created_at, int(row.id or 0)),
    )
    latest_risk_by_recommendation = {int(row.recommendation_id): row for row in latest_risks if row.recommendation_id is not None}
    latest_risk_by_candidate = {int(row.grading_candidate_id): row for row in latest_risks if row.grading_candidate_id is not None}

    batch_rows = list(
        session.exec(select(GradingSubmissionBatch).where(GradingSubmissionBatch.owner_user_id == owner_user_id)).all(),
    )
    active_batches = [row for row in batch_rows if row.status in ACTIVE_BATCH_STATUSES]
    shipped_batches = [
        row
        for row in batch_rows
        if row.status in {"SHIPPED", "RECEIVED_BY_GRADER", "GRADING", "RETURN_SHIPPED"}
    ]
    delayed_batches: list[tuple[GradingSubmissionBatch, int]] = []
    for row in active_batches:
        reference_date = row.submission_date or row.shipped_date or row.created_at.date()
        if row.estimated_turnaround_days is None:
            continue
        elapsed = max((snapshot_date - reference_date).days, 0)
        if elapsed > int(row.estimated_turnaround_days):
            delayed_batches.append((row, elapsed - int(row.estimated_turnaround_days)))

    reconciliation_rows = list(
        session.exec(select(GradingReconciliationRecord).where(GradingReconciliationRecord.owner_user_id == owner_user_id)).all(),
    )
    reconciled_rows = [row for row in reconciliation_rows if row.reconciliation_status == "RECONCILED"]

    grader_perf_rows = [
        row
        for row in session.exec(select(GraderPerformanceSnapshot).where(GraderPerformanceSnapshot.owner_user_id == owner_user_id)).all()
        if row.snapshot_date <= snapshot_date
    ]
    latest_grader_perf = _latest_rows(
        grader_perf_rows,
        key_fn=lambda row: str(row.grader),
        sort_key_fn=lambda row: (row.snapshot_date, row.created_at, int(row.id or 0)),
    )

    liquidity_rows = [
        row
        for row in session.exec(select(InventoryLiquiditySnapshot).where(InventoryLiquiditySnapshot.owner_user_id == owner_user_id)).all()
        if row.snapshot_date <= snapshot_date
    ]
    latest_liquidity = _latest_rows(
        liquidity_rows,
        key_fn=_liquidity_scope,
        sort_key_fn=lambda row: (row.snapshot_date, row.created_at, int(row.id or 0)),
    )

    estimated_roi_values = [row.expected_roi for row in active_recommendations if row.expected_roi is not None]
    adjusted_roi_values = [row.risk_adjusted_roi for row in latest_risks if row.risk_adjusted_roi is not None]
    pipeline_value_values = [row.estimated_graded_value for row in active_candidates if row.estimated_graded_value is not None]
    submission_cost_values = [row.estimated_total_cost for row in active_batches if row.estimated_total_cost is not None]
    expected_profit_values = [row.estimated_net_profit for row in active_recommendations if row.estimated_net_profit is not None]
    reconciliation_roi_deltas = [row.roi_delta for row in reconciled_rows if row.roi_delta is not None]

    metrics: list[dict[str, Any]] = [
        {"metric_key": "aggregation_label", "metric_value_text": AGGREGATION_VERSION},
        {"metric_key": "grade_recommendation_count", "metric_value_decimal": Decimal(sum(1 for row in active_recommendations if row.recommended_action == "GRADE"))},
        {"metric_key": "elite_opportunity_count", "metric_value_decimal": Decimal(sum(1 for row in active_recommendations if row.recommendation_strength == "ELITE"))},
        {"metric_key": "hold_raw_count", "metric_value_decimal": Decimal(sum(1 for row in active_recommendations if row.recommended_action == "HOLD_RAW"))},
        {"metric_key": "review_manually_count", "metric_value_decimal": Decimal(sum(1 for row in active_recommendations if row.recommended_action == "REVIEW_MANUALLY"))},
        {"metric_key": "not_recommended_count", "metric_value_decimal": Decimal(sum(1 for row in active_recommendations if row.recommended_action == "NOT_RECOMMENDED"))},
        {"metric_key": "low_risk_count", "metric_value_decimal": Decimal(sum(1 for row in latest_risks if row.overall_risk_level == "LOW"))},
        {"metric_key": "high_risk_count", "metric_value_decimal": Decimal(sum(1 for row in latest_risks if row.overall_risk_level in {"HIGH", "EXTREME"}))},
        {"metric_key": "high_confidence_count", "metric_value_decimal": Decimal(sum(1 for row in latest_risks if row.overall_confidence_level == "HIGH"))},
        {"metric_key": "low_confidence_count", "metric_value_decimal": Decimal(sum(1 for row in latest_risks if row.overall_confidence_level == "LOW"))},
        {"metric_key": "shipped_batch_count", "metric_value_decimal": Decimal(len(shipped_batches))},
        {"metric_key": "delayed_batch_count", "metric_value_decimal": Decimal(len(delayed_batches))},
        {
            "metric_key": "average_turnaround_days",
            "metric_value_decimal": _money(
                sum(Decimal(str(row.estimated_turnaround_days)) for row in batch_rows if row.estimated_turnaround_days is not None)
                / Decimal(str(sum(1 for row in batch_rows if row.estimated_turnaround_days is not None)))
                if any(row.estimated_turnaround_days is not None for row in batch_rows)
                else None,
            )
            if any(row.estimated_turnaround_days is not None for row in batch_rows)
            else None,
        },
        {"metric_key": "above_expectation_count", "metric_value_decimal": Decimal(sum(1 for row in reconciled_rows if row.grading_accuracy_status == "ABOVE_EXPECTATION"))},
        {"metric_key": "below_expectation_count", "metric_value_decimal": Decimal(sum(1 for row in reconciled_rows if row.grading_accuracy_status == "BELOW_EXPECTATION"))},
        {
            "metric_key": "average_roi_delta",
            "metric_value_decimal": _pct(sum(reconciliation_roi_deltas, Decimal("0")) / Decimal(str(len(reconciliation_roi_deltas))))
            if reconciliation_roi_deltas
            else None,
        },
        {
            "metric_key": "grader_performance_rollup",
            "metric_value_text": "Latest grader summaries",
            "metric_metadata_json": {
                "graders": [
                    {
                        "grader": row.grader,
                        "submission_count": row.submission_count,
                        "above_expectation_count": row.above_expectation_count,
                        "below_expectation_count": row.below_expectation_count,
                        "average_roi_delta": row.average_roi_delta,
                        "average_turnaround_days": row.average_turnaround_days,
                    }
                    for row in sorted(latest_grader_perf, key=lambda item: item.grader)
                ],
            },
        },
    ]

    weak_liquidity_rows = [
        row
        for row in latest_liquidity
        if row.inventory_item_id is not None and row.liquidity_status in {"LOW", "ILLIQUID"}
    ]

    alerts: list[dict[str, Any]] = []
    for row in sorted(active_recommendations, key=lambda item: (item.created_at, int(item.id or 0))):
        if (row.expected_roi is not None and row.expected_roi < ZERO) or (
            row.estimated_net_profit is not None and row.estimated_net_profit < ZERO
        ):
            alerts.append(
                {
                    "alert_type": "NEGATIVE_ROI",
                    "severity": "critical",
                    "source_candidate_id": row.grading_candidate_id,
                    "source_submission_batch_id": None,
                    "source_recommendation_id": row.id,
                    "message": f"Recommendation #{row.id} projects negative grading economics.",
                    "created_at": row.created_at,
                },
            )
        if int(row.evidence_count or 0) < 3:
            alerts.append(
                {
                    "alert_type": "MISSING_EVIDENCE",
                    "severity": "warning" if int(row.evidence_count or 0) <= 1 else "info",
                    "source_candidate_id": row.grading_candidate_id,
                    "source_submission_batch_id": None,
                    "source_recommendation_id": row.id,
                    "message": f"Recommendation #{row.id} has only {int(row.evidence_count or 0)} evidence rows.",
                    "created_at": row.created_at,
                },
            )

    for row in sorted(latest_risks, key=lambda item: (item.created_at, int(item.id or 0))):
        if row.overall_risk_level in {"HIGH", "EXTREME"}:
            alerts.append(
                {
                    "alert_type": "HIGH_RISK",
                    "severity": "critical" if row.overall_risk_level == "EXTREME" else "warning",
                    "source_candidate_id": row.grading_candidate_id,
                    "source_submission_batch_id": None,
                    "source_recommendation_id": row.recommendation_id,
                    "message": f"Risk snapshot #{row.id} is {row.overall_risk_level.lower()} risk.",
                    "created_at": row.created_at,
                },
            )
        if row.overall_confidence_level == "LOW":
            alerts.append(
                {
                    "alert_type": "LOW_CONFIDENCE",
                    "severity": "warning",
                    "source_candidate_id": row.grading_candidate_id,
                    "source_submission_batch_id": None,
                    "source_recommendation_id": row.recommendation_id,
                    "message": f"Risk snapshot #{row.id} reduced recommendation confidence to LOW.",
                    "created_at": row.created_at,
                },
            )
        if int(row.evidence_count or 0) < 3 and row.recommendation_id is not None:
            alerts.append(
                {
                    "alert_type": "MISSING_EVIDENCE",
                    "severity": "warning" if int(row.evidence_count or 0) <= 1 else "info",
                    "source_candidate_id": row.grading_candidate_id,
                    "source_submission_batch_id": None,
                    "source_recommendation_id": row.recommendation_id,
                    "message": f"Risk snapshot #{row.id} has only {int(row.evidence_count or 0)} supporting evidence rows.",
                    "created_at": row.created_at,
                },
            )

    for batch, overdue_days in sorted(delayed_batches, key=lambda pair: (pair[0].created_at, int(pair[0].id or 0))):
        alerts.append(
            {
                "alert_type": "SUBMISSION_DELAY",
                "severity": "critical" if overdue_days >= 14 else "warning",
                "source_candidate_id": None,
                "source_submission_batch_id": batch.id,
                "source_recommendation_id": None,
                "message": f"Submission batch #{batch.id} is overdue by {overdue_days} day(s).",
                "created_at": batch.created_at,
            },
        )

    for row in sorted(reconciled_rows, key=lambda item: (item.created_at, int(item.id or 0))):
        if row.grading_accuracy_status == "BELOW_EXPECTATION":
            alerts.append(
                {
                    "alert_type": "RECONCILIATION_FAILURE",
                    "severity": "critical",
                    "source_candidate_id": row.grading_candidate_id,
                    "source_submission_batch_id": None,
                    "source_recommendation_id": None,
                    "message": f"Reconciliation #{row.id} landed below expectation.",
                    "created_at": row.created_at,
                },
            )

    for row in sorted(weak_liquidity_rows, key=lambda item: (item.created_at, int(item.id or 0))):
        candidate = candidate_by_inventory.get(int(row.inventory_item_id or 0))
        alerts.append(
            {
                "alert_type": "WEAK_LIQUIDITY",
                "severity": "warning",
                "source_candidate_id": int(candidate.id) if candidate is not None and candidate.id is not None else None,
                "source_submission_batch_id": None,
                "source_recommendation_id": None,
                "message": f"Liquidity snapshot #{row.id} marked inventory #{row.inventory_item_id} as {row.liquidity_status}.",
                "created_at": row.created_at,
            },
        )

    feed_events: list[dict[str, Any]] = []
    for row in sorted(candidates, key=lambda item: (item.created_at, int(item.id or 0))):
        feed_events.append(
            {
                "deterministic_key": f"candidate_created:{int(row.id or 0)}",
                "event_type": "CANDIDATE_CREATED",
                "source_id": row.id,
                "summary": f"Candidate #{row.id} created for inventory #{row.inventory_item_id}.",
                "metadata_json": {"status": row.status, "target_grader": row.target_grader},
                "created_at": row.created_at,
            },
        )

    for row in sorted(recommendation_rows, key=lambda item: (item.created_at, int(item.id or 0))):
        feed_events.append(
            {
                "deterministic_key": f"recommendation_generated:{int(row.id or 0)}",
                "event_type": "RECOMMENDATION_GENERATED",
                "source_id": row.id,
                "summary": f"Recommendation #{row.id} generated as {row.recommended_action}.",
                "metadata_json": {"strength": row.recommendation_strength, "risk_level": row.risk_level},
                "created_at": row.created_at,
            },
        )
        if row.recommendation_strength == "ELITE":
            feed_events.append(
                {
                    "deterministic_key": f"elite_opportunity:{int(row.id or 0)}",
                    "event_type": "ELITE_OPPORTUNITY_DETECTED",
                    "source_id": row.id,
                    "summary": f"Recommendation #{row.id} surfaced an elite grading opportunity.",
                    "metadata_json": {"recommended_action": row.recommended_action},
                    "created_at": row.created_at,
                },
            )

    for row in sorted(batch_rows, key=lambda item: (item.created_at, int(item.id or 0))):
        feed_events.append(
            {
                "deterministic_key": f"submission_batch_created:{int(row.id or 0)}",
                "event_type": "SUBMISSION_BATCH_CREATED",
                "source_id": row.id,
                "summary": f"Submission batch #{row.id} created for {row.target_grader}.",
                "metadata_json": {"status": row.status, "item_count": row.item_count},
                "created_at": row.created_at,
            },
        )

    shipment_events = session.exec(
        select(GradingSubmissionLifecycleEvent)
        .join(
            GradingSubmissionBatch,
            GradingSubmissionLifecycleEvent.grading_submission_batch_id == GradingSubmissionBatch.id,
        )
        .where(
            GradingSubmissionBatch.owner_user_id == owner_user_id,
            GradingSubmissionLifecycleEvent.event_type == "SHIPPED",
        )
        .order_by(col(GradingSubmissionLifecycleEvent.created_at).asc(), col(GradingSubmissionLifecycleEvent.id).asc()),
    ).all()
    for row in shipment_events:
        feed_events.append(
            {
                "deterministic_key": f"submission_shipped:{int(row.id or 0)}",
                "event_type": "SUBMISSION_SHIPPED",
                "source_id": row.grading_submission_batch_id,
                "summary": f"Submission batch #{row.grading_submission_batch_id} shipped to grader.",
                "metadata_json": row.metadata_json,
                "created_at": row.created_at,
            },
        )

    returned_events = session.exec(
        select(GradingSubmissionLifecycleEvent)
        .join(
            GradingSubmissionBatch,
            GradingSubmissionLifecycleEvent.grading_submission_batch_id == GradingSubmissionBatch.id,
        )
        .where(
            GradingSubmissionBatch.owner_user_id == owner_user_id,
            GradingSubmissionLifecycleEvent.event_type == "COMPLETED",
        )
        .order_by(col(GradingSubmissionLifecycleEvent.created_at).asc(), col(GradingSubmissionLifecycleEvent.id).asc()),
    ).all()
    for row in returned_events:
        feed_events.append(
            {
                "deterministic_key": f"grades_returned:{int(row.id or 0)}",
                "event_type": "GRADES_RETURNED",
                "source_id": row.grading_submission_batch_id,
                "summary": f"Submission batch #{row.grading_submission_batch_id} returned from grader.",
                "metadata_json": row.metadata_json,
                "created_at": row.created_at,
            },
        )

    for row in sorted(reconciled_rows, key=lambda item: (item.created_at, int(item.id or 0))):
        feed_events.append(
            {
                "deterministic_key": f"reconciliation_completed:{int(row.id or 0)}",
                "event_type": "RECONCILIATION_COMPLETED",
                "source_id": row.id,
                "summary": f"Reconciliation #{row.id} completed for candidate #{row.grading_candidate_id}.",
                "metadata_json": {"accuracy_status": row.grading_accuracy_status, "target_grader": row.target_grader},
                "created_at": row.created_at,
            },
        )

    for row in sorted(latest_risks, key=lambda item: (item.created_at, int(item.id or 0))):
        if row.overall_risk_level in {"HIGH", "EXTREME"}:
            feed_events.append(
                {
                    "deterministic_key": f"high_risk_detected:{int(row.id or 0)}",
                    "event_type": "HIGH_RISK_DETECTED",
                    "source_id": row.id,
                    "summary": f"Risk snapshot #{row.id} detected {row.overall_risk_level.lower()} grading risk.",
                    "metadata_json": {
                        "recommendation_id": row.recommendation_id,
                        "confidence_level": row.overall_confidence_level,
                    },
                    "created_at": row.created_at,
                },
            )

    payload: dict[str, Any] = {
        "aggregation_version": AGGREGATION_VERSION,
        "owner_user_id": owner_user_id,
        "snapshot_date": snapshot_date,
        "active_candidate_count": len(active_candidates),
        "ready_for_submission_count": len(ready_candidates),
        "submitted_candidate_count": len(submitted_candidates),
        "graded_candidate_count": len(graded_candidates),
        "elite_recommendation_count": sum(1 for row in active_recommendations if row.recommendation_strength == "ELITE"),
        "high_risk_candidate_count": sum(1 for row in latest_risks if row.overall_risk_level in {"HIGH", "EXTREME"}),
        "low_confidence_candidate_count": sum(1 for row in latest_risks if row.overall_confidence_level == "LOW"),
        "average_estimated_roi": _pct(sum(estimated_roi_values, Decimal("0")) / Decimal(str(len(estimated_roi_values))))
        if estimated_roi_values
        else None,
        "average_risk_adjusted_roi": _pct(sum(adjusted_roi_values, Decimal("0")) / Decimal(str(len(adjusted_roi_values))))
        if adjusted_roi_values
        else None,
        "active_submission_batch_count": len(active_batches),
        "grading_pipeline_value": _money(sum((_money(value) for value in pipeline_value_values), ZERO)) if pipeline_value_values else None,
        "estimated_total_submission_cost": _money(sum((_money(value) for value in submission_cost_values), ZERO))
        if submission_cost_values
        else None,
        "expected_total_profit": _money(sum((_money(value) for value in expected_profit_values), ZERO)) if expected_profit_values else None,
        "candidate_rows": [
            {
                "id": row.id,
                "inventory_item_id": row.inventory_item_id,
                "status": row.status,
                "estimated_graded_value": row.estimated_graded_value,
                "estimated_roi": row.estimated_roi,
            }
            for row in sorted(candidates, key=lambda item: int(item.id or 0))
        ],
        "recommendation_rows": [
            {
                "id": row.id,
                "grading_candidate_id": row.grading_candidate_id,
                "recommended_action": row.recommended_action,
                "recommendation_strength": row.recommendation_strength,
                "expected_roi": row.expected_roi,
                "estimated_net_profit": row.estimated_net_profit,
                "evidence_count": row.evidence_count,
            }
            for row in sorted(active_recommendations, key=lambda item: int(item.id or 0))
        ],
        "risk_rows": [
            {
                "id": row.id,
                "grading_candidate_id": row.grading_candidate_id,
                "recommendation_id": row.recommendation_id,
                "overall_risk_level": row.overall_risk_level,
                "overall_confidence_level": row.overall_confidence_level,
                "risk_adjusted_roi": row.risk_adjusted_roi,
                "evidence_count": row.evidence_count,
            }
            for row in sorted(latest_risks, key=lambda item: int(item.id or 0))
        ],
        "batch_rows": [
            {
                "id": row.id,
                "status": row.status,
                "estimated_turnaround_days": row.estimated_turnaround_days,
                "estimated_total_cost": row.estimated_total_cost,
                "item_count": row.item_count,
            }
            for row in sorted(batch_rows, key=lambda item: int(item.id or 0))
        ],
        "reconciliation_rows": [
            {
                "id": row.id,
                "grading_candidate_id": row.grading_candidate_id,
                "grading_accuracy_status": row.grading_accuracy_status,
                "roi_delta": row.roi_delta,
            }
            for row in sorted(reconciled_rows, key=lambda item: int(item.id or 0))
        ],
        "metrics": sorted(metrics, key=lambda item: item["metric_key"]),
        "alerts": [
            {
                "alert_type": row["alert_type"],
                "severity": row["severity"],
                "source_candidate_id": row["source_candidate_id"],
                "source_submission_batch_id": row["source_submission_batch_id"],
                "source_recommendation_id": row["source_recommendation_id"],
                "message": row["message"],
                "created_at": row["created_at"],
            }
            for row in sorted(
                alerts,
                key=lambda item: (
                    item["created_at"],
                    item["alert_type"],
                    int(item["source_candidate_id"] or 0),
                    int(item["source_submission_batch_id"] or 0),
                    int(item["source_recommendation_id"] or 0),
                    item["message"],
                ),
            )
        ],
        "feed_events": [
            {
                "deterministic_key": row["deterministic_key"],
                "event_type": row["event_type"],
                "source_id": row["source_id"],
                "summary": row["summary"],
                "metadata_json": row["metadata_json"],
                "created_at": row["created_at"],
            }
            for row in sorted(feed_events, key=lambda item: (item["created_at"], item["deterministic_key"]))
        ],
    }

    return payload


def generate_dealer_grading_dashboard(
    session: Session,
    *,
    owner_user_id: int,
    payload: DealerGradingDashboardGeneratePayload,
) -> DealerGradingDashboardGenerateResponse:
    replay_key_trim = payload.replay_key.strip() if payload.replay_key else None
    snapshot_date = payload.snapshot_date or _utc_today()

    if replay_key_trim:
        existing = session.exec(
            select(DealerGradingDashboardSnapshot).where(
                DealerGradingDashboardSnapshot.owner_user_id == owner_user_id,
                DealerGradingDashboardSnapshot.replay_key == replay_key_trim,
            ),
        ).first()
        if existing:
            return DealerGradingDashboardGenerateResponse(snapshot=_snapshot_read(existing))

    payload_dict = _compute_payload(session, owner_user_id=owner_user_id, snapshot_date=snapshot_date)
    checksum = _hash_payload(payload_dict)

    checksum_collision = session.exec(
        select(DealerGradingDashboardSnapshot).where(
            DealerGradingDashboardSnapshot.owner_user_id == owner_user_id,
            DealerGradingDashboardSnapshot.snapshot_date == snapshot_date,
            DealerGradingDashboardSnapshot.checksum == checksum,
        ),
    ).first()
    if checksum_collision:
        return DealerGradingDashboardGenerateResponse(snapshot=_snapshot_read(checksum_collision))

    snap = DealerGradingDashboardSnapshot(
        owner_user_id=owner_user_id,
        replay_key=replay_key_trim,
        active_candidate_count=int(payload_dict["active_candidate_count"]),
        ready_for_submission_count=int(payload_dict["ready_for_submission_count"]),
        submitted_candidate_count=int(payload_dict["submitted_candidate_count"]),
        graded_candidate_count=int(payload_dict["graded_candidate_count"]),
        elite_recommendation_count=int(payload_dict["elite_recommendation_count"]),
        high_risk_candidate_count=int(payload_dict["high_risk_candidate_count"]),
        low_confidence_candidate_count=int(payload_dict["low_confidence_candidate_count"]),
        average_estimated_roi=payload_dict["average_estimated_roi"],
        average_risk_adjusted_roi=payload_dict["average_risk_adjusted_roi"],
        active_submission_batch_count=int(payload_dict["active_submission_batch_count"]),
        grading_pipeline_value=payload_dict["grading_pipeline_value"],
        estimated_total_submission_cost=payload_dict["estimated_total_submission_cost"],
        expected_total_profit=payload_dict["expected_total_profit"],
        checksum=checksum,
        snapshot_date=snapshot_date,
    )
    session.add(snap)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        if replay_key_trim:
            existing = session.exec(
                select(DealerGradingDashboardSnapshot).where(
                    DealerGradingDashboardSnapshot.owner_user_id == owner_user_id,
                    DealerGradingDashboardSnapshot.replay_key == replay_key_trim,
                ),
            ).first()
            if existing:
                return DealerGradingDashboardGenerateResponse(snapshot=_snapshot_read(existing))
        raise

    for metric in payload_dict["metrics"]:
        session.add(
            DealerGradingDashboardMetric(
                dashboard_snapshot_id=int(snap.id or 0),
                metric_key=str(metric["metric_key"]),
                metric_value_decimal=metric.get("metric_value_decimal"),
                metric_value_text=metric.get("metric_value_text"),
                metric_metadata_json=_json_safe(metric.get("metric_metadata_json")),
            ),
        )

    for alert in payload_dict["alerts"]:
        alert_replay_key = _hash_payload(
            {
                "snapshot_id": snap.id,
                "alert_type": alert["alert_type"],
                "severity": alert["severity"],
                "source_candidate_id": alert["source_candidate_id"],
                "source_submission_batch_id": alert["source_submission_batch_id"],
                "source_recommendation_id": alert["source_recommendation_id"],
                "message": alert["message"],
            },
        )
        session.add(
            DealerGradingDashboardAlert(
                owner_user_id=owner_user_id,
                dashboard_snapshot_id=int(snap.id or 0),
                alert_type=str(alert["alert_type"]),
                severity=str(alert["severity"]),
                alert_replay_key=alert_replay_key,
                source_candidate_id=alert["source_candidate_id"],
                source_submission_batch_id=alert["source_submission_batch_id"],
                source_recommendation_id=alert["source_recommendation_id"],
                message=str(alert["message"]),
                created_at=alert["created_at"],
            ),
        )

    existing_feed_keys = set(
        session.exec(
            select(DealerGradingDashboardFeedEvent.deterministic_key).where(
                DealerGradingDashboardFeedEvent.owner_user_id == owner_user_id,
            ),
        ).all(),
    )
    for event in payload_dict["feed_events"]:
        key = str(event["deterministic_key"])
        if key in existing_feed_keys:
            continue
        existing_feed_keys.add(key)
        session.add(
            DealerGradingDashboardFeedEvent(
                owner_user_id=owner_user_id,
                deterministic_key=key,
                dashboard_snapshot_id=int(snap.id or 0),
                event_type=str(event["event_type"]),
                source_id=event["source_id"],
                summary=str(event["summary"]),
                metadata_json=_json_safe(event.get("metadata_json")),
                created_at=event["created_at"],
            ),
        )

    session.commit()
    session.refresh(snap)
    return DealerGradingDashboardGenerateResponse(snapshot=_snapshot_read(snap))


def list_metrics_owner(
    session: Session,
    *,
    owner_user_id: int,
    dashboard_snapshot_id: int | None,
    limit: int,
    offset: int,
) -> DealerGradingDashboardMetricListResponse:
    limit, offset = clamp_dealer_grading_dashboard_pagination(limit=limit, offset=offset)
    snapshot = (
        session.get(DealerGradingDashboardSnapshot, dashboard_snapshot_id)
        if dashboard_snapshot_id is not None
        else latest_snapshot_for_owner(session, owner_user_id=owner_user_id)
    )
    if snapshot is None or snapshot.owner_user_id != owner_user_id:
        return DealerGradingDashboardMetricListResponse(items=[], total_items=0, limit=limit, offset=offset)
    items = session.exec(
        select(DealerGradingDashboardMetric)
        .where(DealerGradingDashboardMetric.dashboard_snapshot_id == int(snapshot.id or 0))
        .order_by(col(DealerGradingDashboardMetric.metric_key).asc(), col(DealerGradingDashboardMetric.id).asc())
        .offset(offset)
        .limit(limit),
    ).all()
    total = len(
        session.exec(
            select(DealerGradingDashboardMetric)
            .where(DealerGradingDashboardMetric.dashboard_snapshot_id == int(snapshot.id or 0))
            .order_by(col(DealerGradingDashboardMetric.id).asc()),
        ).all(),
    )
    return DealerGradingDashboardMetricListResponse(
        items=[DealerGradingDashboardMetricRead.model_validate(row, from_attributes=True) for row in items],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_metrics_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    dashboard_snapshot_id: int | None,
    limit: int,
    offset: int,
) -> DealerGradingDashboardMetricListResponse:
    limit, offset = clamp_dealer_grading_dashboard_pagination(limit=limit, offset=offset)
    snapshot = (
        session.get(DealerGradingDashboardSnapshot, dashboard_snapshot_id)
        if dashboard_snapshot_id is not None
        else latest_snapshot_ops(session, owner_user_id=owner_user_id)
    )
    if snapshot is None or (owner_user_id is not None and snapshot.owner_user_id != owner_user_id):
        return DealerGradingDashboardMetricListResponse(items=[], total_items=0, limit=limit, offset=offset)
    return list_metrics_owner(
        session,
        owner_user_id=int(snapshot.owner_user_id),
        dashboard_snapshot_id=int(snapshot.id or 0),
        limit=limit,
        offset=offset,
    )


def list_alerts_owner(
    session: Session,
    *,
    owner_user_id: int,
    severity: str | None,
    alert_type: str | None,
    created_from: datetime | None,
    created_to: datetime | None,
    limit: int,
    offset: int,
) -> DealerGradingDashboardAlertListResponse:
    limit, offset = clamp_dealer_grading_dashboard_pagination(limit=limit, offset=offset)
    stmt = select(DealerGradingDashboardAlert).where(DealerGradingDashboardAlert.owner_user_id == owner_user_id)
    if severity:
        stmt = stmt.where(DealerGradingDashboardAlert.severity == severity)
    if alert_type:
        stmt = stmt.where(DealerGradingDashboardAlert.alert_type == alert_type)
    if created_from is not None:
        stmt = stmt.where(DealerGradingDashboardAlert.created_at >= created_from)
    if created_to is not None:
        stmt = stmt.where(DealerGradingDashboardAlert.created_at <= created_to)
    ordered = stmt.order_by(col(DealerGradingDashboardAlert.created_at).desc(), col(DealerGradingDashboardAlert.id).desc())
    total = len(session.exec(ordered).all())
    items = session.exec(ordered.offset(offset).limit(limit)).all()
    return DealerGradingDashboardAlertListResponse(
        items=[DealerGradingDashboardAlertRead.model_validate(row, from_attributes=True) for row in items],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_alerts_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    severity: str | None,
    alert_type: str | None,
    created_from: datetime | None,
    created_to: datetime | None,
    limit: int,
    offset: int,
) -> DealerGradingDashboardAlertListResponse:
    limit, offset = clamp_dealer_grading_dashboard_pagination(limit=limit, offset=offset)
    stmt = select(DealerGradingDashboardAlert)
    if owner_user_id is not None:
        stmt = stmt.where(DealerGradingDashboardAlert.owner_user_id == owner_user_id)
    if severity:
        stmt = stmt.where(DealerGradingDashboardAlert.severity == severity)
    if alert_type:
        stmt = stmt.where(DealerGradingDashboardAlert.alert_type == alert_type)
    if created_from is not None:
        stmt = stmt.where(DealerGradingDashboardAlert.created_at >= created_from)
    if created_to is not None:
        stmt = stmt.where(DealerGradingDashboardAlert.created_at <= created_to)
    ordered = stmt.order_by(col(DealerGradingDashboardAlert.created_at).desc(), col(DealerGradingDashboardAlert.id).desc())
    total = len(session.exec(ordered).all())
    items = session.exec(ordered.offset(offset).limit(limit)).all()
    return DealerGradingDashboardAlertListResponse(
        items=[DealerGradingDashboardAlertRead.model_validate(row, from_attributes=True) for row in items],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_feed_owner(
    session: Session,
    *,
    owner_user_id: int,
    event_type: str | None,
    created_from: datetime | None,
    created_to: datetime | None,
    limit: int,
    offset: int,
) -> DealerGradingDashboardFeedListResponse:
    limit, offset = clamp_dealer_grading_dashboard_pagination(limit=limit, offset=offset)
    stmt = select(DealerGradingDashboardFeedEvent).where(DealerGradingDashboardFeedEvent.owner_user_id == owner_user_id)
    if event_type:
        stmt = stmt.where(DealerGradingDashboardFeedEvent.event_type == event_type)
    if created_from is not None:
        stmt = stmt.where(DealerGradingDashboardFeedEvent.created_at >= created_from)
    if created_to is not None:
        stmt = stmt.where(DealerGradingDashboardFeedEvent.created_at <= created_to)
    ordered = stmt.order_by(col(DealerGradingDashboardFeedEvent.created_at).desc(), col(DealerGradingDashboardFeedEvent.id).desc())
    total = len(session.exec(ordered).all())
    items = session.exec(ordered.offset(offset).limit(limit)).all()
    return DealerGradingDashboardFeedListResponse(
        items=[DealerGradingDashboardFeedEventRead.model_validate(row, from_attributes=True) for row in items],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_feed_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    event_type: str | None,
    created_from: datetime | None,
    created_to: datetime | None,
    limit: int,
    offset: int,
) -> DealerGradingDashboardFeedListResponse:
    limit, offset = clamp_dealer_grading_dashboard_pagination(limit=limit, offset=offset)
    stmt = select(DealerGradingDashboardFeedEvent)
    if owner_user_id is not None:
        stmt = stmt.where(DealerGradingDashboardFeedEvent.owner_user_id == owner_user_id)
    if event_type:
        stmt = stmt.where(DealerGradingDashboardFeedEvent.event_type == event_type)
    if created_from is not None:
        stmt = stmt.where(DealerGradingDashboardFeedEvent.created_at >= created_from)
    if created_to is not None:
        stmt = stmt.where(DealerGradingDashboardFeedEvent.created_at <= created_to)
    ordered = stmt.order_by(col(DealerGradingDashboardFeedEvent.created_at).desc(), col(DealerGradingDashboardFeedEvent.id).desc())
    total = len(session.exec(ordered).all())
    items = session.exec(ordered.offset(offset).limit(limit)).all()
    return DealerGradingDashboardFeedListResponse(
        items=[DealerGradingDashboardFeedEventRead.model_validate(row, from_attributes=True) for row in items],
        total_items=total,
        limit=limit,
        offset=offset,
    )
