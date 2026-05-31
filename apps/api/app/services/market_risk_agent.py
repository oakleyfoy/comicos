from __future__ import annotations

from collections import defaultdict

from sqlmodel import Session, select

from app.models.market_forecast import ForecastAgentExecution, MarketRiskAssessment, utc_now
from app.models.market_intelligence import MarketSignal, MarketSnapshot, MarketTrend
from app.schemas.market_forecast import ForecastAgentExecutionRead, MarketRiskAssessmentRead, MarketRiskRunResponse

AGENT_CODE = "market_risk_agent"


def _execution_read(row: ForecastAgentExecution) -> ForecastAgentExecutionRead:
    return ForecastAgentExecutionRead.model_validate(row)


def _risk_read(row: MarketRiskAssessment) -> MarketRiskAssessmentRead:
    return MarketRiskAssessmentRead.model_validate(row)


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


def detect_volatility_risk(session: Session, *, owner_user_id: int) -> list[MarketRiskAssessment]:
    signals = session.exec(
        select(MarketSignal)
        .where(MarketSignal.owner_user_id == owner_user_id)
        .where(MarketSignal.asset_id.is_not(None))
        .order_by(MarketSignal.observed_at.asc(), MarketSignal.id.asc())
    ).all()
    histories: dict[tuple[str, int], list[float]] = defaultdict(list)
    for signal in signals:
        if signal.asset_id is None:
            continue
        histories[(signal.asset_type, int(signal.asset_id))].append(float(signal.signal_value))

    created: list[MarketRiskAssessment] = []
    for (asset_type, asset_id), values in histories.items():
        if len(values) < 2:
            continue
        risk_score = max(values) - min(values)
        if risk_score < 5:
            continue
        row = MarketRiskAssessment(
            owner_user_id=owner_user_id,
            asset_type=asset_type,
            asset_id=asset_id,
            risk_type="HIGH_VOLATILITY_RISK",
            risk_score=round(risk_score, 4),
            confidence_score=min(0.55 + len(values) * 0.05, 0.9),
            created_at=utc_now(),
        )
        session.add(row)
        created.append(row)
    session.flush()
    return created


def detect_decline_risk(session: Session, *, owner_user_id: int) -> list[MarketRiskAssessment]:
    trends = session.exec(
        select(MarketTrend)
        .where(MarketTrend.owner_user_id == owner_user_id)
        .where(MarketTrend.trend_direction == "DOWN")
        .order_by(MarketTrend.trend_strength.desc(), MarketTrend.id.desc())
    ).all()
    created: list[MarketRiskAssessment] = []
    for trend in trends[:10]:
        row = MarketRiskAssessment(
            owner_user_id=owner_user_id,
            asset_type=trend.asset_type,
            asset_id=trend.asset_id,
            risk_type="RAPID_PRICE_DECLINE_RISK",
            risk_score=round(float(trend.trend_strength), 4),
            confidence_score=min(max(float(trend.confidence_score), 0.45), 0.95),
            created_at=utc_now(),
        )
        session.add(row)
        created.append(row)
    session.flush()
    return created


def detect_liquidity_risk(session: Session, *, owner_user_id: int) -> list[MarketRiskAssessment]:
    snapshots = session.exec(
        select(MarketSnapshot)
        .where(MarketSnapshot.owner_user_id == owner_user_id)
        .order_by(MarketSnapshot.created_at.desc(), MarketSnapshot.id.desc())
    ).all()
    if not snapshots:
        return []
    latest = snapshots[0]
    if latest.bearish_signals <= latest.bullish_signals:
        return []
    row = MarketRiskAssessment(
        owner_user_id=owner_user_id,
        asset_type="market",
        asset_id=None,
        risk_type="WEAK_DEMAND_RISK",
        risk_score=round(float(latest.bearish_signals - latest.bullish_signals), 4),
        confidence_score=0.75,
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return [row]


def detect_signal_instability(session: Session, *, owner_user_id: int) -> list[MarketRiskAssessment]:
    trends = session.exec(select(MarketTrend).where(MarketTrend.owner_user_id == owner_user_id)).all()
    by_asset: dict[tuple[str, int | None], set[str]] = defaultdict(set)
    for trend in trends:
        by_asset[(trend.asset_type, trend.asset_id)].add(trend.trend_direction)
    created: list[MarketRiskAssessment] = []
    for (asset_type, asset_id), directions in by_asset.items():
        if len(directions) < 2:
            continue
        row = MarketRiskAssessment(
            owner_user_id=owner_user_id,
            asset_type=asset_type,
            asset_id=asset_id,
            risk_type="SIGNAL_INSTABILITY_RISK",
            risk_score=round(float(len(directions)) / 3.0, 4),
            confidence_score=0.7,
            created_at=utc_now(),
        )
        session.add(row)
        created.append(row)
    session.flush()
    return created


def run_market_risk_agent(session: Session, *, owner_user_id: int) -> MarketRiskRunResponse:
    execution = _start_execution(session, owner_user_id=owner_user_id)
    try:
        risks = [
            *detect_volatility_risk(session, owner_user_id=owner_user_id),
            *detect_decline_risk(session, owner_user_id=owner_user_id),
            *detect_liquidity_risk(session, owner_user_id=owner_user_id),
            *detect_signal_instability(session, owner_user_id=owner_user_id),
        ]
        _finish_execution(session, execution=execution, status="COMPLETED")
        session.commit()
        return MarketRiskRunResponse(
            execution=_execution_read(execution),
            created_count=len(risks),
            risks=[_risk_read(row) for row in risks],
        )
    except Exception:
        _finish_execution(session, execution=execution, status="FAILED")
        session.commit()
        raise
