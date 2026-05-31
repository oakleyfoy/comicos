from __future__ import annotations

from sqlmodel import Session, select

from app.models.market_intelligence import (
    MarketAgentExecution,
    MarketObservation,
    MarketSignal,
    MarketSnapshot,
    MarketTrend,
)
from app.schemas.market_intelligence import (
    MarketAgentExecutionListResponse,
    MarketAgentExecutionRead,
    MarketIntelligenceDashboardRead,
    MarketObservationListResponse,
    MarketObservationRead,
    MarketSignalListResponse,
    MarketSignalRead,
    MarketSnapshotListResponse,
    MarketSnapshotRead,
    MarketTrendListResponse,
    MarketTrendRead,
)


def _paginate(limit: int, offset: int) -> tuple[int, int]:
    clamped_limit = min(max(limit, 1), 200)
    clamped_offset = max(offset, 0)
    return clamped_limit, clamped_offset


def list_signals(session: Session, *, owner_user_id: int, limit: int = 50, offset: int = 0) -> MarketSignalListResponse:
    limit, offset = _paginate(limit, offset)
    rows = session.exec(
        select(MarketSignal)
        .where(MarketSignal.owner_user_id == owner_user_id)
        .order_by(MarketSignal.observed_at.desc(), MarketSignal.id.desc())
    ).all()
    items = [MarketSignalRead.model_validate(row) for row in rows[offset : offset + limit]]
    return MarketSignalListResponse(items=items, total_items=len(rows), limit=limit, offset=offset)


def list_snapshots(session: Session, *, owner_user_id: int, limit: int = 50, offset: int = 0) -> MarketSnapshotListResponse:
    limit, offset = _paginate(limit, offset)
    rows = session.exec(
        select(MarketSnapshot)
        .where(MarketSnapshot.owner_user_id == owner_user_id)
        .order_by(MarketSnapshot.created_at.desc(), MarketSnapshot.id.desc())
    ).all()
    items = [MarketSnapshotRead.model_validate(row) for row in rows[offset : offset + limit]]
    return MarketSnapshotListResponse(items=items, total_items=len(rows), limit=limit, offset=offset)


def list_trends(session: Session, *, owner_user_id: int, limit: int = 50, offset: int = 0) -> MarketTrendListResponse:
    limit, offset = _paginate(limit, offset)
    rows = session.exec(
        select(MarketTrend)
        .where(MarketTrend.owner_user_id == owner_user_id)
        .order_by(MarketTrend.calculated_at.desc(), MarketTrend.id.desc())
    ).all()
    items = [MarketTrendRead.model_validate(row) for row in rows[offset : offset + limit]]
    return MarketTrendListResponse(items=items, total_items=len(rows), limit=limit, offset=offset)


def list_observations(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> MarketObservationListResponse:
    limit, offset = _paginate(limit, offset)
    rows = session.exec(
        select(MarketObservation)
        .where(MarketObservation.owner_user_id == owner_user_id)
        .order_by(MarketObservation.created_at.desc(), MarketObservation.id.desc())
    ).all()
    items = [MarketObservationRead.model_validate(row) for row in rows[offset : offset + limit]]
    return MarketObservationListResponse(items=items, total_items=len(rows), limit=limit, offset=offset)


def list_executions(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> MarketAgentExecutionListResponse:
    limit, offset = _paginate(limit, offset)
    rows = session.exec(
        select(MarketAgentExecution)
        .where(MarketAgentExecution.owner_user_id == owner_user_id)
        .order_by(MarketAgentExecution.created_at.desc(), MarketAgentExecution.id.desc())
    ).all()
    items = [MarketAgentExecutionRead.model_validate(row) for row in rows[offset : offset + limit]]
    return MarketAgentExecutionListResponse(items=items, total_items=len(rows), limit=limit, offset=offset)


def build_market_intelligence_dashboard(session: Session, *, owner_user_id: int) -> MarketIntelligenceDashboardRead:
    latest_snapshot = session.exec(
        select(MarketSnapshot)
        .where(MarketSnapshot.owner_user_id == owner_user_id)
        .order_by(MarketSnapshot.created_at.desc(), MarketSnapshot.id.desc())
    ).first()
    top_trends = session.exec(
        select(MarketTrend)
        .where(MarketTrend.owner_user_id == owner_user_id)
        .order_by(MarketTrend.calculated_at.desc(), MarketTrend.trend_strength.desc(), MarketTrend.id.desc())
    ).all()[:5]
    latest_observations = session.exec(
        select(MarketObservation)
        .where(MarketObservation.owner_user_id == owner_user_id)
        .order_by(MarketObservation.created_at.desc(), MarketObservation.id.desc())
    ).all()[:5]
    agent_activity = session.exec(
        select(MarketAgentExecution)
        .where(MarketAgentExecution.owner_user_id == owner_user_id)
        .order_by(MarketAgentExecution.created_at.desc(), MarketAgentExecution.id.desc())
    ).all()[:10]

    if latest_snapshot is None:
        return MarketIntelligenceDashboardRead(
            market_score=0.0,
            bullish_signals=0,
            bearish_signals=0,
            neutral_signals=0,
            top_trends=[MarketTrendRead.model_validate(row) for row in top_trends],
            latest_observations=[MarketObservationRead.model_validate(row) for row in latest_observations],
            agent_activity=[MarketAgentExecutionRead.model_validate(row) for row in agent_activity],
        )

    return MarketIntelligenceDashboardRead(
        market_score=float(latest_snapshot.market_score),
        bullish_signals=latest_snapshot.bullish_signals,
        bearish_signals=latest_snapshot.bearish_signals,
        neutral_signals=latest_snapshot.neutral_signals,
        top_trends=[MarketTrendRead.model_validate(row) for row in top_trends],
        latest_observations=[MarketObservationRead.model_validate(row) for row in latest_observations],
        agent_activity=[MarketAgentExecutionRead.model_validate(row) for row in agent_activity],
    )
