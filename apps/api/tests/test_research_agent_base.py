from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from agent_security_test_utils import grant_agent_execute
from app.models import AgentDefinition, ResearchEvidence, ResearchFinding, ResearchSnapshot
from app.services.agent_execution import complete_execution, start_execution
from app.services.agent_registry import enable_agent
from app.services.agent_seed import seed_foundational_agents
from app.services.research_agent_base import (
    add_evidence,
    add_finding,
    complete_snapshot,
    create_snapshot,
    get_finding_read,
    get_snapshot_detail,
)


def _enabled_agent_id(session: Session, *, code: str) -> int:
    seed_foundational_agents(session)
    row = session.exec(select(AgentDefinition).where(AgentDefinition.code == code)).first()
    assert row is not None and row.id is not None
    enable_agent(session, agent_id=int(row.id))
    grant_agent_execute(session, agent_id=int(row.id))
    return int(row.id)


def test_research_agent_base_creates_snapshot_findings_evidence_and_preserves_linkage(
    client: TestClient,
    session: Session,
) -> None:
    del client
    agent_id = _enabled_agent_id(session, code="marketplace_research_agent")
    execution = start_execution(
        session,
        agent_id=agent_id,
        triggered_by="101",
        trigger_source="test:research-base",
    )

    snapshot = create_snapshot(
        session,
        agent_execution_id=execution.execution.id,
        agent_code="marketplace_research_agent",
        research_type="marketplace",
        input_scope_json={"owner_user_id": 101, "inventory_copy_count": 1},
    )
    finding = add_finding(
        session,
        snapshot_id=snapshot.id,
        finding_code="possible_underpriced_item|inventory_copy|1",
        finding_type="possible_underpriced_item",
        title="Invincible #1 has upside",
        description="The copy has strong spread versus cost basis.",
        confidence_score=0.91,
        priority_score=0.84,
        recommendation_json={"candidate_action": "review_listing_or_hold_strategy"},
    )
    evidence = add_evidence(
        session,
        finding_id=finding.id,
        evidence_type="inventory_projection",
        source_name="inventory_copy",
        source_payload_json={"inventory_copy_id": 1, "acquisition_cost": "10.00", "current_fmv": "25.00"},
        evidence_score=1.0,
    )
    completed = complete_snapshot(
        session,
        snapshot_id=snapshot.id,
        summary_json={"finding_count": 1, "findings_by_type": {"possible_underpriced_item": 1}},
    )
    complete_execution(
        session,
        execution_id=execution.execution.id,
        event_payload_json={"snapshot_id": snapshot.id, "finding_count": 1},
    )

    assert completed.agent_execution_id == execution.execution.id
    assert completed.status == "COMPLETED"
    assert finding.snapshot_id == snapshot.id
    assert evidence.finding_id == finding.id

    detail = get_snapshot_detail(session, snapshot_id=snapshot.id)
    assert detail.snapshot.snapshot_uuid
    assert detail.snapshot.summary_json["finding_count"] == 1
    assert [row.finding_code for row in detail.findings] == ["possible_underpriced_item|inventory_copy|1"]
    assert detail.findings[0].evidence[0].source_payload_json["inventory_copy_id"] == 1
    assert get_finding_read(session, finding_id=finding.id).evidence[0].id == evidence.id

    assert session.exec(select(ResearchSnapshot).where(ResearchSnapshot.id == snapshot.id)).one().agent_execution_id == execution.execution.id
    assert session.exec(select(ResearchFinding).where(ResearchFinding.id == finding.id)).one().snapshot_id == snapshot.id
    assert session.exec(select(ResearchEvidence).where(ResearchEvidence.id == evidence.id)).one().finding_id == finding.id
