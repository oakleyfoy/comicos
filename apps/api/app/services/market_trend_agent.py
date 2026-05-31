from __future__ import annotations

from collections import defaultdict

from sqlmodel import Session, select

from app.models.market_intelligence import MarketAgentExecution, MarketSignal, MarketSnapshot, MarketTrend, utc_now
from app.schemas.market_intelligence import (
    MarketAgentExecutionRead,
    MarketTrendRead,
    MarketTrendRunResponse,
)

AGENT_CODE = "market_trend_agent"


def _execution_read(row: MarketAgentExecution) -> MarketAgentExecutionRead:
    return MarketAgentExecutionRead.model_validate(row)


def _trend_read(row: MarketTrend) -> MarketTrendRead:
    return MarketTrendRead.model_validate(row)


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


def _direction(delta: float) -> str:
    if delta > 0.01:
        return "UP"
    if delta < -0.01:
        return "DOWN"
    return "FLAT"


def calculate_asset_trends(session: Session, *, owner_user_id: int) -> list[MarketTrend]:
    signals = session.exec(select(MarketSignal).where(MarketSignal.owner_user_id == owner_user_id)).all()
    grouped: dict[tuple[str, int], list[MarketSignal]] = defaultdict(list)
    for row in signals:
        if row.asset_id is not None:
            grouped[(row.asset_type, int(row.asset_id))].append(row)

    created: list[MarketTrend] = []
    now = utc_now()
    for (asset_type, asset_id), rows in grouped.items():
        ordered = sorted(rows, key=lambda row: (row.observed_at, row.id or 0))
        if len(ordered) < 2:
            continue
        midpoint = max(len(ordered) // 2, 1)
        earlier = ordered[:midpoint]
        later = ordered[midpoint:]
        if not later:
            continue
        earlier_avg = sum(row.signal_value for row in earlier) / len(earlier)
        later_avg = sum(row.signal_value for row in later) / len(later)
        delta = later_avg - earlier_avg
        created.append(
            MarketTrend(
                owner_user_id=owner_user_id,
                trend_type="ASSET_SIGNAL_VALUE",
                asset_type=asset_type,
                asset_id=asset_id,
                trend_direction=_direction(delta),
                trend_strength=round(abs(delta), 4),
                confidence_score=min(0.6 + (len(ordered) * 0.05), 0.9),
                calculated_at=now,
                created_at=now,
            )
        )

    for row in created:
        session.add(row)
    session.flush()
    return created


def calculate_market_strength(session: Session, *, owner_user_id: int) -> dict[str, float | str | int]:
    snapshots = session.exec(
        select(MarketSnapshot).where(MarketSnapshot.owner_user_id == owner_user_id).order_by(MarketSnapshot.created_at.desc())
    ).all()
    latest = snapshots[0] if snapshots else None
    if latest is None:
        return {
            "market_score": 0.0,
            "trend_direction": "FLAT",
            "trend_strength": 0.0,
            "snapshot_count": 0,
        }
    previous = snapshots[1] if len(snapshots) > 1 else None
    delta = latest.market_score - previous.market_score if previous is not None else 0.0
    return {
        "market_score": float(latest.market_score),
        "trend_direction": _direction(float(delta)),
        "trend_strength": round(abs(float(delta)), 4),
        "snapshot_count": len(snapshots),
    }


def calculate_market_trends(session: Session, *, owner_user_id: int) -> MarketTrendRunResponse:
    execution = _start_execution(session, owner_user_id=owner_user_id)
    try:
        snapshots = session.exec(
            select(MarketSnapshot).where(MarketSnapshot.owner_user_id == owner_user_id).order_by(MarketSnapshot.created_at.desc())
        ).all()
        created: list[MarketTrend] = []
        now = utc_now()
        if len(snapshots) >= 2:
            latest = snapshots[0]
            previous = snapshots[1]
            delta = float(latest.market_score) - float(previous.market_score)
            market_trend = MarketTrend(
                owner_user_id=owner_user_id,
                trend_type="MARKET_SCORE",
                asset_type="market",
                asset_id=None,
                trend_direction=_direction(delta),
                trend_strength=round(abs(delta), 4),
                confidence_score=0.85,
                calculated_at=now,
                created_at=now,
            )
            session.add(market_trend)
            session.flush()
            created.append(market_trend)

        created.extend(calculate_asset_trends(session, owner_user_id=owner_user_id))
        _finish_execution(session, execution=execution, status="COMPLETED")
        session.commit()
        return MarketTrendRunResponse(
            execution=_execution_read(execution),
            created_count=len(created),
            trends=[_trend_read(row) for row in created],
        )
    except Exception:
        _finish_execution(session, execution=execution, status="FAILED")
        session.commit()
        raise
