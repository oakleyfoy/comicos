from __future__ import annotations

from sqlmodel import Session, select

from app.models.dealer_copilot import DealerOpportunityScore
from app.models.market_forecast import MarketForecast, MarketRiskAssessment
from app.schemas.dealer_copilot import DealerCopilotExecutionRead, DealerCopilotRunResponse, DealerRecommendationRead
from app.services.dealer_copilot_engine import create_recommendation_with_evidence, finish_execution, start_execution

AGENT_CODE = "sell_agent"


def run_sell_agent(session: Session, *, owner_user_id: int) -> DealerCopilotRunResponse:
    execution = start_execution(session, owner_user_id=owner_user_id, agent_code=AGENT_CODE)
    try:
        scores = session.exec(
            select(DealerOpportunityScore)
            .where(DealerOpportunityScore.owner_user_id == owner_user_id)
            .order_by(DealerOpportunityScore.risk_score.desc(), DealerOpportunityScore.calculated_at.desc(), DealerOpportunityScore.id.desc())
        ).all()
        created: list[DealerRecommendationRead] = []
        for score in scores[:10]:
            forecasts = session.exec(
                select(MarketForecast)
                .where(MarketForecast.owner_user_id == owner_user_id)
                .where(MarketForecast.asset_type == score.asset_type)
                .where(MarketForecast.asset_id == score.asset_id)
                .order_by(MarketForecast.created_at.desc(), MarketForecast.id.desc())
            ).all()
            bearish = any("BEARISH" in row.forecast_type or row.forecast_value < 0 for row in forecasts)
            if not bearish and score.risk_score < 0.5:
                continue
            risks = session.exec(
                select(MarketRiskAssessment)
                .where(MarketRiskAssessment.owner_user_id == owner_user_id)
                .where(MarketRiskAssessment.asset_type == score.asset_type)
                .where(MarketRiskAssessment.asset_id == score.asset_id)
                .order_by(MarketRiskAssessment.created_at.desc(), MarketRiskAssessment.id.desc())
            ).all()[:3]
            created.append(
                create_recommendation_with_evidence(
                    session,
                    owner_user_id=owner_user_id,
                    execution_id=int(execution.id or 0),
                    recommendation_key=f"sell:{score.asset_type}:{score.asset_id}",
                    recommendation_type="SELL",
                    asset_type=score.asset_type,
                    asset_id=score.asset_id,
                    title="Sell before decline risk",
                    description=f"{score.asset_type} {score.asset_id} shows bearish forecast pressure or elevated downside risk.",
                    confidence_score=min(max(score.risk_score, 0.45), 1.0),
                    priority_score=min((score.risk_score * 0.7) + ((1.0 - score.forecast_score) * 0.3), 1.0),
                    evidence=[
                        {
                            "evidence_type": "forecast_context",
                            "evidence_source": "trend_forecast_agent",
                            "evidence_payload_json": {"forecast_types": [row.forecast_type for row in forecasts[:5]]},
                            "evidence_score": max(0.0, 1.0 - score.forecast_score),
                        },
                        {
                            "evidence_type": "risk_context",
                            "evidence_source": "market_risk_agent",
                            "evidence_payload_json": {"risk_types": [row.risk_type for row in risks]},
                            "evidence_score": score.risk_score,
                        },
                        {
                            "evidence_type": "opportunity_score",
                            "evidence_source": "dealer_copilot_engine",
                            "evidence_payload_json": score.model_dump(mode="json"),
                            "evidence_score": score.risk_score,
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
