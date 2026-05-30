from __future__ import annotations

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from agent_security_test_utils import grant_agent_execute, grant_agent_review
from app.models import (
    AgentCapability,
    AgentDefinition,
    AgentPermissionAuditEvent,
    User,
    WorkflowDefinition,
    WorkflowExecution,
)
from app.schemas.agent import AgentCapabilityDeclaration, AgentDefinitionCreate
from app.schemas.agent_security import AgentPermissionPolicyCreate
from app.schemas.agent_workflow import WorkflowDefinitionCreate, WorkflowStepCreate
from app.services.agent_execution import start_execution
from app.services.agent_permissions import (
    EXECUTE_PERMISSION_CAPABILITY,
    RECOMMENDATION_REVIEW_CAPABILITY,
    check_permission,
    grant_permission,
    list_agent_permissions,
    revoke_permission,
)
from app.services.agent_registry import enable_agent, register_agent
from app.services.agent_seed import seed_foundational_agents
from app.services.intelligence_engine import create_recommendation
from app.services.intelligence_review import mark_accepted, mark_reviewed
from app.services.workflow_orchestrator import execute_step, start_workflow
from app.services.workflow_registry import create_workflow, enable_workflow
from test_inventory import register_and_login


def _registered_enabled_agent(
    session: Session,
    *,
    code: str,
    capabilities: list[AgentCapabilityDeclaration] | None = None,
) -> int:
    registered = register_agent(
        session,
        payload=AgentDefinitionCreate(
            code=code,
            name=f"{code} name",
            description=f"{code} description",
            version="1.0.0",
            enabled=False,
            capabilities=capabilities or [],
        ),
    )
    enabled = enable_agent(session, agent_id=registered.id)
    return enabled.id


def _owner_id(session: Session, email: str) -> int:
    row = session.exec(select(User).where(User.email == email)).first()
    assert row is not None and row.id is not None
    return int(row.id)


def test_permission_service_defaults_to_deny_and_supports_allow_and_revoke(
    client: TestClient,
    session: Session,
) -> None:
    del client
    agent_id = _registered_enabled_agent(
        session,
        code="permission_matrix_agent",
        capabilities=[AgentCapabilityDeclaration(capability_code="inventory.read", capability_name="Inventory Read")],
    )

    denied = check_permission(
        session,
        agent_id=agent_id,
        capability_code="inventory.read",
        permission_scope="read",
        action_code="test_read",
        event_payload_json={"source": "unit-test"},
    )
    assert not denied.allowed
    assert denied.reason == "missing_policy"

    audit_rows = session.exec(select(AgentPermissionAuditEvent).order_by(AgentPermissionAuditEvent.id.asc())).all()
    assert audit_rows[-1].decision == "denied"
    assert audit_rows[-1].capability_code == "inventory.read"

    granted = grant_permission(
        session,
        payload=AgentPermissionPolicyCreate(
            agent_id=agent_id,
            capability_code="inventory.read",
            permission_scope="read",
            allowed=True,
        ),
    )
    assert granted.allowed is True

    allowed = check_permission(
        session,
        agent_id=agent_id,
        capability_code="inventory.read",
        permission_scope="read",
        action_code="test_read",
    )
    assert allowed.allowed is True
    assert allowed.reason == "policy_allowed"

    listed = list_agent_permissions(session, agent_id=agent_id, limit=20, offset=0)
    assert [row.capability_code for row in listed.items] == ["inventory.read"]

    revoke_permission(session, policy_id=granted.id)
    denied_again = check_permission(
        session,
        agent_id=agent_id,
        capability_code="inventory.read",
        permission_scope="read",
        action_code="test_read",
    )
    assert not denied_again.allowed
    assert denied_again.reason == "missing_policy"


def test_agent_execution_requires_explicit_execute_permission(
    client: TestClient,
    session: Session,
) -> None:
    del client
    agent_id = _registered_enabled_agent(
        session,
        code="permission_execution_agent",
        capabilities=[AgentCapabilityDeclaration(capability_code="inventory.read", capability_name="Inventory Read")],
    )
    grant_permission(
        session,
        payload=AgentPermissionPolicyCreate(
            agent_id=agent_id,
            capability_code="inventory.read",
            permission_scope="read",
            allowed=True,
        ),
    )

    try:
        start_execution(
            session,
            agent_id=agent_id,
            triggered_by="101",
            trigger_source="unit-test",
        )
    except HTTPException as exc:
        assert exc.status_code == 403
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected execution without explicit execute permission to be rejected.")

    grant_agent_execute(session, agent_id=agent_id)
    started = start_execution(
        session,
        agent_id=agent_id,
        triggered_by="101",
        trigger_source="unit-test",
    )
    assert started.execution.status == "RUNNING"


