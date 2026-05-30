from __future__ import annotations

from collections import defaultdict

from sqlmodel import Session, select

from app.models import (
    AgentCapability,
    AgentDefinition,
    AgentExecution,
    AgentPermissionAuditEvent,
    AgentPermissionPolicy,
    IntelligenceRecommendation,
    IntelligenceRecommendationReview,
    WorkflowDefinition,
    WorkflowStep,
)
from app.schemas.agent_platform import (
    AgentPlatformSummaryRead,
    AgentPlatformValidationCheckRead,
    AgentPlatformValidationRead,
)
from app.services.agent_analytics import (
    get_latest_snapshot,
    list_agent_metrics,
    list_recommendation_outcome_metrics,
    list_workflow_metrics,
)
from app.services.agent_dashboard import (
    get_dashboard_summary,
    get_recent_executions,
    get_recent_recommendations,
    get_recommendation_review_queue,
)
from app.services.agent_health import list_agent_health, list_workflow_health
from app.services.agent_permissions import (
    EXECUTE_PERMISSION_CAPABILITY,
    RECOMMENDATION_REVIEW_CAPABILITY,
    check_permission,
)
from app.services.agent_seed import FOUNDATIONAL_AGENT_SEEDS
from app.services.workflow_seed import FOUNDATIONAL_WORKFLOW_SEEDS

PLATFORM_STATUS_PASS = "PASS"
PLATFORM_STATUS_WARNING = "WARNING"
PLATFORM_STATUS_FAIL = "FAIL"

_RECOMMENDATION_REVIEW_STATUSES = {"REVIEWED", "DISMISSED", "ACCEPTED", "NOTED"}


def _aggregate_status(statuses: list[str]) -> str:
    if any(status == PLATFORM_STATUS_FAIL for status in statuses):
        return PLATFORM_STATUS_FAIL
    if any(status == PLATFORM_STATUS_WARNING for status in statuses):
        return PLATFORM_STATUS_WARNING
    return PLATFORM_STATUS_PASS


def _check(
    *,
    check_code: str,
    title: str,
    status: str,
    summary: str,
    details_json: dict[str, object],
) -> AgentPlatformValidationCheckRead:
    return AgentPlatformValidationCheckRead(
        check_code=check_code,
        title=title,
        status=status,
        summary=summary,
        details_json=details_json,
    )


def validate_agents(session: Session, *, owner_user_id: int) -> AgentPlatformValidationCheckRead:
    rows = session.exec(select(AgentDefinition).order_by(AgentDefinition.code.asc(), AgentDefinition.id.asc())).all()
    capability_rows = session.exec(
        select(AgentCapability).order_by(AgentCapability.agent_id.asc(), AgentCapability.capability_code.asc(), AgentCapability.id.asc())
    ).all()
    agent_ids_with_capabilities = {row.agent_id for row in capability_rows}
    codes = [row.code for row in rows]
    required_codes = sorted(definition.code for definition in FOUNDATIONAL_AGENT_SEEDS)
    missing_codes = sorted(set(required_codes) - set(codes))
    duplicate_codes = sorted({code for code in codes if codes.count(code) > 1})
    missing_versions = sorted(row.code for row in rows if not row.version.strip())
    missing_capabilities = sorted(row.code for row in rows if int(row.id or 0) not in agent_ids_with_capabilities)

    status = PLATFORM_STATUS_PASS
    if missing_codes or duplicate_codes or missing_versions or missing_capabilities:
        status = PLATFORM_STATUS_FAIL
    elif not rows:
        status = PLATFORM_STATUS_WARNING

    summary = (
        f"{len(rows)} agent definitions validated; "
        f"{len(required_codes) - len(missing_codes)}/{len(required_codes)} required definitions present."
    )
    return _check(
        check_code="agents",
        title="Agent Registry",
        status=status,
        summary=summary,
        details_json={
            "agent_count": len(rows),
            "required_agent_codes": required_codes,
            "missing_agent_codes": missing_codes,
            "duplicate_agent_codes": duplicate_codes,
            "agents_missing_version": missing_versions,
            "agents_missing_capabilities": missing_capabilities,
            "owner_user_id": owner_user_id,
        },
    )


