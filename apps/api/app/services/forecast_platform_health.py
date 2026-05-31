from __future__ import annotations

from collections import Counter

from sqlmodel import Session, select

from app.models.dealer_copilot import DealerCopilotExecution, DealerRecommendation
from app.models.forecast_validation import ForecastOutcome, ForecastValidationExecution
from app.models.market_forecast import ForecastAgentExecution, MarketForecast, MarketRiskAssessment
from app.models.market_intelligence import MarketAgentExecution, MarketSignal, MarketSnapshot
from app.schemas.forecast_platform import ForecastPlatformHealthComponentRead, ForecastPlatformHealthRead

HEALTH_STATUS_HEALTHY = "HEALTHY"
HEALTH_STATUS_WARNING = "WARNING"
HEALTH_STATUS_FAILED = "FAILED"
HEALTH_STATUS_DISABLED = "DISABLED"


def _aggregate_health(statuses: list[str]) -> str:
    if any(status == HEALTH_STATUS_FAILED for status in statuses):
        return HEALTH_STATUS_FAILED
    if any(status == HEALTH_STATUS_WARNING for status in statuses):
        return HEALTH_STATUS_WARNING
    if statuses and all(status == HEALTH_STATUS_DISABLED for status in statuses):
        return HEALTH_STATUS_DISABLED
    return HEALTH_STATUS_HEALTHY


def _component(
    *,
    component_code: str,
    title: str,
    health_status: str,
    summary: str,
    details_json: dict[str, object] | None = None,
) -> ForecastPlatformHealthComponentRead:
    return ForecastPlatformHealthComponentRead(
        component_code=component_code,
        title=title,
        health_status=health_status,
        summary=summary,
        details_json=details_json or {},
    )


def _execution_health(statuses: list[str]) -> str:
    if not statuses:
        return HEALTH_STATUS_WARNING
    if statuses and all(status == "FAILED" for status in statuses):
        return HEALTH_STATUS_FAILED
    if any(status == "FAILED" for status in statuses):
        return HEALTH_STATUS_WARNING
    if any(status == "RUNNING" for status in statuses):
        return HEALTH_STATUS_WARNING
    return HEALTH_STATUS_HEALTHY


def get_market_intelligence_health(session: Session, *, owner_user_id: int) -> ForecastPlatformHealthComponentRead:
    signals = session.exec(select(MarketSignal).where(MarketSignal.owner_user_id == owner_user_id)).all()
    snapshots = session.exec(select(MarketSnapshot).where(MarketSnapshot.owner_user_id == owner_user_id)).all()
    executions = session.exec(select(MarketAgentExecution).where(MarketAgentExecution.owner_user_id == owner_user_id)).all()
    status = _execution_health([row.status for row in executions])
    if not signals and not snapshots:
        status = HEALTH_STATUS_WARNING
    return _component(
        component_code="market_intelligence_health",
        title="Market Intelligence Health",
        health_status=status,
        summary=f"{len(signals)} signals, {len(snapshots)} snapshots, and {len(executions)} agent executions reviewed.",
        details_json={"execution_status_counts": dict(Counter(row.status for row in executions))},
    )


def get_forecast_generation_health(session: Session, *, owner_user_id: int) -> ForecastPlatformHealthComponentRead:
    forecasts = session.exec(select(MarketForecast).where(MarketForecast.owner_user_id == owner_user_id)).all()
    executions = session.exec(select(ForecastAgentExecution).where(ForecastAgentExecution.owner_user_id == owner_user_id)).all()
    status = _execution_health([row.status for row in executions if row.agent_code in {"price_forecast_agent", "trend_forecast_agent"}])
    if not forecasts:
        status = HEALTH_STATUS_WARNING
    return _component(
        component_code="forecast_generation_health",
        title="Forecast Generation Health",
        health_status=status,
        summary=f"{len(forecasts)} forecasts and {len(executions)} forecast executions reviewed.",
        details_json={"execution_status_counts": dict(Counter(row.status for row in executions))},
    )


