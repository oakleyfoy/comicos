from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from sqlmodel import Session, select

from app.models.asset_ledger import InventoryCopy
from app.models.market_forecast import (
    ForecastAgentExecution,
    MarketForecast,
    MarketForecastConfidence,
    MarketForecastPoint,
    utc_now,
)
from app.models.market_intelligence import MarketSignal, MarketTrend
from app.schemas.market_forecast import (
    ForecastAgentExecutionRead,
    MarketForecastRead,
    MarketForecastRunResponse,
)

AGENT_CODE = "price_forecast_agent"


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


def _confidence_band(score: float) -> str:
    if score >= 0.8:
        return "HIGH"
    if score >= 0.6:
        return "MEDIUM"
    return "LOW"


def _latest_trend_map(session: Session, *, owner_user_id: int) -> dict[tuple[str, int | None], MarketTrend]:
    rows = session.exec(
        select(MarketTrend)
        .where(MarketTrend.owner_user_id == owner_user_id)
        .order_by(MarketTrend.calculated_at.desc(), MarketTrend.id.desc())
    ).all()
    out: dict[tuple[str, int | None], MarketTrend] = {}
    for row in rows:
        key = (row.asset_type, row.asset_id)
        if key not in out:
            out[key] = row
    return out


def _asset_histories(session: Session, *, owner_user_id: int) -> dict[tuple[str, int], list[float]]:
    rows = session.exec(
        select(MarketSignal)
        .where(MarketSignal.owner_user_id == owner_user_id)
        .where(MarketSignal.asset_id.is_not(None))
        .order_by(MarketSignal.observed_at.asc(), MarketSignal.id.asc())
    ).all()
    histories: dict[tuple[str, int], list[float]] = defaultdict(list)
    for row in rows:
        if row.asset_id is None:
            continue
        histories[(row.asset_type, int(row.asset_id))].append(float(row.signal_value))
    return histories


def generate_asset_forecast(
    session: Session,
    *,
    owner_user_id: int,
    asset_type: str,
    asset_id: int,
    forecast_horizon_days: int,
) -> MarketForecast:
    histories = _asset_histories(session, owner_user_id=owner_user_id)
    history = histories.get((asset_type, asset_id), [])
    base_value = history[-1] if history else 0.0

    if asset_type == "inventory_copy":
        row = session.get(InventoryCopy, asset_id)
        if row is not None and row.current_fmv is not None:
            base_value = float(row.current_fmv)

    trend_map = _latest_trend_map(session, owner_user_id=owner_user_id)
    trend = trend_map.get((asset_type, asset_id)) or trend_map.get((asset_type, None))
    direction_multiplier = 0.0
    trend_strength = 0.0
    trend_confidence = 0.55
    if trend is not None:
        trend_strength = float(trend.trend_strength)
        trend_confidence = float(trend.confidence_score)
        if trend.trend_direction == "UP":
            direction_multiplier = 1.0
        elif trend.trend_direction == "DOWN":
            direction_multiplier = -1.0

    history_bias = 0.0
    if len(history) >= 2:
        midpoint = max(len(history) // 2, 1)
        earlier_avg = sum(history[:midpoint]) / len(history[:midpoint])
        later_avg = sum(history[midpoint:]) / len(history[midpoint:])
        history_bias = later_avg - earlier_avg

    horizon_scale = forecast_horizon_days / 30.0
    projected_delta = (trend_strength * direction_multiplier * 0.12 * max(base_value, 1.0) * horizon_scale) + (history_bias * 0.4)
    forecast_value = round(max(base_value + projected_delta, 0.0), 2)
    confidence_score = round(min(max((trend_confidence + min(len(history), 5) * 0.05), 0.35), 0.95), 4)

    forecast = MarketForecast(
        owner_user_id=owner_user_id,
        forecast_type=f"PRICE_FORECAST_{forecast_horizon_days}D",
        asset_type=asset_type,
        asset_id=asset_id,
        forecast_horizon_days=forecast_horizon_days,
        forecast_value=forecast_value,
        confidence_score=confidence_score,
        created_at=utc_now(),
    )
    session.add(forecast)
    session.flush()

    point_count = max(forecast_horizon_days // 30, 1)
    for step in range(1, point_count + 1):
        step_days = min(step * 30, forecast_horizon_days)
        point_projection = round(max(base_value + (projected_delta * (step_days / forecast_horizon_days)), 0.0), 2)
        session.add(
            MarketForecastPoint(
                forecast_id=int(forecast.id or 0),
                forecast_date=(utc_now() + timedelta(days=step_days)).date(),
                projected_value=point_projection,
                confidence_score=round(max(confidence_score - (step * 0.03), 0.25), 4),
                created_at=utc_now(),
            )
        )

    session.add(
        MarketForecastConfidence(
            forecast_id=int(forecast.id or 0),
            confidence_score=confidence_score,
            confidence_band=_confidence_band(confidence_score),
            explanation=(
                f"Derived from {len(history)} signal points and "
                f"{'asset-specific' if trend is not None and trend.asset_id is not None else 'market-level'} trend context."
            ),
            created_at=utc_now(),
        )
    )
    session.flush()
    return forecast


def _forecast_targets(session: Session, *, owner_user_id: int) -> list[tuple[str, int]]:
    signals = session.exec(
        select(MarketSignal)
        .where(MarketSignal.owner_user_id == owner_user_id)
        .where(MarketSignal.asset_id.is_not(None))
        .order_by(MarketSignal.observed_at.desc(), MarketSignal.id.desc())
    ).all()
    seen: set[tuple[str, int]] = set()
    targets: list[tuple[str, int]] = []
    for row in signals:
        if row.asset_id is None:
            continue
        key = (row.asset_type, int(row.asset_id))
        if key in seen:
            continue
        seen.add(key)
        targets.append(key)
    return targets


def generate_30_day_forecast(session: Session, *, owner_user_id: int) -> list[MarketForecast]:
    return [
        generate_asset_forecast(
            session,
            owner_user_id=owner_user_id,
            asset_type=asset_type,
            asset_id=asset_id,
            forecast_horizon_days=30,
        )
        for asset_type, asset_id in _forecast_targets(session, owner_user_id=owner_user_id)
    ]


def generate_90_day_forecast(session: Session, *, owner_user_id: int) -> list[MarketForecast]:
    return [
        generate_asset_forecast(
            session,
            owner_user_id=owner_user_id,
            asset_type=asset_type,
            asset_id=asset_id,
            forecast_horizon_days=90,
        )
        for asset_type, asset_id in _forecast_targets(session, owner_user_id=owner_user_id)
    ]


def generate_180_day_forecast(session: Session, *, owner_user_id: int) -> list[MarketForecast]:
    return [
        generate_asset_forecast(
            session,
            owner_user_id=owner_user_id,
            asset_type=asset_type,
            asset_id=asset_id,
            forecast_horizon_days=180,
        )
        for asset_type, asset_id in _forecast_targets(session, owner_user_id=owner_user_id)
    ]


def run_price_forecast_agent(session: Session, *, owner_user_id: int) -> MarketForecastRunResponse:
    execution = _start_execution(session, owner_user_id=owner_user_id)
    try:
        forecasts = [
            *generate_30_day_forecast(session, owner_user_id=owner_user_id),
            *generate_90_day_forecast(session, owner_user_id=owner_user_id),
            *generate_180_day_forecast(session, owner_user_id=owner_user_id),
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