def validate_workflows(session: Session, *, owner_user_id: int) -> AgentPlatformValidationCheckRead:
    rows = session.exec(select(WorkflowDefinition).order_by(WorkflowDefinition.workflow_code.asc(), WorkflowDefinition.id.asc())).all()
    step_rows = session.exec(
        select(WorkflowStep).order_by(WorkflowStep.workflow_id.asc(), WorkflowStep.step_order.asc(), WorkflowStep.id.asc())
    ).all()
    steps_by_workflow: dict[int, list[WorkflowStep]] = defaultdict(list)
    for row in step_rows:
        steps_by_workflow[row.workflow_id].append(row)

    required_codes = sorted(definition.workflow_code for definition in FOUNDATIONAL_WORKFLOW_SEEDS)
    workflow_codes = [row.workflow_code for row in rows]
    missing_codes = sorted(set(required_codes) - set(workflow_codes))
    duplicate_codes = sorted({code for code in workflow_codes if workflow_codes.count(code) > 1})
    workflows_with_invalid_step_order: list[str] = []
    workflows_missing_steps: list[str] = []
    for workflow in rows:
        ordered_steps = steps_by_workflow.get(int(workflow.id or 0), [])
        if not ordered_steps:
            workflows_missing_steps.append(workflow.workflow_code)
            continue
        expected = list(range(1, len(ordered_steps) + 1))
        actual = [row.step_order for row in ordered_steps]
        if actual != expected:
            workflows_with_invalid_step_order.append(workflow.workflow_code)

    status = PLATFORM_STATUS_PASS
    if missing_codes or duplicate_codes or workflows_with_invalid_step_order or workflows_missing_steps:
        status = PLATFORM_STATUS_FAIL
    elif not rows:
        status = PLATFORM_STATUS_WARNING

    return _check(
        check_code="workflows",
        title="Workflow Engine",
        status=status,
        summary=(
            f"{len(rows)} workflow definitions validated; "
            f"{len(required_codes) - len(missing_codes)}/{len(required_codes)} required workflows present."
        ),
        details_json={
            "workflow_count": len(rows),
            "required_workflow_codes": required_codes,
            "missing_workflow_codes": missing_codes,
            "duplicate_workflow_codes": duplicate_codes,
            "workflows_missing_steps": sorted(workflows_missing_steps),
            "workflows_with_invalid_step_order": sorted(workflows_with_invalid_step_order),
            "owner_user_id": owner_user_id,
        },
    )


def validate_permissions(session: Session, *, owner_user_id: int) -> AgentPlatformValidationCheckRead:
    agents = session.exec(select(AgentDefinition).order_by(AgentDefinition.code.asc(), AgentDefinition.id.asc())).all()
    capabilities = session.exec(
        select(AgentCapability).order_by(AgentCapability.agent_id.asc(), AgentCapability.capability_code.asc(), AgentCapability.id.asc())
    ).all()
    policies = session.exec(
        select(AgentPermissionPolicy).order_by(
            AgentPermissionPolicy.agent_id.asc(),
            AgentPermissionPolicy.capability_code.asc(),
            AgentPermissionPolicy.permission_scope.asc(),
            AgentPermissionPolicy.id.asc(),
        )
    ).all()
    denied_audits = session.exec(
        select(AgentPermissionAuditEvent)
        .where(AgentPermissionAuditEvent.decision == "denied")
        .order_by(AgentPermissionAuditEvent.created_at.desc(), AgentPermissionAuditEvent.id.desc())
    ).all()

    capability_map: dict[int, set[str]] = defaultdict(set)
    for row in capabilities:
        capability_map[row.agent_id].add(row.capability_code)
    synthetic = {EXECUTE_PERMISSION_CAPABILITY, RECOMMENDATION_REVIEW_CAPABILITY}

    invalid_allowed_policies: list[dict[str, object]] = []
    write_policies: list[dict[str, object]] = []
    for row in policies:
        known_capabilities = capability_map.get(row.agent_id, set()) | synthetic
        if row.allowed and row.permission_scope == "write":
            write_policies.append(
                {
                    "agent_id": row.agent_id,
                    "capability_code": row.capability_code,
                    "policy_id": int(row.id or 0),
                }
            )
        if row.allowed and row.capability_code not in known_capabilities:
            invalid_allowed_policies.append(
                {
                    "agent_id": row.agent_id,
                    "capability_code": row.capability_code,
                    "policy_id": int(row.id or 0),
                }
            )

    default_deny_result = None
    if agents:
        default_deny_result = check_permission(
            session,
            agent_id=int(agents[0].id or 0),
            capability_code="platform.synthetic.unknown",
            permission_scope="read",
            action_code="platform_validation_default_deny",
            audit_denied=False,
        )

    status = PLATFORM_STATUS_PASS
    if invalid_allowed_policies or write_policies:
        status = PLATFORM_STATUS_FAIL
    elif default_deny_result is None or default_deny_result.allowed:
        status = PLATFORM_STATUS_FAIL
    elif not policies:
        status = PLATFORM_STATUS_WARNING

    return _check(
        check_code="permissions",
        title="Security",
        status=status,
        summary=(
            f"{len(policies)} permission policies and {len(denied_audits)} denied audit events validated."
        ),
        details_json={
            "policy_count": len(policies),
            "denied_audit_count": len(denied_audits),
            "invalid_allowed_policies": invalid_allowed_policies,
            "allowed_write_policies": write_policies,
            "default_deny_probe_allowed": None if default_deny_result is None else default_deny_result.allowed,
            "owner_user_id": owner_user_id,
        },
    )


