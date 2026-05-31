from __future__ import annotations

from sqlmodel import Session, select

from app.models.dealer_copilot import DealerOpportunityScore
from app.models.market_intelligence import MarketSignal
from app.schemas.dealer_copilot import DealerCopilotExecutionRead, DealerCopilotRunResponse, DealerRecommendationRead
from app.services.dealer_copilot_engine import create_recommendation_with_evidence, finish_execution, start_execution

AGENT_CODE = "grade_candidate_agent"


def run_grade_candidate_agent(session: Session, *, owner_user_id: int) -> DealerCopilotRunResponse:
    execution = start_execution(session, owner_user_id=owner_user_id, agent_code=AGENT_CODE)
    try:
        scores = session.exec(
            select(DealerOpportunityScore)
            .where(DealerOpportunityScore.owner_user_id == owner_user_id)
            .order_by(DealerOpportunityScore.grading_score.desc(), DealerOpportunityScore.calculated_at.desc(), DealerOpportunityScore.id.desc())
        ).all()
        created: list[DealerRecommendationRead] = []
        for score in scores[:10]:
            if score.grading_score is None or score.grading_score < 0.55:
                continue
            signals = session.exec(
                select(MarketSignal)
                .where(MarketSignal.owner_user_id == owner_user_id)
                .where(MarketSignal.asset_type == score.asset_type)
                .where(MarketSignal.asset_id == score.asset_id)
                .order_by(MarketSignal.observed_at.desc(), MarketSignal.id.desc())
            ).all()[:3]
            created.append(
                create_recommendation_with_evidence(
                    session,
                    owner_user_id=owner_user_id,
                    execution_id=int(execution.id or 0),
                    recommendation_key=f"grade:{score.asset_type}:{score.asset_id}",
                    recommendation_type="GRADE",
                    asset_type=score.asset_type,
                    asset_id=score.asset_id,
                    title="Strong grading candidate",
                    description=f"{score.asset_type} {score.asset_id} has enough forecast and demand strength to justify grading review.",
                    confidence_score=min(score.grading_score, 1.0),
                    priority_score=min((score.grading_score * 0.7) + (score.opportunity_score * 0.3), 1.0),
                    evidence=[
                        {
                            "evidence_type": "grading_score",
                            "evidence_source": "dealer_copilot_engine",
                            "evidence_payload_json": score.model_dump(mode="json"),
                            "evidence_score": score.grading_score,
                        },
                        {
                            "evidence_type": "market_signals",
                            "evidence_source": "market_signal_agent",
                            "evidence_payload_json": {"signal_types": [row.signal_type for row in signals]},
                            "evidence_score": score.demand_score,
                        },
                    ],
                )
            )
        finish_execution(session, execution=execution, status="COMPLETED")
        session.commit()
        return DealerCopilotRunResponse(recommendations=created, opportunities=[], executions=[DealerCopilotExecutionRead.model_validate(execution)])
    except Exception:
        finish_execution(session, execution=execution, status="FAILED")
        session.commit()
        raise
