from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import (
    AgentDefinition,
    AgentExecution,
    AgentMetricSnapshot,
    AgentPerformanceMetric,
    IntelligenceRecommendation,
    IntelligenceRecommendationReview,
    RecommendationOutcomeMetric,
    WorkflowDefinition,
    WorkflowExecution,
    WorkflowPerformanceMetric,
)
from app.schemas.agent_analytics import (
    AgentAnalyticsSummaryRead,
    AgentMetricSnapshotDetail,
    AgentMetricSnapshotListResponse,
    AgentMetricSnapshotRead,
    AgentPerformanceMetricListResponse,
    AgentPerformanceMetricRead,
    RecommendationOutcomeMetricListResponse,
    RecommendationOutcomeMetricRead,
    WorkflowPerformanceMetricListResponse,
    WorkflowPerformanceMetricRead,
)
from app.services.agent_registry import clamp_agent_pagination
from app.services.recommendation_outcomes import calculate_outcomes_by_type


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _round_rate(value: float) -> float:
    return round(float(value), 4)


def _snapshot_scope(*, owner_user_id: int) -> str:
    return f"owner:{owner_user_id}"


def _snapshot_read(row: AgentMetricSnapshot) -> AgentMetricSnapshotRead:
    return AgentMetricSnapshotRead(
        id=int(row.id or 0),
        snapshot_uuid=row.snapshot_uuid,
        snapshot_date=row.snapshot_date,
        generated_at=row.generated_at,
        scope=row.scope,
        summary_json=dict(row.summary_json or {}),
        created_at=row.created_at,
    )


def _agent_metric_read(row: AgentPerformanceMetric) -> AgentPerformanceMetricRead:
    return AgentPerformanceMetricRead(
        id=int(row.id or 0),
        snapshot_id=row.snapshot_id,
        agent_id=row.agent_id,
        agent_code=row.agent_code,
        executions_total=row.executions_total,
        executions_completed=row.executions_completed,
        executions_failed=row.executions_failed,
        success_rate=row.success_rate,
        failure_rate=row.failure_rate,
        avg_duration_ms=row.avg_duration_ms,
        last_run_at=row.last_run_at,
        last_success_at=row.last_success_at,
        last_failure_at=row.last_failure_at,
        recommendations_generated=row.recommendations_generated,
        recommendations_reviewed=row.recommendations_reviewed,
        recommendations_accepted=row.recommendations_accepted,
        recommendations_dismissed=row.recommendations_dismissed,
        created_at=row.created_at,
    )


def _workflow_metric_read(row: WorkflowPerformanceMetric) -> WorkflowPerformanceMetricRead:
    return WorkflowPerformanceMetricRead(
        id=int(row.id or 0),
        snapshot_id=row.snapshot_id,
        workflow_id=row.workflow_id,
        workflow_code=row.workflow_code,
        executions_total=row.executions_total,
        executions_completed=row.executions_completed,
        executions_failed=row.executions_failed,
        success_rate=row.success_rate,
        failure_rate=row.failure_rate,
        avg_duration_ms=row.avg_duration_ms,
        last_run_at=row.last_run_at,
        last_success_at=row.last_success_at,
        last_failure_at=row.last_failure_at,
        created_at=row.created_at,
    )


def _recommendation_metric_read(row: RecommendationOutcomeMetric) -> RecommendationOutcomeMetricRead:
    return RecommendationOutcomeMetricRead(
        id=int(row.id or 0),
        snapshot_id=row.snapshot_id,
        recommendation_type=row.recommendation_type,
        recommendations_total=row.recommendations_total,
        reviewed_total=row.reviewed_total,
        accepted_total=row.accepted_total,
        dismissed_total=row.dismissed_total,
        acceptance_rate=row.acceptance_rate,
        dismissal_rate=row.dismissal_rate,
        avg_confidence_score=row.avg_confidence_score,
        avg_opportunity_score=row.avg_opportunity_score,
        avg_priority_score=row.avg_priority_score,
        created_at=row.created_at,
    )


def _latest_review_status_map(session: Session, *, recommendation_ids: list[int]) -> dict[int, str]:
    if not recommendation_ids:
        return {}
    rows = session.exec(
        select(IntelligenceRecommendationReview)
        .where(IntelligenceRecommendationReview.recommendation_id.in_(recommendation_ids))
        .order_by(IntelligenceRecommendationReview.reviewed_at.asc(), IntelligenceRecommendationReview.id.asc())
    ).all()
    latest: dict[int, str] = {}
    for row in rows:
        latest[row.recommendation_id] = row.review_status
    return latest


