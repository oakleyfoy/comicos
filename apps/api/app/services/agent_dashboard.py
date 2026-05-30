from __future__ import annotations

from sqlmodel import Session, func, select

from app.models import (
    AgentDefinition,
    AgentExecution,
    IntelligenceRecommendation,
    IntelligenceRecommendationReview,
    ResearchSnapshot,
    WorkflowDefinition,
    WorkflowExecution,
    WorkflowStepExecution,
)
from app.schemas.agent_dashboard import (
    AgentDashboardSummaryRead,
    RecommendationQueueListResponse,
    RecommendationQueueRead,
    RecentExecutionListResponse,
    RecentExecutionRead,
)
from app.services.agent_health import list_agent_health, list_workflow_health
from app.services.agent_registry import clamp_agent_pagination


_ACTIVE_AGENT_STATUSES = {"PENDING", "RUNNING"}


def _latest_review_status_map(
    session: Session,
    *,
    recommendation_ids: list[int],
) -> dict[int, str]:
    if not recommendation_ids:
        return {}
    review_rows = session.exec(
        select(IntelligenceRecommendationReview)
        .where(IntelligenceRecommendationReview.recommendation_id.in_(recommendation_ids))
        .order_by(
            IntelligenceRecommendationReview.reviewed_at.asc(),
            IntelligenceRecommendationReview.id.asc(),
        )
    ).all()
    latest: dict[int, str] = {}
    for row in review_rows:
        latest[row.recommendation_id] = row.review_status
    return latest


def get_dashboard_summary(session: Session, *, owner_user_id: int) -> AgentDashboardSummaryRead:
    total_agents = int(session.exec(select(func.count()).select_from(AgentDefinition)).one())
    enabled_agents = int(
        session.exec(select(func.count()).select_from(AgentDefinition).where(AgentDefinition.enabled.is_(True))).one()
    )
    total_workflows = int(session.exec(select(func.count()).select_from(WorkflowDefinition)).one())
    enabled_workflows = int(
        session.exec(select(func.count()).select_from(WorkflowDefinition).where(WorkflowDefinition.enabled.is_(True))).one()
    )
    active_executions = int(
        session.exec(
            select(func.count())
            .select_from(AgentExecution)
            .where(
                AgentExecution.triggered_by == str(owner_user_id),
                AgentExecution.status.in_(tuple(sorted(_ACTIVE_AGENT_STATUSES))),
            )
        ).one()
    )
    total_research_snapshots = int(
        session.exec(
            select(func.count())
            .select_from(ResearchSnapshot)
            .join(AgentExecution, AgentExecution.id == ResearchSnapshot.agent_execution_id)
            .where(AgentExecution.triggered_by == str(owner_user_id))
        ).one()
    )
    visible_recommendation_ids = session.exec(
        select(IntelligenceRecommendation.id)
        .join(AgentExecution, AgentExecution.id == IntelligenceRecommendation.agent_execution_id)
        .where(AgentExecution.triggered_by == str(owner_user_id))
    ).all()
    total_recommendations = len(visible_recommendation_ids)
    reviewed_ids = set(
        session.exec(
            select(IntelligenceRecommendationReview.recommendation_id).where(
                IntelligenceRecommendationReview.recommendation_id.in_(visible_recommendation_ids or [-1])
            )
        ).all()
    )
    return AgentDashboardSummaryRead(
        total_agents=total_agents,
        enabled_agents=enabled_agents,
        total_workflows=total_workflows,
        enabled_workflows=enabled_workflows,
        active_executions=active_executions,
        total_research_snapshots=total_research_snapshots,
        total_recommendations=total_recommendations,
        recommendations_awaiting_review=max(0, total_recommendations - len(reviewed_ids)),
    )


def get_agent_status_summary(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
):
    return list_agent_health(session, owner_user_id=owner_user_id, limit=limit, offset=offset)


def get_workflow_status_summary(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
):
    return list_workflow_health(session, owner_user_id=owner_user_id, limit=limit, offset=offset)