def validate_recommendations(session: Session, *, owner_user_id: int) -> AgentPlatformValidationCheckRead:
    rows = session.exec(
        select(IntelligenceRecommendation)
        .join(AgentExecution, AgentExecution.id == IntelligenceRecommendation.agent_execution_id)
        .where(AgentExecution.triggered_by == str(owner_user_id))
        .order_by(IntelligenceRecommendation.created_at.asc(), IntelligenceRecommendation.id.asc())
    ).all()
    review_rows = session.exec(
        select(IntelligenceRecommendationReview)
        .join(IntelligenceRecommendation, IntelligenceRecommendation.id == IntelligenceRecommendationReview.recommendation_id)
        .join(AgentExecution, AgentExecution.id == IntelligenceRecommendation.agent_execution_id)
        .where(AgentExecution.triggered_by == str(owner_user_id))
        .order_by(IntelligenceRecommendationReview.reviewed_at.asc(), IntelligenceRecommendationReview.id.asc())
    ).all()
    invalid_review_statuses = sorted(
        {
            row.review_status
            for row in review_rows
            if row.review_status not in _RECOMMENDATION_REVIEW_STATUSES
        }
    )
    recommendation_types = sorted({row.recommendation_type for row in rows})
    status = PLATFORM_STATUS_PASS
    if invalid_review_statuses:
        status = PLATFORM_STATUS_FAIL
    elif not rows:
        status = PLATFORM_STATUS_WARNING

    return _check(
        check_code="recommendations",
        title="Recommendation Engine",
        status=status,
        summary=f"{len(rows)} recommendations and {len(review_rows)} review events validated.",
        details_json={
            "recommendation_count": len(rows),
            "review_count": len(review_rows),
            "recommendation_types": recommendation_types,
            "invalid_review_statuses": invalid_review_statuses,
            "owner_user_id": owner_user_id,
        },
    )


def validate_dashboard(session: Session, *, owner_user_id: int) -> AgentPlatformValidationCheckRead:
    summary = get_dashboard_summary(session, owner_user_id=owner_user_id)
    agent_health = list_agent_health(session, owner_user_id=owner_user_id, limit=200, offset=0)
    workflow_health = list_workflow_health(session, owner_user_id=owner_user_id, limit=200, offset=0)
    recent_executions = get_recent_executions(session, owner_user_id=owner_user_id, limit=200, offset=0)
    recent_recommendations = get_recent_recommendations(session, owner_user_id=owner_user_id, limit=200, offset=0)
    review_queue = get_recommendation_review_queue(session, owner_user_id=owner_user_id, limit=200, offset=0)

    execution_pairs = [(row.started_at, row.execution_id) for row in recent_executions.items]
    recommendation_pairs = [(row.created_at, row.recommendation_id) for row in recent_recommendations.items]
    queue_pairs = [(-row.priority_score, row.created_at, row.recommendation_id) for row in review_queue.items]

    execution_order_ok = execution_pairs == sorted(execution_pairs, reverse=True)
    recommendation_order_ok = recommendation_pairs == sorted(recommendation_pairs, reverse=True)
    queue_order_ok = queue_pairs == sorted(queue_pairs)

    status = PLATFORM_STATUS_PASS
    if not execution_order_ok or not recommendation_order_ok or not queue_order_ok:
        status = PLATFORM_STATUS_FAIL
    elif recent_executions.total_items == 0 and recent_recommendations.total_items == 0:
        status = PLATFORM_STATUS_WARNING

    return _check(
        check_code="dashboard",
        title="Dashboard",
        status=status,
        summary=(
            f"Dashboard summary validated with {summary.total_agents} agents, "
            f"{recent_executions.total_items} executions, and {recent_recommendations.total_items} recommendations."
        ),
        details_json={
            "summary": summary.model_dump(mode="json"),
            "agent_health_count": len(agent_health.items),
            "workflow_health_count": len(workflow_health.items),
            "execution_count": recent_executions.total_items,
            "recommendation_count": recent_recommendations.total_items,
            "queue_count": review_queue.total_items,
            "execution_order_ok": execution_order_ok,
            "recommendation_order_ok": recommendation_order_ok,
            "queue_order_ok": queue_order_ok,
            "owner_user_id": owner_user_id,
        },
    )


