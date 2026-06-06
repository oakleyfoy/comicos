from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from agent_security_test_utils import grant_agent_execute, grant_agent_review
from app.models import AgentDefinition, IntelligenceRecommendation, User
from app.services.agent_execution import start_execution
from app.services.agent_registry import enable_agent
from app.services.agent_seed import seed_foundational_agents
from app.services.intelligence_engine import create_recommendation
from app.services.intelligence_review import mark_accepted, mark_dismissed, mark_reviewed
from app.services.recommendation_outcomes import calculate_outcomes_by_type
from test_inventory import register_and_login


def _enable_pricing_agent(session: Session) -> int:
    seed_foundational_agents(session)
    row = session.exec(
        select(AgentDefinition).where(AgentDefinition.code == "pricing_intelligence_agent")
    ).first()
    assert row is not None and row.id is not None
    agent_id = int(row.id)
    enable_agent(session, agent_id=agent_id)
    grant_agent_execute(session, agent_id=agent_id)
    grant_agent_review(session, agent_id=agent_id, admin=True)
    return agent_id


def test_recommendation_outcomes_aggregate_reviews_without_mutating_recommendations(
    client: TestClient,
    session: Session,
) -> None:
    agent_id = _enable_pricing_agent(session)
    owner_email = "recommendation-outcomes@example.com"
    register_and_login(client, owner_email)
    owner_row = session.exec(select(User).where(User.email == owner_email)).first()
    assert owner_row is not None and owner_row.id is not None
    owner_user_id = int(owner_row.id)

    execution = start_execution(
        session,
        agent_id=agent_id,
        triggered_by=str(owner_user_id),
        trigger_source="test:recommendation-outcomes",
    )

    first = create_recommendation(
        session,
        agent_execution_id=execution.execution.id,
        recommendation_key="underpriced-1",
        recommendation_type="underpriced_inventory",
        title="Underpriced copy 1",
        description="First pricing signal.",
        inventory_title="Amazing Spider-Man #1",
        confidence_score=0.8,
        opportunity_score=0.7,
        priority_score=0.75,
    )
    second = create_recommendation(
        session,
        agent_execution_id=execution.execution.id,
        recommendation_key="underpriced-2",
        recommendation_type="underpriced_inventory",
        title="Underpriced copy 2",
        description="Second pricing signal.",
        inventory_title="Amazing Spider-Man #2",
        confidence_score=0.6,
        opportunity_score=0.5,
        priority_score=0.55,
    )
    third = create_recommendation(
        session,
        agent_execution_id=execution.execution.id,
        recommendation_key="metadata-1",
        recommendation_type="missing_metadata",
        title="Metadata gap",
        description="Needs additional catalog metadata.",
        inventory_title="X-Men #1",
        confidence_score=0.9,
        opportunity_score=0.4,
        priority_score=0.5,
    )

    recommendation_status_before = {
        row.id: row.status for row in session.exec(select(IntelligenceRecommendation)).all()
    }

    mark_reviewed(
        session,
        owner_user_id=owner_user_id,
        recommendation_id=first.id,
        reviewed_by=owner_email,
    )
    mark_accepted(
        session,
        owner_user_id=owner_user_id,
        recommendation_id=second.id,
        reviewed_by=owner_email,
    )
    mark_dismissed(
        session,
        owner_user_id=owner_user_id,
        recommendation_id=third.id,
        reviewed_by=owner_email,
    )

    outcomes = {
        row.recommendation_type: row
        for row in calculate_outcomes_by_type(session, owner_user_id=owner_user_id)
    }

    assert outcomes["underpriced_inventory"].recommendations_total == 2
    assert outcomes["underpriced_inventory"].reviewed_total == 2
    assert outcomes["underpriced_inventory"].accepted_total == 1
    assert outcomes["underpriced_inventory"].dismissed_total == 0
    assert outcomes["underpriced_inventory"].acceptance_rate == 0.5
    assert outcomes["underpriced_inventory"].dismissal_rate == 0.0
    assert outcomes["underpriced_inventory"].avg_confidence_score == 0.7
    assert outcomes["underpriced_inventory"].avg_opportunity_score == 0.6
    assert outcomes["underpriced_inventory"].avg_priority_score == 0.65

    assert outcomes["missing_metadata"].recommendations_total == 1
    assert outcomes["missing_metadata"].reviewed_total == 1
    assert outcomes["missing_metadata"].accepted_total == 0
    assert outcomes["missing_metadata"].dismissed_total == 1
    assert outcomes["missing_metadata"].acceptance_rate == 0.0
    assert outcomes["missing_metadata"].dismissal_rate == 1.0

    recommendation_status_after = {
        row.id: row.status for row in session.exec(select(IntelligenceRecommendation)).all()
    }
    assert recommendation_status_after == recommendation_status_before


def test_p73_recommendation_outcome_creation_and_list(client: TestClient, session: Session) -> None:
    from sqlmodel import select

    from app.models import User
    from app.schemas.recommendation_outcome import P73RecommendationOutcomeCreatePayload
    from app.services.recommendation_outcome_service import create_outcome

    token = register_and_login(client, "p73-outcomes-list@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p73-outcomes-list@example.com")).one().id or 0)
    row = create_outcome(
        session,
        owner_user_id=owner_id,
        payload=P73RecommendationOutcomeCreatePayload(
            recommendation_id="rec-p73-list",
            series="Spider-Man",
            issue="300",
            variant="A",
            recommendation_type="SELL",
            recommendation_category="EXIT",
        ),
    )
    assert row.current_status == "RECOMMENDED"
    assert row.recommendation_type == "SELL"

    listed = client.get(
        "/api/v1/recommendation-feedback/outcomes",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert listed.status_code == 200
    assert listed.json()["data"]["items"][0]["recommendation_id"] == "rec-p73-list"
