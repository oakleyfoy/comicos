from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from agent_security_test_utils import grant_agent_execute, grant_agent_review
from app.models import AgentDefinition, IntelligenceRecommendation, IntelligenceRecommendationReview
from app.services.agent_execution import start_execution
from app.services.agent_registry import enable_agent
from app.services.agent_seed import seed_foundational_agents
from app.services.intelligence_engine import (
    attach_evidence,
    calculate_confidence_score,
    calculate_opportunity_score,
    calculate_priority_score,
    create_recommendation,
    recommendation_detail,
)
from app.services.intelligence_review import mark_reviewed


def _enabled_agent_id(session: Session, *, code: str) -> int:
    seed_foundational_agents(session)
    row = session.exec(select(AgentDefinition).where(AgentDefinition.code == code)).first()
    assert row is not None and row.id is not None
    enable_agent(session, agent_id=int(row.id))
    grant_agent_execute(session, agent_id=int(row.id))
    grant_agent_review(session, agent_id=int(row.id))
    return int(row.id)


def test_intelligence_engine_scoring_is_deterministic_and_recommendations_are_append_only(
    client: TestClient,
    session: Session,
) -> None:
    del client
    agent_id = _enabled_agent_id(session, code="pricing_intelligence_agent")
    execution = start_execution(
        session,
        agent_id=agent_id,
        triggered_by="101",
        trigger_source="test:intelligence-engine",
    )

    confidence = calculate_confidence_score(evidence_scores=[1.0, 0.88, 0.76], supporting_signal_count=3, data_freshness_score=1.0)
    opportunity = calculate_opportunity_score(spread_score=0.8, trend_score=0.7, urgency_score=0.4, scarcity_score=0.3)
    priority = calculate_priority_score(opportunity_score=opportunity, confidence_score=confidence, urgency_score=0.4)

    assert confidence == calculate_confidence_score(
        evidence_scores=[1.0, 0.88, 0.76],
        supporting_signal_count=3,
        data_freshness_score=1.0,
    )
    assert opportunity == calculate_opportunity_score(
        spread_score=0.8,
        trend_score=0.7,
        urgency_score=0.4,
        scarcity_score=0.3,
    )
    assert priority == calculate_priority_score(
        opportunity_score=opportunity,
        confidence_score=confidence,
        urgency_score=0.4,
    )

    recommendation = create_recommendation(
        session,
        agent_execution_id=execution.execution.id,
        recommendation_key="underpriced_inventory|inventory_copy|1",
        recommendation_type="underpriced_inventory",
        title="Invincible #1 appears underpriced",
        description="Internal value signals are above acquisition cost.",
        inventory_copy_id=None,
        inventory_title="Invincible #1",
        confidence_score=confidence,
        opportunity_score=opportunity,
        priority_score=priority,
        recommendation_payload_json={"candidate_action": "review_price_position"},
    )
    evidence = attach_evidence(
        session,
        recommendation_id=recommendation.id,
        evidence_type="market_fmv_snapshot",
        evidence_source="market_fmv_snapshot",
        evidence_payload_json={"estimated_fmv": "30.00", "acquisition_cost": "12.00"},
        evidence_score=0.88,
    )
    detail = recommendation_detail(session, recommendation_id=recommendation.id)
    assert detail.recommendation.recommendation_uuid == recommendation.recommendation_uuid
    assert detail.evidence[0].id == evidence.id
    assert detail.reviews == []

    mark_reviewed(
        session,
        owner_user_id=101,
        recommendation_id=recommendation.id,
        reviewed_by="101",
        review_notes="Looks actionable.",
    )
    refreshed = recommendation_detail(session, recommendation_id=recommendation.id)
    assert refreshed.recommendation.status == "REVIEWED"
    assert len(refreshed.reviews) == 1
    assert refreshed.reviews[0].review_notes == "Looks actionable."

    stored_row = session.get(IntelligenceRecommendation, recommendation.id)
    assert stored_row is not None
    assert stored_row.status == "OPEN"
    assert len(session.exec(select(IntelligenceRecommendationReview).where(IntelligenceRecommendationReview.recommendation_id == recommendation.id)).all()) == 1