def validate_analytics(session: Session, *, owner_user_id: int) -> AgentPlatformValidationCheckRead:
    summary = get_latest_snapshot(session, owner_user_id=owner_user_id)
    status = PLATFORM_STATUS_PASS
    agent_metric_rows = []
    workflow_metric_rows = []
    recommendation_metric_rows = []
    summary_keys_present = False
    ordering_ok = True

    if summary.latest_snapshot is None:
        status = PLATFORM_STATUS_WARNING
    else:
        agent_metric_rows = list_agent_metrics(session, owner_user_id=owner_user_id, limit=500, offset=0).items
        workflow_metric_rows = list_workflow_metrics(session, owner_user_id=owner_user_id, limit=500, offset=0).items
        recommendation_metric_rows = list_recommendation_outcome_metrics(
            session,
            owner_user_id=owner_user_id,
            limit=500,
            offset=0,
        ).items
        required_summary_keys = {
            "agent_success_rate",
            "agent_failure_rate",
            "avg_execution_duration_ms",
            "recommendation_acceptance_rate",
            "recommendation_dismissal_rate",
            "recommendations_generated_by_type",
        }
        summary_keys_present = required_summary_keys.issubset(set(summary.summary_json.keys()))
        ordering_ok = (
            [row.agent_code for row in agent_metric_rows] == sorted(row.agent_code for row in agent_metric_rows)
            and [row.workflow_code for row in workflow_metric_rows] == sorted(row.workflow_code for row in workflow_metric_rows)
            and [row.recommendation_type for row in recommendation_metric_rows]
            == sorted(row.recommendation_type for row in recommendation_metric_rows)
        )
        if (
            summary.agent_metric_count != len(agent_metric_rows)
            or summary.workflow_metric_count != len(workflow_metric_rows)
            or summary.recommendation_metric_count != len(recommendation_metric_rows)
            or not summary_keys_present
            or not ordering_ok
        ):
            status = PLATFORM_STATUS_FAIL

    return _check(
        check_code="analytics",
        title="Analytics",
        status=status,
        summary=(
            "Analytics snapshot coverage validated."
            if summary.latest_snapshot is not None
            else "Analytics snapshot has not been generated yet."
        ),
        details_json={
            "latest_snapshot_id": None if summary.latest_snapshot is None else summary.latest_snapshot.id,
            "agent_metric_count": len(agent_metric_rows),
            "workflow_metric_count": len(workflow_metric_rows),
            "recommendation_metric_count": len(recommendation_metric_rows),
            "summary_keys_present": summary_keys_present,
            "ordering_ok": ordering_ok,
            "owner_user_id": owner_user_id,
        },
    )


def validate_platform(session: Session, *, owner_user_id: int) -> AgentPlatformValidationRead:
    checks = [
        validate_agents(session, owner_user_id=owner_user_id),
        validate_workflows(session, owner_user_id=owner_user_id),
        validate_permissions(session, owner_user_id=owner_user_id),
        validate_recommendations(session, owner_user_id=owner_user_id),
        validate_dashboard(session, owner_user_id=owner_user_id),
        validate_analytics(session, owner_user_id=owner_user_id),
    ]
    return AgentPlatformValidationRead(
        overall_status=_aggregate_status([check.status for check in checks]),
        checks=checks,
    )


def validate_platform_summary(session: Session, *, owner_user_id: int) -> AgentPlatformSummaryRead:
    validation = validate_platform(session, owner_user_id=owner_user_id)
    checks = {row.check_code: row for row in validation.checks}
    return AgentPlatformSummaryRead(
        overall_status=validation.overall_status,
        validation_status=validation.overall_status,
        security_status=checks["permissions"].status,
        analytics_status=checks["analytics"].status,
        recommendation_engine_status=checks["recommendations"].status,
        workflow_status=checks["workflows"].status,
    )
