from __future__ import annotations

from sqlmodel import Session, select

from app.models.market_forecast import (
    ForecastAgentExecution,
    MarketForecast,
    MarketForecastConfidence,
    MarketForecastPoint,
    MarketRiskAssessment,
)
from app.schemas.market_forecast import (
    ForecastAgentExecutionListResponse,
    ForecastAgentExecutionRead,
    ForecastDashboardRead,
    ForecastDashboardSummaryRead,
    MarketForecastConfidenceListResponse,
    MarketForecastConfidenceRead,
    MarketForecastDetail,
    MarketForecastListResponse,
    MarketForecastRead,
    MarketRiskAssessmentListResponse,
    MarketRiskAssessmentRead,
)


def _paginate(limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 200), max(offset, 0)


def _forecast_read(row: MarketForecast) -> MarketForecastRead:
    return MarketForecastRead.model_validate(row)


def _confidence_read(row: MarketForecastConfidence) -> MarketForecastConfidenceRead:
    return MarketForecastConfidenceRead.model_validate(row)


def _risk_read(row: MarketRiskAssessment) -> MarketRiskAssessmentRead:
    return MarketRiskAssessmentRead.model_validate(row)


def _execution_read(row: ForecastAgentExecution) -> ForecastAgentExecutionRead:
    return ForecastAgentExecutionRead.model_validate(row)


def list_forecasts(session: Session, *, owner_user_id: int, limit: int = 50, offset: int = 0) -> MarketForecastListResponse:
    limit, offset = _paginate(limit, offset)
    rows = session.exec(
        select(MarketForecast)
        .where(MarketForecast.owner_user_id == owner_user_id)
        .order_by(MarketForecast.created_at.desc(), MarketForecast.id.desc())
    ).all()
    items = [_forecast_read(row) for row in rows[offset : offset + limit]]
    return MarketForecastListResponse(items=items, total_items=len(rows), limit=limit, offset=offset)


def get_forecast_detail(session: Session, *, owner_user_id: int, forecast_id: int) -> MarketForecastDetail:
    forecast = session.get(MarketForecast, forecast_id)
    if forecast is None or forecast.owner_user_id != owner_user_id:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Market forecast not found.")
    points = session.exec(
        select(MarketForecastPoint)
        .where(MarketForecastPoint.forecast_id == forecast_id)
        .order_by(MarketForecastPoint.forecast_date.asc(), MarketForecastPoint.id.asc())
    ).all()
    confidence = session.exec(
        select(MarketForecastConfidence)
        .where(MarketForecastConfidence.forecast_id == forecast_id)
        .order_by(MarketForecastConfidence.created_at.desc(), MarketForecastConfidence.id.desc())
    ).first()
    from app.schemas.market_forecast import MarketForecastPointRead

    return MarketForecastDetail(
        forecast=_forecast_read(forecast),
        points=[MarketForecastPointRead.model_validate(row) for row in points],
        confidence=_confidence_read(confidence) if confidence is not None else None,
    )


def list_risks(session: Session, *, owner_user_id: int, limit: int = 50, offset: int = 0) -> MarketRiskAssessmentListResponse:
    limit, offset = _paginate(limit, offset)
    rows = session.exec(
        select(MarketRiskAssessment)
        .where(MarketRiskAssessment.owner_user_id == owner_user_id)
        .order_by(MarketRiskAssessment.created_at.desc(), MarketRiskAssessment.id.desc())
    ).all()
    items = [_risk_read(row) for row in rows[offset : offset + limit]]
    return MarketRiskAssessmentListResponse(items=items, total_items=len(rows), limit=limit, offset=offset)


