from __future__ import annotations

from sqlmodel import Session, select

from app.models.dealer_copilot import DealerOpportunityScore
from app.models.market_intelligence import MarketObservation
from app.schemas.dealer_copilot import DealerCopilotExecutionRead, DealerCopilotRunResponse, DealerRecommendationRead
from app.services.dealer_copilot_engine import create_recommendation_with_evidence, finish_execution, start_execution

AGENT_CODE = "watchlist_agent"


def run_watchlist_agent(session: Session, *, owner_user_id: int) -> DealerCopilotRunResponse:
    execution = start_execution(session, owner_user_id=owner_user_id, agent_code=AGENT_CODE)
    try:
        scores = session.exec(
            select(DealerOpportunityScore)
            .where(DealerOpportunityScore.owner_user_id == owner_user_id)
            .order_by(DealerOpportunityScore.demand_score.desc(), DealerOpportunityScore.calculated_at.desc(), DealerOpportunityScore.id.desc())
        ).all()
        observations = session.exec(
            select(MarketObservation)
            .where(MarketObservation.owner_user_id == owner_user_id)
            .order_by(MarketObservation.created_at.desc(), MarketObservation.id.desc())
        ).all()
        created: list[DealerRecommendationRead] = []
        for score in scores[:10]:
            if score.opportunity_score > 0.65 or score.risk_score > 0.75:
                continue
            created.append(
                create_recommendation_with_evidence(
                    session,
                    owner_user_id=owner_user_id,
                    execution_id=int(execution.id or 0),
                    recommendation_key=f"watch:{score.asset_type}:{score.asset_id}",
                    recommendation_type="WATCH",
                    asset_type=score.asset_type,
                    asset_id=score.asset_id,
                    title="Monitor demand increase",
                    description=f"{score.asset_type} {score.asset_id} is worth watching as market activity develops.",
                    confidence_score=min((score.demand_score * 0.6) + (score.forecast_score * 0.4), 1.0),
                    priority_score=min((score.demand_score * 0.7) + ((1.0 - score.risk_score) * 0.3), 1.0),
                    evidence=[
                        {
                            "evidence_type": "opportunity_score",
                            "evidence_source": "dealer_copilot_engine",
                            "evidence_payload_json": score.model_dump(mode="json"),
                            "evidence_score": score.demand_score,
                        },
                        {
                            "evidence_type": "market_observations",
                            "evidence_source": "market_observation_agent",
                            "evidence_payload_json": {"observation_titles": [row.title for row in observations[:3]]},
                            "evidence_score": 0.6 if observations else 0.3,
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
