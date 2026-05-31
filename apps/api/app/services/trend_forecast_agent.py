from __future__ import annotations

from datetime import timedelta

from sqlmodel import Session, select

from app.models.market_forecast import (
    ForecastAgentExecution,
    MarketForecast,
    MarketForecastConfidence,
    MarketForecastPoint,
    utc_now,
)
from app.models.market_intelligence import MarketTrend
from app.schemas.market_forecast import ForecastAgentExecutionRead, MarketForecastRead, MarketForecastRunResponse

AGENT_CODE = "trend_forecast_agent"


def _execution_read(row: ForecastAgentExecution) -> ForecastAgentExecutionRead:
    return ForecastAgentExecutionRead.model_validate(row)


def _forecast_read(row: MarketForecast) -> MarketForecastRead:
    return MarketForecastRead.model_validate(row)


def _start_execution(session: Session, *, owner_user_id: int) -> ForecastAgentExecution:
    row = ForecastAgentExecution(
        owner_user_id=owner_user_id,
        agent_code=AGENT_CODE,
        status="RUNNING",
        started_at=utc_now(),
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return row


def _finish_execution(session: Session, *, execution: ForecastAgentExecution, status: str) -> None:
    completed_at = utc_now()
    execution.status = status
    execution.completed_at = completed_at
    execution.duration_ms = max(int((completed_at - execution.started_at).total_seconds() * 1000), 0)
    session.add(execution)
    session.flush()


def forecast_trend_direction(session: Session, *, owner_user_id: int) -> list[MarketForecast]:
    trends = session.exec(
        select(MarketTrend)
        .where(MarketTrend.owner_user_id == owner_user_id)
        .order_by(MarketTrend.calculated_at.desc(), MarketTrend.id.desc())
    ).all()
    created: list[MarketForecast] = []
    seen: set[tuple[str, int | None]] = set()
    for trend in trends:
        key = (trend.asset_type, trend.asset_id)
        if key in seen:
            continue
        seen.add(key)
        projected_value = 1.0 if trend.trend_direction == "UP" else -1.0 if trend.trend_direction == "DOWN" else 0.0
        direction_label = "BULLISH" if projected_value > 0 else "BEARISH" if projected_value < 0 else "NEUTRAL"
        forecast = MarketForecast(
            owner_user_id=owner_user_id,
            forecast_type=f"TREND_FORECAST_{direction_label}",
            asset_type=trend.asset_type,
            asset_id=trend.asset_id,
            forecast_horizon_days=30,
            forecast_value=projected_value,
            confidence_score=min(max(trend.confidence_score, 0.4), 0.95),
            created_at=utc_now(),
        )
        session.add(forecast)
        session.flush()
        session.add(
            MarketForecastPoint(
                forecast_id=int(forecast.id or 0),
                forecast_date=(utc_now() + timedelta(days=30)).date(),
                projected_value=projected_value,
                confidence_score=forecast.confidence_score,
                created_at=utc_now(),
            )
        )
        session.add(
            MarketForecastConfidence(
                forecast_id=int(forecast.id or 0),
                confidence_score=forecast.confidence_score,
                confidence_band="HIGH" if forecast.confidence_score >= 0.8 else "MEDIUM" if forecast.confidence_score >= 0.6 else "LOW",
                explanation=f"Based on latest {trend.trend_type.lower()} direction forecast from stored market trends.",
                created_at=utc_now(),
            )
        )
        created.append(forecast)
    session.flush()
    return created


def forecast_trend_strength(session: Session, *, owner_user_id: int) -> list[MarketForecast]:
    trends = session.exec(
        select(MarketTrend)
        .where(MarketTrend.owner_user_id == owner_user_id)
        .order_by(MarketTrend.calculated_at.desc(), MarketTrend.id.desc())
    ).all()
    created: list[MarketForecast] = []
    for trend in trends[:10]:
        forecast = MarketForecast(
            owner_user_id=owner_user_id,
            forecast_type="TREND_STRENGTH_FORECAST",
            asset_type=trend.asset_type,
            asset_id=trend.asset_id,
            forecast_horizon_days=30,
            forecast_value=round(float(trend.trend_strength), 4),
            confidence_score=min(max(trend.confidence_score, 0.4), 0.95),
            created_at=utc_now(),
        )
        session.add(forecast)
        session.flush()
        session.add(
            MarketForecastConfidence(
                forecast_id=int(forecast.id or 0),
                confidence_score=forecast.confidence_score,
                confidence_band="HIGH" if forecast.confidence_score >= 0.8 else "MEDIUM" if forecast.confidence_score >= 0.6 else "LOW",
                explanation="Strength forecast projects persistence of the current trend intensity.",
                created_at=utc_now(),
            )
        )
        created.append(forecast)
    session.flush()
    return created


def forecast_momentum(session: Session, *, owner_user_id: int) -> list[MarketForecast]:
    trends = session.exec(
        select(MarketTrend)
        .where(MarketTrend.owner_user_id == owner_user_id)
        .order_by(MarketTrend.calculated_at.desc(), MarketTrend.id.desc())
    ).all()
    created: list[MarketForecast] = []
    for trend in trends[:10]:
        sign = 1.0 if trend.trend_direction == "UP" else -1.0 if trend.trend_direction == "DOWN" else 0.0
        momentum = round(sign * float(trend.trend_strength) * float(trend.confidence_score), 4)
        forecast = MarketForecast(
            owner_user_id=owner_user_id,
            forecast_type="TREND_MOMENTUM_FORECAST",
            asset_type=trend.asset_type,
            asset_id=trend.asset_id,
            forecast_horizon_days=30,
            forecast_value=momentum,
            confidence_score=min(max(trend.confidence_score, 0.4), 0.95),
            created_at=utc_now(),
        )
        session.add(forecast)
        session.flush()
        session.add(
            MarketForecastConfidence(
                forecast_id=int(forecast.id or 0),
                confidence_score=forecast.confidence_score,
                confidence_band="HIGH" if forecast.confidence_score >= 0.8 else "MEDIUM" if forecast.confidence_score >= 0.6 else "LOW",
                explanation="Momentum forecast captures the directional persistence implied by current trend strength and confidence.",
                created_at=utc_now(),
            )
        )
        created.append(forecast)
    session.flush()
    return created


def run_trend_forecast_agent(session: Session, *, owner_user_id: int) -> MarketForecastRunResponse:
    execution = _start_execution(session, owner_user_id=owner_user_id)
    try:
        forecasts = [
            *forecast_trend_direction(session, owner_user_id=owner_user_id),
            *forecast_trend_strength(session, owner_user_id=owner_user_id),
            *forecast_momentum(session, owner_user_id=owner_user_id),
        ]
        _finish_execution(session, execution=execution, status="COMPLETED")
        session.commit()
        return MarketForecastRunResponse(
            execution=_execution_read(execution),
            created_count=len(forecasts),
            forecasts=[_forecast_read(row) for row in forecasts],
        )
    except Exception:
        _finish_execution(session, execution=execution, status="FAILED")
        session.commit()
        raise
