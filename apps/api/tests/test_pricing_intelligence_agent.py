from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from agent_security_test_utils import grant_agent_execute
from app.models import AgentDefinition, AgentExecution, InventoryCopy
from app.services.agent_registry import enable_agent
from app.services.agent_seed import seed_foundational_agents
from app.services.pricing_intelligence_agent import run_pricing_intelligence_agent
from test_marketplace_research_agent import _seed_marketplace_inventory


def _enable_pricing_intelligence_agent(session: Session) -> None:
    seed_foundational_agents(session)
    row = session.exec(select(AgentDefinition).where(AgentDefinition.code == "pricing_intelligence_agent")).first()
    assert row is not None and row.id is not None
    enable_agent(session, agent_id=int(row.id))
    grant_agent_execute(session, agent_id=int(row.id))


def _inventory_state(session: Session, *, owner_user_id: int) -> list[tuple]:
    rows = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id).order_by(InventoryCopy.id.asc())).all()
    return [
        (
            int(row.id or 0),
            str(row.current_fmv) if row.current_fmv is not None else None,
            row.hold_status,
            row.order_status,
            row.metadata_identity_key,
        )
        for row in rows
    ]


def test_pricing_intelligence_agent_generates_evidence_backed_recommendations_without_mutation(
    client: TestClient,
    session: Session,
) -> None:
    _enable_pricing_intelligence_agent(session)
    user = _seed_marketplace_inventory(client, session, email="pricing-intelligence-owner@example.com")

    before_inventory_state = _inventory_state(session, owner_user_id=int(user.id or 0))
    execution_count_before = len(session.exec(select(AgentExecution)).all())

    result = run_pricing_intelligence_agent(session, current_user=user)

    assert result.snapshot.status == "COMPLETED"
    assert result.snapshot.research_type == "pricing_intelligence"
    assert len(result.recommendations) >= 3
    assert {row.recommendation_type for row in result.recommendations} >= {
        "underpriced_inventory",
        "rapid_appreciation_candidate",
        "grade_candidate",
    }
    assert all(row.confidence_score > 0 for row in result.recommendations)
    assert all(row.opportunity_score > 0 for row in result.recommendations)

    after_inventory_state = _inventory_state(session, owner_user_id=int(user.id or 0))
    assert before_inventory_state == after_inventory_state
    assert len(session.exec(select(AgentExecution)).all()) == execution_count_before + 1