def _average_duration_ms(rows: list[int | None]) -> int | None:
    durations = [value for value in rows if value is not None]
    if not durations:
        return None
    return int(sum(durations) / len(durations))


def _latest_timestamp(rows: list[datetime | None]) -> datetime | None:
    timestamps = [value for value in rows if value is not None]
    return max(timestamps) if timestamps else None


def _build_summary(
    *,
    agent_metrics: list[AgentPerformanceMetric],
    workflow_metrics: list[WorkflowPerformanceMetric],
    recommendation_metrics: list[RecommendationOutcomeMetric],
) -> dict[str, object]:
    total_agent_executions = sum(row.executions_total for row in agent_metrics)
    total_agent_completed = sum(row.executions_completed for row in agent_metrics)
    total_agent_failed = sum(row.executions_failed for row in agent_metrics)
    total_recommendations = sum(row.recommendations_total for row in recommendation_metrics)
    total_accepted = sum(row.accepted_total for row in recommendation_metrics)
    total_dismissed = sum(row.dismissed_total for row in recommendation_metrics)
    recommendations_generated_by_type = {
        row.recommendation_type: row.recommendations_total
        for row in sorted(recommendation_metrics, key=lambda item: item.recommendation_type)
    }
    return {
        "agent_executions_total": total_agent_executions,
        "agent_success_rate": _round_rate(total_agent_completed / total_agent_executions) if total_agent_executions else 0.0,
        "agent_failure_rate": _round_rate(total_agent_failed / total_agent_executions) if total_agent_executions else 0.0,
        "avg_execution_duration_ms": _average_duration_ms([row.avg_duration_ms for row in agent_metrics]),
        "workflow_executions_total": sum(row.executions_total for row in workflow_metrics),
        "recommendations_total": total_recommendations,
        "recommendation_acceptance_rate": _round_rate(total_accepted / total_recommendations) if total_recommendations else 0.0,
        "recommendation_dismissal_rate": _round_rate(total_dismissed / total_recommendations) if total_recommendations else 0.0,
        "recommendations_generated_by_type": recommendations_generated_by_type,
    }


def calculate_agent_metrics(session: Session, *, owner_user_id: int) -> list[AgentPerformanceMetric]:
    agents = session.exec(select(AgentDefinition).order_by(AgentDefinition.code.asc(), AgentDefinition.id.asc())).all()
    executions = session.exec(
        select(AgentExecution)
        .where(AgentExecution.triggered_by == str(owner_user_id))
        .order_by(AgentExecution.started_at.asc(), AgentExecution.id.asc())
    ).all()
    recommendations = session.exec(
        select(IntelligenceRecommendation)
        .join(AgentExecution, AgentExecution.id == IntelligenceRecommendation.agent_execution_id)
        .where(AgentExecution.triggered_by == str(owner_user_id))
        .order_by(IntelligenceRecommendation.created_at.asc(), IntelligenceRecommendation.id.asc())
    ).all()
    latest_review_status = _latest_review_status_map(
        session,
        recommendation_ids=[int(row.id or 0) for row in recommendations],
    )

    execution_groups: dict[int, list[AgentExecution]] = defaultdict(list)
    for row in executions:
        execution_groups[row.agent_id].append(row)

    recommendation_groups: dict[int, list[IntelligenceRecommendation]] = defaultdict(list)
    for row in recommendations:
        execution = session.get(AgentExecution, row.agent_execution_id)
        if execution is not None:
            recommendation_groups[execution.agent_id].append(row)

    metrics: list[AgentPerformanceMetric] = []
    for agent in agents:
        grouped_executions = execution_groups.get(int(agent.id or 0), [])
        grouped_recommendations = recommendation_groups.get(int(agent.id or 0), [])
        executions_total = len(grouped_executions)
        executions_completed = sum(1 for row in grouped_executions if row.status == "COMPLETED")
        executions_failed = sum(1 for row in grouped_executions if row.status == "FAILED")
        recommendations_reviewed = sum(1 for row in grouped_recommendations if int(row.id or 0) in latest_review_status)
        recommendations_accepted = sum(
            1 for row in grouped_recommendations if latest_review_status.get(int(row.id or 0)) == "ACCEPTED"
        )
        recommendations_dismissed = sum(
            1 for row in grouped_recommendations if latest_review_status.get(int(row.id or 0)) == "DISMISSED"
        )
        metrics.append(
            AgentPerformanceMetric(
                snapshot_id=0,
                agent_id=int(agent.id or 0),
                agent_code=agent.code,
                executions_total=executions_total,
                executions_completed=executions_completed,
                executions_failed=executions_failed,
                success_rate=_round_rate(executions_completed / executions_total) if executions_total else 0.0,
                failure_rate=_round_rate(executions_failed / executions_total) if executions_total else 0.0,
                avg_duration_ms=_average_duration_ms([row.execution_duration_ms for row in grouped_executions]),
                last_run_at=_latest_timestamp([row.started_at for row in grouped_executions]),
                last_success_at=_latest_timestamp([row.completed_at for row in grouped_executions if row.status == "COMPLETED"]),
                last_failure_at=_latest_timestamp([row.completed_at for row in grouped_executions if row.status == "FAILED"]),
                recommendations_generated=len(grouped_recommendations),
                recommendations_reviewed=recommendations_reviewed,
                recommendations_accepted=recommendations_accepted,
                recommendations_dismissed=recommendations_dismissed,
            )
        )
    return metrics


