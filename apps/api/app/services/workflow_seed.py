from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, select

from app.models import AgentDefinition, WorkflowDefinition
from app.schemas.agent_workflow import WorkflowDefinitionCreate, WorkflowDefinitionRead, WorkflowStepCreate
from app.services.agent_seed import seed_foundational_agents
from app.services.workflow_registry import create_workflow, get_workflow, update_workflow


@dataclass(frozen=True)
class WorkflowSeedDefinition:
    workflow_code: str
    workflow_name: str
    description: str
    step_agent_codes: tuple[str, ...]


FOUNDATIONAL_WORKFLOW_SEEDS: tuple[WorkflowSeedDefinition, ...] = (
    WorkflowSeedDefinition(
        workflow_code="inventory_refresh_workflow",
        workflow_name="InventoryRefreshWorkflow",
        description="Placeholder deterministic workflow for future inventory refresh orchestration.",
        step_agent_codes=("inventory_agent",),
    ),
    WorkflowSeedDefinition(
        workflow_code="pricing_refresh_workflow",
        workflow_name="PricingRefreshWorkflow",
        description="Placeholder deterministic workflow for future pricing refresh orchestration.",
        step_agent_codes=("inventory_agent", "pricing_agent"),
    ),
    WorkflowSeedDefinition(
        workflow_code="market_refresh_workflow",
        workflow_name="MarketRefreshWorkflow",
        description="Placeholder deterministic workflow for future market refresh orchestration.",
        step_agent_codes=("inventory_agent", "pricing_agent", "market_agent"),
    ),
    WorkflowSeedDefinition(
        workflow_code="analytics_refresh_workflow",
        workflow_name="AnalyticsRefreshWorkflow",
        description="Placeholder deterministic workflow for future analytics refresh orchestration.",
        step_agent_codes=("inventory_agent", "pricing_agent", "market_agent", "analytics_agent"),
    ),
)


def _workflow_steps_for_codes(session: Session, *, step_agent_codes: tuple[str, ...]) -> list[WorkflowStepCreate]:
    steps: list[WorkflowStepCreate] = []
    for index, agent_code in enumerate(step_agent_codes, start=1):
        agent = session.exec(select(AgentDefinition).where(AgentDefinition.code == agent_code)).first()
        if agent is None or agent.id is None:
            raise ValueError(f"Missing agent seed for workflow step {agent_code}")
        steps.append(
            WorkflowStepCreate(
                step_order=index,
                agent_definition_id=int(agent.id),
                step_name=agent.name,
                step_code=agent_code,
                required_success=True,
                timeout_seconds=300,
            )
        )
    return steps


def seed_foundational_workflows(session: Session) -> list[WorkflowDefinitionRead]:
    seed_foundational_agents(session)
    seeded: list[WorkflowDefinitionRead] = []
    for definition in FOUNDATIONAL_WORKFLOW_SEEDS:
        existing = session.exec(
            select(WorkflowDefinition).where(WorkflowDefinition.workflow_code == definition.workflow_code)
        ).first()
        steps = _workflow_steps_for_codes(session, step_agent_codes=definition.step_agent_codes)
        if existing is None:
            seeded.append(
                create_workflow(
                    session,
                    payload=WorkflowDefinitionCreate(
                        workflow_code=definition.workflow_code,
                        workflow_name=definition.workflow_name,
                        description=definition.description,
                        enabled=False,
                        schedule_enabled=False,
                        cron_expression=None,
                        next_run_at=None,
                        steps=steps,
                    ),
                )
            )
            continue
        if existing.id is not None:
            try:
                seeded.append(
                    update_workflow(
                        session,
                        workflow_id=int(existing.id),
                        workflow_name=definition.workflow_name,
                        description=definition.description,
                        schedule_enabled=False,
                        cron_expression=None,
                        next_run_at=None,
                        steps=steps,
                    )
                )
            except Exception:
                seeded.append(get_workflow(session, workflow_id=int(existing.id)))
        else:
            seeded.append(get_workflow(session, workflow_id=int(existing.id or 0)))
    return seeded
