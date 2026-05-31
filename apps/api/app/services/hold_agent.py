from __future__ import annotations

from sqlmodel import Session, select

from app.models.dealer_copilot import DealerOpportunityScore
from app.schemas.dealer_copilot import DealerCopilotExecutionRead, DealerCopilotRunResponse, DealerRecommendationRead
from app.services.dealer_copilot_engine import create_recommendation_with_evidence, finish_execution, start_execution

AGENT_CODE = "hold_agent"


def run_hold_agent(session: Session, *, owner_user_id: int) -> DealerCopilotRunResponse:
    execution = start_execution(session, owner_user_id=owner_user_id, agent_code=AGENT_CODE)
    try:
        scores = session.exec(
            select(DealerOpportunityScore)
            .where(DealerOpportunityScore.owner_user_id == owner_user_id)
            .order_by(DealerOpportunityScore.opportunity_score.desc(), DealerOpportunityScore.calculated_at.desc(), DealerOpportunityScore.id.desc())
        ).all()
        created: list[DealerRecommendationRead] = []
        for score in scores[:10]:
            if not (0.35 <= score.opportunity_score <= 0.65 and score.risk_score <= 0.55):
                continue
            created.append(
                create_recommendation_with_evidence(
                    session,
                    owner_user_id=owner_user_id,
                    execution_id=int(execution.id or 0),
                    recommendation_key=f"hold:{score.asset_type}:{score.asset_id}",
                    recommendation_type="HOLD",
                    asset_type=score.asset_type,
                    asset_id=score.asset_id,
                    title="Continue holding",
                    description=f"{score.asset_type} {score.asset_id} has balanced opportunity and risk, favoring patience over action.",
                    confidence_score=min((score.forecast_score + score.demand_score) / 2.0, 1.0),
                    priority_score=score.opportunity_score,
                    evidence=[
                        {
                            "evidence_type": "opportunity_score",
                            "evidence_source": "dealer_copilot_engine",
                            "evidence_payload_json": score.model_dump(mode="json"),
                            "evidence_score": score.opportunity_score,
                        },
                        {
                            "evidence_type": "risk_balance",
                            "evidence_source": "dealer_copilot_engine",
                            "evidence_payload_json": {"risk_score": score.risk_score, "forecast_score": score.forecast_score},
                            "evidence_score": max(0.0, 1.0 - abs(score.forecast_score - score.risk_score)),
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
