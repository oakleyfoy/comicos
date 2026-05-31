from __future__ import annotations

from datetime import date, timedelta

from sqlmodel import Session, select

from app.models.market_intelligence import MarketAgentExecution, MarketSignal, MarketSnapshot, utc_now
from app.schemas.market_intelligence import (
    MarketAgentExecutionRead,
    MarketSnapshotRead,
    MarketSnapshotRunResponse,
)

AGENT_CODE = "market_snapshot_agent"


def _execution_read(row: MarketAgentExecution) -> MarketAgentExecutionRead:
    return MarketAgentExecutionRead.model_validate(row)


def _snapshot_read(row: MarketSnapshot) -> MarketSnapshotRead:
    return MarketSnapshotRead.model_validate(row)


def _start_execution(session: Session, *, owner_user_id: int) -> MarketAgentExecution:
    row = MarketAgentExecution(
        owner_user_id=owner_user_id,
        agent_code=AGENT_CODE,
        status="RUNNING",
        started_at=utc_now(),
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return row


def _finish_execution(session: Session, *, execution: MarketAgentExecution, status: str) -> None:
    completed_at = utc_now()
    execution.status = status
    execution.completed_at = completed_at
    execution.duration_ms = max(int((completed_at - execution.started_at).total_seconds() * 1000), 0)
    session.add(execution)
    session.flush()


def _signal_sentiment(row: MarketSignal) -> str:
    if row.signal_type in {"LISTING_PUBLISHABLE", "INVENTORY_HEALTHY"}:
        return "BULLISH"
    if row.signal_type in {"INVENTORY_CONSTRAINED"}:
        return "BEARISH"
    if row.signal_type == "MARKETPLACE_EXECUTION_HEALTH":
        if row.signal_value >= 0.9:
            return "BULLISH"
        if row.signal_value < 0.5:
            return "BEARISH"
        return "NEUTRAL"
    if row.signal_type == "FMV_SIGNAL":
        if row.signal_value >= 25:
            return "BULLISH"
        if row.signal_value < 10:
            return "BEARISH"
    return "NEUTRAL"


def generate_snapshot_metrics(
    session: Session,
    *,
    owner_user_id: int,
    date_from: date,
    date_to: date,
) -> dict[str, int | float]:
    signals = session.exec(select(MarketSignal).where(MarketSignal.owner_user_id == owner_user_id)).all()
    window_rows = [row for row in signals if date_from <= row.observed_at.date() <= date_to]
    bullish = sum(1 for row in window_rows if _signal_sentiment(row) == "BULLISH")
    bearish = sum(1 for row in window_rows if _signal_sentiment(row) == "BEARISH")
    neutral = sum(1 for row in window_rows if _signal_sentiment(row) == "NEUTRAL")
    market_score = max(min(50.0 + (bullish * 5.0) - (bearish * 5.0) + (neutral * 1.0), 100.0), 0.0)
    return {
        "market_score": round(market_score, 2),
        "bullish_signals": bullish,
        "bearish_signals": bearish,
        "neutral_signals": neutral,
    }


def generate_daily_snapshot(session: Session, *, owner_user_id: int, snapshot_date: date | None = None) -> MarketSnapshot:
    target_date = snapshot_date or utc_now().date()
    metrics = generate_snapshot_metrics(
        session,
        owner_user_id=owner_user_id,
        date_from=target_date,
        date_to=target_date,
    )
    row = MarketSnapshot(
        owner_user_id=owner_user_id,
        snapshot_date=target_date,
        market_score=float(metrics["market_score"]),
        bullish_signals=int(metrics["bullish_signals"]),
        bearish_signals=int(metrics["bearish_signals"]),
        neutral_signals=int(metrics["neutral_signals"]),
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return row


def generate_weekly_snapshot(session: Session, *, owner_user_id: int, ending_on: date | None = None) -> MarketSnapshot:
    target_date = ending_on or utc_now().date()
    start_date = target_date - timedelta(days=6)
    metrics = generate_snapshot_metrics(
        session,
        owner_user_id=owner_user_id,
        date_from=start_date,
        date_to=target_date,
    )
    row = MarketSnapshot(
        owner_user_id=owner_user_id,
        snapshot_date=target_date,
        market_score=float(metrics["market_score"]),
        bullish_signals=int(metrics["bullish_signals"]),
        bearish_signals=int(metrics["bearish_signals"]),
        neutral_signals=int(metrics["neutral_signals"]),
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return row


def run_snapshot_agent(session: Session, *, owner_user_id: int) -> MarketSnapshotRunResponse:
    execution = _start_execution(session, owner_user_id=owner_user_id)
    try:
        snapshot = generate_daily_snapshot(session, owner_user_id=owner_user_id)
        _finish_execution(session, execution=execution, status="COMPLETED")
        session.commit()
        return MarketSnapshotRunResponse(
            execution=_execution_read(execution),
            created_count=1,
            snapshots=[_snapshot_read(snapshot)],
        )
    except Exception:
        _finish_execution(session, execution=execution, status="FAILED")
        session.commit()
        raise