def calculate_workflow_metrics(session: Session, *, owner_user_id: int) -> list[WorkflowPerformanceMetric]:
    workflows = session.exec(
        select(WorkflowDefinition).order_by(WorkflowDefinition.workflow_code.asc(), WorkflowDefinition.id.asc())
    ).all()
    executions = session.exec(
        select(WorkflowExecution)
        .where(WorkflowExecution.triggered_by == str(owner_user_id))
        .order_by(WorkflowExecution.started_at.asc(), WorkflowExecution.id.asc())
    ).all()
    grouped: dict[int, list[WorkflowExecution]] = defaultdict(list)
    for row in executions:
        grouped[row.workflow_id].append(row)

    metrics: list[WorkflowPerformanceMetric] = []
    for workflow in workflows:
        grouped_rows = grouped.get(int(workflow.id or 0), [])
        executions_total = len(grouped_rows)
        executions_completed = sum(1 for row in grouped_rows if row.status == "COMPLETED")
        executions_failed = sum(1 for row in grouped_rows if row.status == "FAILED")
        metrics.append(
            WorkflowPerformanceMetric(
                snapshot_id=0,
                workflow_id=int(workflow.id or 0),
                workflow_code=workflow.workflow_code,
                executions_total=executions_total,
                executions_completed=executions_completed,
                executions_failed=executions_failed,
                success_rate=_round_rate(executions_completed / executions_total) if executions_total else 0.0,
                failure_rate=_round_rate(executions_failed / executions_total) if executions_total else 0.0,
                avg_duration_ms=_average_duration_ms([row.duration_ms for row in grouped_rows]),
                last_run_at=_latest_timestamp([row.started_at for row in grouped_rows]),
                last_success_at=_latest_timestamp([row.completed_at for row in grouped_rows if row.status == "COMPLETED"]),
                last_failure_at=_latest_timestamp([row.completed_at for row in grouped_rows if row.status == "FAILED"]),
            )
        )
    return metrics


def calculate_recommendation_outcome_metrics(session: Session, *, owner_user_id: int) -> list[RecommendationOutcomeMetric]:
    aggregates = calculate_outcomes_by_type(session, owner_user_id=owner_user_id)
    metrics: list[RecommendationOutcomeMetric] = []
    for row in aggregates:
        metrics.append(
            RecommendationOutcomeMetric(
                snapshot_id=0,
                recommendation_type=row.recommendation_type,
                recommendations_total=row.recommendations_total,
                reviewed_total=row.reviewed_total,
                accepted_total=row.accepted_total,
                dismissed_total=row.dismissed_total,
                acceptance_rate=row.acceptance_rate,
                dismissal_rate=row.dismissal_rate,
                avg_confidence_score=row.avg_confidence_score,
                avg_opportunity_score=row.avg_opportunity_score,
                avg_priority_score=row.avg_priority_score,
            )
        )
    return metrics


