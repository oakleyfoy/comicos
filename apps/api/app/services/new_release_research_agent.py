from __future__ import annotations

from collections import Counter

from sqlmodel import Session, select

from app.models import AgentDefinition, User
from app.schemas.research_agent import ResearchSnapshotDetail
from app.services.agent_execution import complete_execution, fail_execution, start_execution
from app.services.order_arrival_intelligence import compute_order_arrival_intelligence
from app.services.research_agent_base import (
    add_evidence,
    add_finding,
    complete_snapshot,
    create_snapshot,
    fail_snapshot,
    get_snapshot_detail,
)

AGENT_CODE = "new_release_research_agent"
RESEARCH_TYPE = "new_releases"


def _agent_id(session: Session) -> int:
    row = session.exec(select(AgentDefinition).where(AgentDefinition.code == AGENT_CODE)).first()
    if row is None or row.id is None:
        raise RuntimeError("New release research agent is not registered.")
    return int(row.id)


def _is_issue_one(issue_number: str) -> bool:
    normalized = issue_number.strip().lstrip("0")
    return normalized == "1"


def run_new_release_research_agent(session: Session, *, current_user: User) -> ResearchSnapshotDetail:
    assert current_user.id is not None
    owner_user_id = int(current_user.id)
    agent_execution = start_execution(
        session,
        agent_id=_agent_id(session),
        triggered_by=str(owner_user_id),
        trigger_source="research_agent:new_releases",
    )
    snapshot_id: int | None = None
    try:
        arrival_response, _ = compute_order_arrival_intelligence(session, current_user=current_user)
        snapshot = create_snapshot(
            session,
            agent_execution_id=agent_execution.execution.id,
            agent_code=AGENT_CODE,
            research_type=RESEARCH_TYPE,
            input_scope_json={
                "owner_user_id": owner_user_id,
                "arrival_item_count": arrival_response.total_count,
                "generated_as_of_date": arrival_response.generated_as_of_date,
            },
        )
        snapshot_id = snapshot.id
        finding_types: list[str] = []

        for item in arrival_response.items:
            evidence_payload = {
                "inventory_copy_id": item.inventory_copy_id,
                "classification": item.classification,
                "publisher": item.publisher,
                "title": item.title,
                "issue_number": item.issue_number,
                "order_status": item.order_status,
                "release_status": item.release_status,
                "purchase_date": item.purchase_date,
                "release_date": item.release_date,
                "expected_ship_date": item.expected_ship_date,
                "received_at": item.received_at,
                "evidence_json": item.evidence_json,
            }

            def _persist(
                *,
                finding_code: str,
                finding_type: str,
                title: str,
                description: str,
                confidence_score: float,
                priority_score: float,
                recommendation_json: dict,
            ) -> None:
                finding = add_finding(
                    session,
                    snapshot_id=snapshot_id,
                    finding_code=finding_code,
                    finding_type=finding_type,
                    title=title,
                    description=description,
                    confidence_score=confidence_score,
                    priority_score=priority_score,
                    recommendation_json=recommendation_json,
                )
                add_evidence(
                    session,
                    finding_id=finding.id,
                    evidence_type="order_arrival_intelligence",
                    source_name="order_arrival_intelligence",
                    source_payload_json=evidence_payload,
                    evidence_score=0.9,
                )
                finding_types.append(finding.finding_type)

            if item.classification == "upcoming_preorder":
                _persist(
                    finding_code=f"upcoming_release_to_watch|inventory_copy|{item.inventory_copy_id}",
                    finding_type="upcoming_release_to_watch",
                    title=f"{item.title} #{item.issue_number} is an upcoming preorder to watch",
                    description="The copy is marked as a preorder with a future release date in the existing order-arrival intelligence layer.",
                    confidence_score=0.95,
                    priority_score=0.88,
                    recommendation_json={
                        "candidate_action": "watch_upcoming_release",
                        "inventory_copy_id": item.inventory_copy_id,
                    },
                )
                if _is_issue_one(item.issue_number):
                    _persist(
                        finding_code=f"possible_spec_candidate|inventory_copy|{item.inventory_copy_id}",
                        finding_type="possible_spec_candidate",
                        title=f"{item.title} #{item.issue_number} may warrant speculative review",
                        description="Issue one preorders get elevated as spec-review candidates inside this read-only release research pass.",
                        confidence_score=0.81,
                        priority_score=0.77,
                        recommendation_json={
                            "candidate_action": "review_spec_interest",
                            "inventory_copy_id": item.inventory_copy_id,
                        },
                    )

            if item.classification == "releases_this_week":
                _persist(
                    finding_code=f"release_this_week|inventory_copy|{item.inventory_copy_id}",
                    finding_type="release_this_week",
                    title=f"{item.title} #{item.issue_number} releases this week",
                    description="Existing release-date intelligence places this copy in the current release window.",
                    confidence_score=0.96,
                    priority_score=0.86,
                    recommendation_json={
                        "candidate_action": "review_this_week_release",
                        "inventory_copy_id": item.inventory_copy_id,
                    },
                )

            if item.classification in {"released_not_received", "overdue_expected_ship"}:
                _persist(
                    finding_code=f"overdue_expected_release|inventory_copy|{item.inventory_copy_id}|{item.classification}",
                    finding_type="overdue_expected_release",
                    title=f"{item.title} #{item.issue_number} needs follow-up against expected release flow",
                    description="The item has crossed an expected release or ship threshold without the arrival state catching up.",
                    confidence_score=0.92,
                    priority_score=0.89,
                    recommendation_json={
                        "candidate_action": "review_release_follow_up",
                        "inventory_copy_id": item.inventory_copy_id,
                        "classification": item.classification,
                    },
                )

            if item.classification in {"missing_release_date", "missing_expected_ship_date"}:
                _persist(
                    finding_code=f"missing_market_data|inventory_copy|{item.inventory_copy_id}|{item.classification}",
                    finding_type="missing_market_data",
                    title=f"{item.title} #{item.issue_number} is missing release schedule data",
                    description="The internal arrival intelligence layer flagged missing schedule data for this copy.",
                    confidence_score=0.93,
                    priority_score=0.82,
                    recommendation_json={
                        "candidate_action": "fill_release_schedule_data",
                        "inventory_copy_id": item.inventory_copy_id,
                        "classification": item.classification,
                    },
                )

        summary = {
            "owner_user_id": owner_user_id,
            "arrival_item_count": arrival_response.total_count,
            "finding_count": len(finding_types),
            "findings_by_type": dict(sorted(Counter(finding_types).items())),
            "generated_as_of_date": arrival_response.generated_as_of_date,
        }
        complete_snapshot(session, snapshot_id=snapshot_id, summary_json=summary)
        complete_execution(
            session,
            execution_id=agent_execution.execution.id,
            event_payload_json={
                "snapshot_id": snapshot_id,
                "research_type": RESEARCH_TYPE,
                "finding_count": len(finding_types),
            },
        )
        return get_snapshot_detail(session, snapshot_id=snapshot_id)
    except Exception as exc:
        if snapshot_id is not None:
            fail_snapshot(
                session,
                snapshot_id=snapshot_id,
                summary_json={"error": str(exc), "research_type": RESEARCH_TYPE},
            )
        fail_execution(
            session,
            execution_id=agent_execution.execution.id,
            event_payload_json={
                "snapshot_id": snapshot_id,
                "research_type": RESEARCH_TYPE,
                "error": str(exc),
            },
        )
        raise
