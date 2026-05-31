from __future__ import annotations

from sqlmodel import Session, select

from app.models.market_intelligence import (
    MarketAgentExecution,
    MarketObservation,
    MarketSnapshot,
    MarketTrend,
    utc_now,
)
from app.schemas.market_intelligence import (
    MarketAgentExecutionRead,
    MarketObservationRead,
    MarketObservationRunResponse,
)

AGENT_CODE = "market_observation_agent"


def _execution_read(row: MarketAgentExecution) -> MarketAgentExecutionRead:
    return MarketAgentExecutionRead.model_validate(row)


def _observation_read(row: MarketObservation) -> MarketObservationRead:
    return MarketObservationRead.model_validate(row)


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


def generate_noteworthy_activity(session: Session, *, owner_user_id: int) -> list[MarketObservation]:
    trends = session.exec(
        select(MarketTrend)
        .where(MarketTrend.owner_user_id == owner_user_id)
        .order_by(MarketTrend.calculated_at.desc(), MarketTrend.trend_strength.desc(), MarketTrend.id.desc())
    ).all()
    created: list[MarketObservation] = []
    now = utc_now()
    for trend in trends:
        if trend.trend_direction != "UP":
            continue
        label = f"{trend.asset_type} {trend.asset_id}" if trend.asset_id is not None else trend.asset_type
        created.append(
            MarketObservation(
                owner_user_id=owner_user_id,
                observation_type="NOTABLE_ACTIVITY",
                title=f"{label} activity increasing",
                description=f"{label} is showing strengthening market activity with trend strength {trend.trend_strength:.2f}.",
                confidence_score=min(trend.confidence_score, 0.9),
                created_by_agent=AGENT_CODE,
                created_at=now,
            )
        )
        if len(created) >= 3:
            break
    for row in created:
        session.add(row)
    session.flush()
    return created


def generate_market_alerts(session: Session, *, owner_user_id: int) -> list[MarketObservation]:
    snapshots = session.exec(
        select(MarketSnapshot)
        .where(MarketSnapshot.owner_user_id == owner_user_id)
        .order_by(MarketSnapshot.created_at.desc(), MarketSnapshot.id.desc())
    ).all()
    created: list[MarketObservation] = []
    now = utc_now()
    if snapshots:
        latest = snapshots[0]
        if latest.bearish_signals > latest.bullish_signals:
            created.append(
                MarketObservation(
                    owner_user_id=owner_user_id,
                    observation_type="MARKET_ALERT",
                    title="Bearish market pressure increasing",
                    description=(
                        f"Latest market snapshot recorded {latest.bearish_signals} bearish signals "
                        f"against {latest.bullish_signals} bullish signals."
                    ),
                    confidence_score=0.82,
                    created_by_agent=AGENT_CODE,
                    created_at=now,
                )
            )
    for row in created:
        session.add(row)
    session.flush()
    return created


def generate_market_observations(session: Session, *, owner_user_id: int) -> MarketObservationRunResponse:
    execution = _start_execution(session, owner_user_id=owner_user_id)
    try:
        created = [
            *generate_noteworthy_activity(session, owner_user_id=owner_user_id),
            *generate_market_alerts(session, owner_user_id=owner_user_id),
        ]
        if not created:
            latest_snapshot = session.exec(
                select(MarketSnapshot)
                .where(MarketSnapshot.owner_user_id == owner_user_id)
                .order_by(MarketSnapshot.created_at.desc(), MarketSnapshot.id.desc())
            ).first()
            summary = MarketObservation(
                owner_user_id=owner_user_id,
                observation_type="MARKET_SUMMARY",
                title="Market activity stable",
                description=(
                    f"Latest market score is {latest_snapshot.market_score:.2f} with balanced signal activity."
                    if latest_snapshot is not None
                    else "No strong directional market activity is available yet."
                ),
                confidence_score=0.6,
                created_by_agent=AGENT_CODE,
                created_at=utc_now(),
            )
            session.add(summary)
            session.flush()
            created.append(summary)

        _finish_execution(session, execution=execution, status="COMPLETED")
        session.commit()
        return MarketObservationRunResponse(
            execution=_execution_read(execution),
            created_count=len(created),
            observations=[_observation_read(row) for row in created],
        )
    except Exception:
        _finish_execution(session, execution=execution, status="FAILED")
        session.commit()
        raise