def generate_snapshot(session: Session, *, owner_user_id: int) -> AgentMetricSnapshotDetail:
    generated_at = utc_now()
    snapshot = AgentMetricSnapshot(
        snapshot_uuid=str(uuid4()),
        snapshot_date=generated_at.date(),
        generated_at=generated_at,
        scope=_snapshot_scope(owner_user_id=owner_user_id),
        summary_json={},
    )
    session.add(snapshot)
    session.flush()

    agent_metrics = calculate_agent_metrics(session, owner_user_id=owner_user_id)
    workflow_metrics = calculate_workflow_metrics(session, owner_user_id=owner_user_id)
    recommendation_metrics = calculate_recommendation_outcome_metrics(session, owner_user_id=owner_user_id)

    for row in agent_metrics:
        row.snapshot_id = int(snapshot.id or 0)
        session.add(row)
    for row in workflow_metrics:
        row.snapshot_id = int(snapshot.id or 0)
        session.add(row)
    for row in recommendation_metrics:
        row.snapshot_id = int(snapshot.id or 0)
        session.add(row)
    session.flush()

    snapshot.summary_json = _build_summary(
        agent_metrics=agent_metrics,
        workflow_metrics=workflow_metrics,
        recommendation_metrics=recommendation_metrics,
    )
    session.add(snapshot)
    session.commit()
    session.refresh(snapshot)
    for row in agent_metrics:
        session.refresh(row)
    for row in workflow_metrics:
        session.refresh(row)
    for row in recommendation_metrics:
        session.refresh(row)
    return AgentMetricSnapshotDetail(
        snapshot=_snapshot_read(snapshot),
        agent_metrics=[_agent_metric_read(row) for row in sorted(agent_metrics, key=lambda item: (item.agent_code, item.id or 0))],
        workflow_metrics=[
            _workflow_metric_read(row) for row in sorted(workflow_metrics, key=lambda item: (item.workflow_code, item.id or 0))
        ],
        recommendation_metrics=[
            _recommendation_metric_read(row)
            for row in sorted(recommendation_metrics, key=lambda item: (item.recommendation_type, item.id or 0))
        ],
    )


def _latest_snapshot_row(session: Session, *, owner_user_id: int) -> AgentMetricSnapshot | None:
    return session.exec(
        select(AgentMetricSnapshot)
        .where(AgentMetricSnapshot.scope == _snapshot_scope(owner_user_id=owner_user_id))
        .order_by(AgentMetricSnapshot.generated_at.desc(), AgentMetricSnapshot.id.desc())
    ).first()


def get_latest_snapshot(session: Session, *, owner_user_id: int) -> AgentAnalyticsSummaryRead:
    snapshot = _latest_snapshot_row(session, owner_user_id=owner_user_id)
    if snapshot is None:
        return AgentAnalyticsSummaryRead(
            latest_snapshot=None,
            summary_json={},
            agent_metric_count=0,
            workflow_metric_count=0,
            recommendation_metric_count=0,
        )
    agent_count = int(
        session.exec(
            select(AgentPerformanceMetric).where(AgentPerformanceMetric.snapshot_id == int(snapshot.id or 0))
        ).all().__len__()
    )
    workflow_count = int(
        session.exec(
            select(WorkflowPerformanceMetric).where(WorkflowPerformanceMetric.snapshot_id == int(snapshot.id or 0))
        ).all().__len__()
    )
    recommendation_count = int(
        session.exec(
            select(RecommendationOutcomeMetric).where(RecommendationOutcomeMetric.snapshot_id == int(snapshot.id or 0))
        ).all().__len__()
    )
    return AgentAnalyticsSummaryRead(
        latest_snapshot=_snapshot_read(snapshot),
        summary_json=dict(snapshot.summary_json or {}),
        agent_metric_count=agent_count,
        workflow_metric_count=workflow_count,
        recommendation_metric_count=recommendation_count,
    )


def list_snapshots(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 20,
    offset: int = 0,
) -> AgentMetricSnapshotListResponse:
    limit, offset = clamp_agent_pagination(limit=limit, offset=offset)
    rows = session.exec(
        select(AgentMetricSnapshot)
        .where(AgentMetricSnapshot.scope == _snapshot_scope(owner_user_id=owner_user_id))
        .order_by(AgentMetricSnapshot.generated_at.desc(), AgentMetricSnapshot.id.desc())
    ).all()
    total_items = len(rows)
    return AgentMetricSnapshotListResponse(
        items=[_snapshot_read(row) for row in rows[offset : offset + limit]],
        total_items=total_items,
        limit=limit,
        offset=offset,
    )