def list_confidence(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> MarketForecastConfidenceListResponse:
    limit, offset = _paginate(limit, offset)
    forecasts = session.exec(select(MarketForecast.id).where(MarketForecast.owner_user_id == owner_user_id)).all()
    forecast_ids = [int(row) for row in forecasts]
    if not forecast_ids:
        return MarketForecastConfidenceListResponse(items=[], total_items=0, limit=limit, offset=offset)
    rows = session.exec(
        select(MarketForecastConfidence)
        .where(MarketForecastConfidence.forecast_id.in_(forecast_ids))  # type: ignore[attr-defined]
        .order_by(MarketForecastConfidence.created_at.desc(), MarketForecastConfidence.id.desc())
    ).all()
    items = [_confidence_read(row) for row in rows[offset : offset + limit]]
    return MarketForecastConfidenceListResponse(items=items, total_items=len(rows), limit=limit, offset=offset)


def list_executions(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> ForecastAgentExecutionListResponse:
    limit, offset = _paginate(limit, offset)
    rows = session.exec(
        select(ForecastAgentExecution)
        .where(ForecastAgentExecution.owner_user_id == owner_user_id)
        .order_by(ForecastAgentExecution.created_at.desc(), ForecastAgentExecution.id.desc())
    ).all()
    items = [_execution_read(row) for row in rows[offset : offset + limit]]
    return ForecastAgentExecutionListResponse(items=items, total_items=len(rows), limit=limit, offset=offset)


def list_top_bullish_forecasts(session: Session, *, owner_user_id: int, limit: int = 10) -> list[MarketForecastRead]:
    rows = session.exec(
        select(MarketForecast)
        .where(MarketForecast.owner_user_id == owner_user_id)
        .where(MarketForecast.forecast_type.contains("BULLISH"))
        .order_by(MarketForecast.confidence_score.desc(), MarketForecast.created_at.desc(), MarketForecast.id.desc())
    ).all()[:limit]
    return [_forecast_read(row) for row in rows]


def list_top_bearish_forecasts(session: Session, *, owner_user_id: int, limit: int = 10) -> list[MarketForecastRead]:
    rows = session.exec(
        select(MarketForecast)
        .where(MarketForecast.owner_user_id == owner_user_id)
        .where(MarketForecast.forecast_type.contains("BEARISH"))
        .order_by(MarketForecast.confidence_score.desc(), MarketForecast.created_at.desc(), MarketForecast.id.desc())
    ).all()[:limit]
    return [_forecast_read(row) for row in rows]


def list_highest_risk_assets(session: Session, *, owner_user_id: int, limit: int = 10) -> list[MarketRiskAssessmentRead]:
    rows = session.exec(
        select(MarketRiskAssessment)
        .where(MarketRiskAssessment.owner_user_id == owner_user_id)
        .order_by(MarketRiskAssessment.risk_score.desc(), MarketRiskAssessment.created_at.desc(), MarketRiskAssessment.id.desc())
    ).all()[:limit]
    return [_risk_read(row) for row in rows]


def build_forecast_summary(session: Session, *, owner_user_id: int) -> ForecastDashboardSummaryRead:
    forecasts = session.exec(select(MarketForecast).where(MarketForecast.owner_user_id == owner_user_id)).all()
    risks = session.exec(select(MarketRiskAssessment).where(MarketRiskAssessment.owner_user_id == owner_user_id)).all()
    avg_confidence = round(
        sum(float(row.confidence_score) for row in forecasts) / len(forecasts),
        4,
    ) if forecasts else 0.0
    bullish_count = sum(1 for row in forecasts if "BULLISH" in row.forecast_type)
    bearish_count = sum(1 for row in forecasts if "BEARISH" in row.forecast_type)
    return ForecastDashboardSummaryRead(
        total_forecasts=len(forecasts),
        average_confidence_score=avg_confidence,
        total_risk_assessments=len(risks),
        bullish_forecast_count=bullish_count,
        bearish_forecast_count=bearish_count,
    )


def build_forecast_dashboard(session: Session, *, owner_user_id: int) -> ForecastDashboardRead:
    confidence = list_confidence(session, owner_user_id=owner_user_id, limit=5, offset=0)
    executions = list_executions(session, owner_user_id=owner_user_id, limit=10, offset=0)
    return ForecastDashboardRead(
        summary=build_forecast_summary(session, owner_user_id=owner_user_id),
        forecast_confidence=confidence.items,
        top_bullish_forecasts=list_top_bullish_forecasts(session, owner_user_id=owner_user_id, limit=5),
        top_bearish_forecasts=list_top_bearish_forecasts(session, owner_user_id=owner_user_id, limit=5),
        highest_risk_assets=list_highest_risk_assets(session, owner_user_id=owner_user_id, limit=5),
        agent_activity=executions.items,
    )