def get_risk_assessment_health(session: Session, *, owner_user_id: int) -> ForecastPlatformHealthComponentRead:
    risks = session.exec(select(MarketRiskAssessment).where(MarketRiskAssessment.owner_user_id == owner_user_id)).all()
    executions = session.exec(
        select(ForecastAgentExecution)
        .where(ForecastAgentExecution.owner_user_id == owner_user_id)
        .where(ForecastAgentExecution.agent_code == "market_risk_agent")
    ).all()
    status = _execution_health([row.status for row in executions])
    if not risks:
        status = HEALTH_STATUS_WARNING
    return _component(
        component_code="risk_assessment_health",
        title="Risk Assessment Health",
        health_status=status,
        summary=f"{len(risks)} risk assessments and {len(executions)} risk executions reviewed.",
        details_json={"execution_status_counts": dict(Counter(row.status for row in executions))},
    )


def get_dealer_copilot_health(session: Session, *, owner_user_id: int) -> ForecastPlatformHealthComponentRead:
    recommendations = session.exec(select(DealerRecommendation).where(DealerRecommendation.owner_user_id == owner_user_id)).all()
    executions = session.exec(select(DealerCopilotExecution).where(DealerCopilotExecution.owner_user_id == owner_user_id)).all()
    status = _execution_health([row.status for row in executions])
    if not recommendations:
        status = HEALTH_STATUS_WARNING
    return _component(
        component_code="dealer_copilot_health",
        title="Dealer Copilot Health",
        health_status=status,
        summary=f"{len(recommendations)} recommendations and {len(executions)} dealer copilot executions reviewed.",
        details_json={"execution_status_counts": dict(Counter(row.status for row in executions))},
    )


def get_validation_learning_health(session: Session, *, owner_user_id: int) -> ForecastPlatformHealthComponentRead:
    outcomes = session.exec(select(ForecastOutcome).where(ForecastOutcome.owner_user_id == owner_user_id)).all()
    executions = session.exec(select(ForecastValidationExecution).where(ForecastValidationExecution.owner_user_id == owner_user_id)).all()
    status = _execution_health([row.status for row in executions])
    if not outcomes:
        status = HEALTH_STATUS_WARNING
    return _component(
        component_code="validation_learning_health",
        title="Validation and Learning Health",
        health_status=status,
        summary=f"{len(outcomes)} outcomes and {len(executions)} validation executions reviewed.",
        details_json={"execution_status_counts": dict(Counter(row.status for row in executions))},
    )


def get_agent_execution_health(session: Session, *, owner_user_id: int) -> ForecastPlatformHealthComponentRead:
    statuses = [
        *[row.status for row in session.exec(select(MarketAgentExecution).where(MarketAgentExecution.owner_user_id == owner_user_id)).all()],
        *[row.status for row in session.exec(select(ForecastAgentExecution).where(ForecastAgentExecution.owner_user_id == owner_user_id)).all()],
        *[row.status for row in session.exec(select(DealerCopilotExecution).where(DealerCopilotExecution.owner_user_id == owner_user_id)).all()],
        *[row.status for row in session.exec(select(ForecastValidationExecution).where(ForecastValidationExecution.owner_user_id == owner_user_id)).all()],
    ]
    status = _execution_health(statuses)
    if not statuses:
        status = HEALTH_STATUS_DISABLED
    return _component(
        component_code="agent_execution_health",
        title="Agent Execution Health",
        health_status=status,
        summary=f"{len(statuses)} total decision-intelligence executions reviewed.",
        details_json={"execution_status_counts": dict(Counter(statuses))},
    )


def get_forecast_platform_health(session: Session, *, owner_user_id: int) -> ForecastPlatformHealthRead:
    components = [
        get_market_intelligence_health(session, owner_user_id=owner_user_id),
        get_forecast_generation_health(session, owner_user_id=owner_user_id),
        get_risk_assessment_health(session, owner_user_id=owner_user_id),
        get_dealer_copilot_health(session, owner_user_id=owner_user_id),
        get_validation_learning_health(session, owner_user_id=owner_user_id),
        get_agent_execution_health(session, owner_user_id=owner_user_id),
    ]
    return ForecastPlatformHealthRead(
        overall_status=_aggregate_health([component.health_status for component in components]),
        components=components,
    )