def get_recent_executions(
    session: Session,
    *,
    owner_user_id: int,
    agent_code: str | None = None,
    workflow_code: str | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> RecentExecutionListResponse:
    limit, offset = clamp_agent_pagination(limit=limit, offset=offset)
    stmt = (
        select(AgentExecution, AgentDefinition)
        .join(AgentDefinition, AgentDefinition.id == AgentExecution.agent_id)
        .where(AgentExecution.triggered_by == str(owner_user_id))
    )
    if agent_code is not None:
        stmt = stmt.where(AgentDefinition.code == agent_code.strip())
    if status is not None:
        stmt = stmt.where(AgentExecution.status == status.strip().upper())
    rows = session.exec(
        stmt.order_by(AgentExecution.started_at.desc(), AgentExecution.id.desc())
    ).all()

    execution_ids = [int(execution.id or 0) for execution, _ in rows]
    workflow_links = session.exec(
        select(WorkflowStepExecution, WorkflowExecution, WorkflowDefinition)
        .join(WorkflowExecution, WorkflowExecution.id == WorkflowStepExecution.workflow_execution_id)
        .join(WorkflowDefinition, WorkflowDefinition.id == WorkflowExecution.workflow_id)
        .where(WorkflowStepExecution.agent_execution_id.in_(execution_ids or [-1]))
    ).all()
    workflow_by_execution_id: dict[int, tuple[WorkflowStepExecution, WorkflowExecution, WorkflowDefinition]] = {
        int(step_execution.agent_execution_id): (step_execution, workflow_execution, workflow_definition)
        for step_execution, workflow_execution, workflow_definition in workflow_links
    }

    items = []
    for execution, agent in rows:
        workflow_link = workflow_by_execution_id.get(int(execution.id or 0))
        workflow_step_execution = workflow_link[0] if workflow_link is not None else None
        workflow_execution = workflow_link[1] if workflow_link is not None else None
        workflow_definition = workflow_link[2] if workflow_link is not None else None
        if workflow_code is not None and (workflow_definition is None or workflow_definition.workflow_code != workflow_code.strip()):
            continue
        items.append(
            RecentExecutionRead(
                execution_id=int(execution.id or 0),
                execution_uuid=execution.execution_uuid,
                agent_id=execution.agent_id,
                agent_code=agent.code,
                agent_name=agent.name,
                workflow_execution_id=int(workflow_execution.id or 0) if workflow_execution is not None else None,
                workflow_id=int(workflow_definition.id or 0) if workflow_definition is not None else None,
                workflow_code=workflow_definition.workflow_code if workflow_definition is not None else None,
                workflow_name=workflow_definition.workflow_name if workflow_definition is not None else None,
                status=execution.status,
                started_at=execution.started_at,
                completed_at=execution.completed_at,
                duration_ms=execution.execution_duration_ms,
                trigger_source=execution.trigger_source,
            )
        )
    total_items = len(items)
    return RecentExecutionListResponse(
        items=items[offset : offset + limit],
        total_items=total_items,
        limit=limit,
        offset=offset,
    )


def get_recent_recommendations(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_type: str | None = None,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> RecommendationQueueListResponse:
    limit, offset = clamp_agent_pagination(limit=limit, offset=offset)
    rows = session.exec(
        select(IntelligenceRecommendation)
        .join(AgentExecution, AgentExecution.id == IntelligenceRecommendation.agent_execution_id)
        .where(AgentExecution.triggered_by == str(owner_user_id))
        .order_by(IntelligenceRecommendation.created_at.desc(), IntelligenceRecommendation.id.desc())
    ).all()
    latest_status_map = _latest_review_status_map(
        session,
        recommendation_ids=[int(row.id or 0) for row in rows],
    )

    items = []
    for row in rows:
        row_status = latest_status_map.get(int(row.id or 0), row.status)
        if recommendation_type is not None and row.recommendation_type != recommendation_type.strip().lower():
            continue
        if status is not None and row_status != status.strip().upper():
            continue
        items.append(
            RecommendationQueueRead(
                recommendation_id=int(row.id or 0),
                recommendation_uuid=row.recommendation_uuid,
                recommendation_type=row.recommendation_type,
                title=row.title,
                inventory_title=row.inventory_title,
                status=row_status,
                confidence_score=row.confidence_score,
                opportunity_score=row.opportunity_score,
                priority_score=row.priority_score,
                created_at=row.created_at,
                agent_execution_id=row.agent_execution_id,
            )
        )
    total_items = len(items)
    return RecommendationQueueListResponse(
        items=items[offset : offset + limit],
        total_items=total_items,
        limit=limit,
        offset=offset,
    )


def get_recommendation_review_queue(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 20,
    offset: int = 0,
) -> RecommendationQueueListResponse:
    limit, offset = clamp_agent_pagination(limit=limit, offset=offset)
    rows = session.exec(
        select(IntelligenceRecommendation)
        .join(AgentExecution, AgentExecution.id == IntelligenceRecommendation.agent_execution_id)
        .where(AgentExecution.triggered_by == str(owner_user_id))
        .order_by(
            IntelligenceRecommendation.priority_score.desc(),
            IntelligenceRecommendation.created_at.asc(),
            IntelligenceRecommendation.id.asc(),
        )
    ).all()
    latest_status_map = _latest_review_status_map(
        session,
        recommendation_ids=[int(row.id or 0) for row in rows],
    )

    items = [
        RecommendationQueueRead(
            recommendation_id=int(row.id or 0),
            recommendation_uuid=row.recommendation_uuid,
            recommendation_type=row.recommendation_type,
            title=row.title,
            inventory_title=row.inventory_title,
            status=latest_status_map.get(int(row.id or 0), row.status),
            confidence_score=row.confidence_score,
            opportunity_score=row.opportunity_score,
            priority_score=row.priority_score,
            created_at=row.created_at,
            agent_execution_id=row.agent_execution_id,
        )
        for row in rows
        if int(row.id or 0) not in latest_status_map
    ]
    total_items = len(items)
    return RecommendationQueueListResponse(
        items=items[offset : offset + limit],
        total_items=total_items,
        limit=limit,
        offset=offset,
    )
