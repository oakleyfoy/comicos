from __future__ import annotations

from sqlmodel import Session, select

from app.models.dealer_copilot import DealerOpportunityScore
from app.models.market_forecast import MarketForecast, MarketRiskAssessment
from app.schemas.dealer_copilot import DealerCopilotExecutionRead, DealerCopilotRunResponse, DealerRecommendationRead
from app.services.dealer_copilot_engine import create_recommendation_with_evidence, finish_execution, start_execution

AGENT_CODE = "buy_list_agent"


def run_buy_list_agent(session: Session, *, owner_user_id: int) -> DealerCopilotRunResponse:
    execution = start_execution(session, owner_user_id=owner_user_id, agent_code=AGENT_CODE)
    try:
        scores = session.exec(
            select(DealerOpportunityScore)
            .where(DealerOpportunityScore.owner_user_id == owner_user_id)
            .order_by(DealerOpportunityScore.opportunity_score.desc(), DealerOpportunityScore.calculated_at.desc(), DealerOpportunityScore.id.desc())
        ).all()
        created: list[DealerRecommendationRead] = []
        for score in scores[:10]:
            if score.opportunity_score < 0.55 or score.risk_score > 0.45:
                continue
            forecasts = session.exec(
                select(MarketForecast)
                .where(MarketForecast.owner_user_id == owner_user_id)
                .where(MarketForecast.asset_type == score.asset_type)
                .where(MarketForecast.asset_id == score.asset_id)
                .order_by(MarketForecast.created_at.desc(), MarketForecast.id.desc())
            ).all()[:3]
            risks = session.exec(
                select(MarketRiskAssessment)
                .where(MarketRiskAssessment.owner_user_id == owner_user_id)
                .where(MarketRiskAssessment.asset_type == score.asset_type)
                .where(MarketRiskAssessment.asset_id == score.asset_id)
                .order_by(MarketRiskAssessment.created_at.desc(), MarketRiskAssessment.id.desc())
            ).all()[:2]
            created.append(
                create_recommendation_with_evidence(
                    session,
                    owner_user_id=owner_user_id,
                    execution_id=int(execution.id or 0),
                    recommendation_key=f"buy:{score.asset_type}:{score.asset_id}",
                    recommendation_type="BUY",
                    asset_type=score.asset_type,
                    asset_id=score.asset_id,
                    title="Acquire additional copies",
                    description=f"{score.asset_type} {score.asset_id} shows favorable opportunity and manageable forecasted risk.",
                    confidence_score=min((score.forecast_score * 0.6) + (score.demand_score * 0.4), 1.0),
                    priority_score=score.opportunity_score,
                    evidence=[
                        {
                            "evidence_type": "opportunity_score",
                            "evidence_source": "dealer_copilot_engine",
                            "evidence_payload_json": score.model_dump(mode="json"),
                            "evidence_score": score.opportunity_score,
                        },
                        {
                            "evidence_type": "forecast_context",
                            "evidence_source": "price_forecast_agent",
                            "evidence_payload_json": {"forecasts": [row.forecast_type for row in forecasts]},
                            "evidence_score": score.forecast_score,
                        },
                        {
                            "evidence_type": "risk_context",
                            "evidence_source": "market_risk_agent",
                            "evidence_payload_json": {"risk_types": [row.risk_type for row in risks]},
                            "evidence_score": max(0.0, 1.0 - score.risk_score),
                        },
                    ],
                )
            )
        finish_execution(session, execution=execution, status="COMPLETED")
        session.commit()
        return DealerCopilotRunResponse(
            recommendations=created,
            opportunities=[],
            executions=[DealerCopilotExecutionRead.model_validate(execution)],
        )
    except Exception:
        finish_execution(session, execution=execution, status="FAILED")
        session.commit()
        raise