def get_snapshot_detail(session: Session, *, owner_user_id: int, snapshot_id: int) -> AgentMetricSnapshotDetail:
    snapshot = session.get(AgentMetricSnapshot, snapshot_id)
    if snapshot is None or snapshot.scope != _snapshot_scope(owner_user_id=owner_user_id):
        raise HTTPException(status_code=404, detail="Agent analytics snapshot was not found.")
    agent_rows = session.exec(
        select(AgentPerformanceMetric)
        .where(AgentPerformanceMetric.snapshot_id == snapshot_id)
        .order_by(AgentPerformanceMetric.agent_code.asc(), AgentPerformanceMetric.id.asc())
    ).all()
    workflow_rows = session.exec(
        select(WorkflowPerformanceMetric)
        .where(WorkflowPerformanceMetric.snapshot_id == snapshot_id)
        .order_by(WorkflowPerformanceMetric.workflow_code.asc(), WorkflowPerformanceMetric.id.asc())
    ).all()
    recommendation_rows = session.exec(
        select(RecommendationOutcomeMetric)
        .where(RecommendationOutcomeMetric.snapshot_id == snapshot_id)
        .order_by(RecommendationOutcomeMetric.recommendation_type.asc(), RecommendationOutcomeMetric.id.asc())
    ).all()
    return AgentMetricSnapshotDetail(
        snapshot=_snapshot_read(snapshot),
        agent_metrics=[_agent_metric_read(row) for row in agent_rows],
        workflow_metrics=[_workflow_metric_read(row) for row in workflow_rows],
        recommendation_metrics=[_recommendation_metric_read(row) for row in recommendation_rows],
    )


def _resolve_snapshot_id(session: Session, *, owner_user_id: int, snapshot_id: int | None) -> int | None:
    if snapshot_id is not None:
        snapshot = session.get(AgentMetricSnapshot, snapshot_id)
        if snapshot is None or snapshot.scope != _snapshot_scope(owner_user_id=owner_user_id):
            raise HTTPException(status_code=404, detail="Agent analytics snapshot was not found.")
        return snapshot_id
    latest = _latest_snapshot_row(session, owner_user_id=owner_user_id)
    return int(latest.id or 0) if latest is not None else None


def list_agent_metrics(
    session: Session,
    *,
    owner_user_id: int,
    snapshot_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> AgentPerformanceMetricListResponse:
    limit, offset = clamp_agent_pagination(limit=limit, offset=offset)
    resolved_snapshot_id = _resolve_snapshot_id(session, owner_user_id=owner_user_id, snapshot_id=snapshot_id)
    if resolved_snapshot_id is None:
        return AgentPerformanceMetricListResponse(items=[], total_items=0, limit=limit, offset=offset)
    rows = session.exec(
        select(AgentPerformanceMetric)
        .where(AgentPerformanceMetric.snapshot_id == resolved_snapshot_id)
        .order_by(AgentPerformanceMetric.agent_code.asc(), AgentPerformanceMetric.id.asc())
    ).all()
    total_items = len(rows)
    return AgentPerformanceMetricListResponse(
        items=[_agent_metric_read(row) for row in rows[offset : offset + limit]],
        total_items=total_items,
        limit=limit,
        offset=offset,
    )


def list_workflow_metrics(
    session: Session,
    *,
    owner_user_id: int,
    snapshot_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> WorkflowPerformanceMetricListResponse:
    limit, offset = clamp_agent_pagination(limit=limit, offset=offset)
    resolved_snapshot_id = _resolve_snapshot_id(session, owner_user_id=owner_user_id, snapshot_id=snapshot_id)
    if resolved_snapshot_id is None:
        return WorkflowPerformanceMetricListResponse(items=[], total_items=0, limit=limit, offset=offset)
    rows = session.exec(
        select(WorkflowPerformanceMetric)
        .where(WorkflowPerformanceMetric.snapshot_id == resolved_snapshot_id)
        .order_by(WorkflowPerformanceMetric.workflow_code.asc(), WorkflowPerformanceMetric.id.asc())
    ).all()
    total_items = len(rows)
    return WorkflowPerformanceMetricListResponse(
        items=[_workflow_metric_read(row) for row in rows[offset : offset + limit]],
        total_items=total_items,
        limit=limit,
        offset=offset,
    )


def list_recommendation_outcome_metrics(
    session: Session,
    *,
    owner_user_id: int,
    snapshot_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> RecommendationOutcomeMetricListResponse:
    limit, offset = clamp_agent_pagination(limit=limit, offset=offset)
    resolved_snapshot_id = _resolve_snapshot_id(session, owner_user_id=owner_user_id, snapshot_id=snapshot_id)
    if resolved_snapshot_id is None:
        return RecommendationOutcomeMetricListResponse(items=[], total_items=0, limit=limit, offset=offset)
    rows = session.exec(
        select(RecommendationOutcomeMetric)
        .where(RecommendationOutcomeMetric.snapshot_id == resolved_snapshot_id)
        .order_by(RecommendationOutcomeMetric.recommendation_type.asc(), RecommendationOutcomeMetric.id.asc())
    ).all()
    total_items = len(rows)
    return RecommendationOutcomeMetricListResponse(
        items=[_recommendation_metric_read(row) for row in rows[offset : offset + limit]],
        total_items=total_items,
        limit=limit,
        offset=offset,
    )