def test_workflow_step_fails_safely_when_step_agent_lacks_execute_permission(
    client: TestClient,
    session: Session,
) -> None:
    del client
    seed_foundational_agents(session)
    inventory_row = session.exec(select(AgentDefinition).where(AgentDefinition.code == "inventory_agent")).first()
    assert inventory_row is not None and inventory_row.id is not None
    enable_agent(session, agent_id=int(inventory_row.id))

    workflow = create_workflow(
        session,
        payload=WorkflowDefinitionCreate(
            workflow_code="permission_guardrail_workflow",
            workflow_name="PermissionGuardrailWorkflow",
            description="Workflow permission guardrail test",
            enabled=False,
            schedule_enabled=False,
            steps=[
                WorkflowStepCreate(
                    step_order=1,
                    agent_definition_id=int(inventory_row.id),
                    step_name="InventoryAgent",
                    step_code="inventory_agent",
                    required_success=True,
                    timeout_seconds=60,
                )
            ],
        ),
    )
    enable_workflow(session, workflow_id=workflow.id)
    execution = start_workflow(
        session,
        workflow_id=workflow.id,
        triggered_by="101",
        trigger_source="workflow-test",
    )

    try:
        execute_step(session, workflow_execution_id=execution.execution.id)
    except HTTPException as exc:
        assert exc.status_code == 403
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected workflow step without execute permission to be rejected.")

    workflow_row = session.get(WorkflowExecution, execution.execution.id)
    assert workflow_row is not None
    assert workflow_row.status == "FAILED"
    audit_rows = session.exec(
        select(AgentPermissionAuditEvent)
        .where(AgentPermissionAuditEvent.agent_id == int(inventory_row.id))
        .order_by(AgentPermissionAuditEvent.id.asc())
    ).all()
    assert audit_rows[-1].decision == "denied"
    assert audit_rows[-1].action_code == "workflow_step_execute"


def test_recommendation_reviews_require_review_and_admin_permissions(
    client: TestClient,
    session: Session,
) -> None:
    email = "permission-review-owner@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    agent_id = _registered_enabled_agent(
        session,
        code="review_guardrail_agent",
        capabilities=[AgentCapabilityDeclaration(capability_code="analytics.read", capability_name="Analytics Read")],
    )
    grant_permission(
        session,
        payload=AgentPermissionPolicyCreate(
            agent_id=agent_id,
            capability_code="analytics.read",
            permission_scope="read",
            allowed=True,
        ),
    )
    grant_agent_execute(session, agent_id=agent_id)
    execution = start_execution(
        session,
        agent_id=agent_id,
        triggered_by=str(owner_id),
        trigger_source="unit-test",
    )
    recommendation = create_recommendation(
        session,
        agent_execution_id=execution.execution.id,
        recommendation_key="review-guardrail|1",
        recommendation_type="watch_candidate",
        title="Review guardrail recommendation",
        description="Permission-gated review action.",
        confidence_score=0.8,
        opportunity_score=0.7,
        priority_score=0.75,
        recommendation_payload_json={},
    )

    try:
        mark_reviewed(
            session,
            owner_user_id=owner_id,
            recommendation_id=recommendation.id,
            reviewed_by=str(owner_id),
        )
    except HTTPException as exc:
        assert exc.status_code == 403
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected review without review permission to be rejected.")

    grant_agent_review(session, agent_id=agent_id, admin=False)
    reviewed = mark_reviewed(
        session,
        owner_user_id=owner_id,
        recommendation_id=recommendation.id,
        reviewed_by=str(owner_id),
    )
    assert reviewed.recommendation.status == "REVIEWED"

    try:
        mark_accepted(
            session,
            owner_user_id=owner_id,
            recommendation_id=recommendation.id,
            reviewed_by=str(owner_id),
        )
    except HTTPException as exc:
        assert exc.status_code == 403
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected accept without admin permission to be rejected.")

    grant_permission(
        session,
        payload=AgentPermissionPolicyCreate(
            agent_id=agent_id,
            capability_code=RECOMMENDATION_REVIEW_CAPABILITY,
            permission_scope="admin",
            allowed=True,
        ),
    )
    accepted = mark_accepted(
        session,
        owner_user_id=owner_id,
        recommendation_id=recommendation.id,
        reviewed_by=str(owner_id),
    )
    assert accepted.recommendation.status == "ACCEPTED"
