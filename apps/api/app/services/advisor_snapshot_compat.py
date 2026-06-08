"""Persist/load advisor snapshots when generation_status column is not migrated yet."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from functools import lru_cache
from typing import Any

from sqlalchemy import inspect as sa_inspect, text
from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.models.p90_collector_advisor_snapshot import P90CollectorAdvisorSnapshot, utc_now
from app.services.p90_safe_reads import is_missing_relation_error, p90_rollback_session

logger = logging.getLogger(__name__)

_GEN_STATUS_COLUMN_CACHE: dict[str, bool] = {}

_LEGACY_SNAPSHOT_FIELDS = (
    "owner_user_id",
    "snapshot_date",
    "buy_actions",
    "sell_actions",
    "grade_actions",
    "watch_actions",
    "todays_actions",
    "recent_activity",
    "market_alerts",
    "total_actions",
    "estimated_profit",
    "estimated_savings",
    "portfolio_score",
    "created_at",
)


@lru_cache(maxsize=16)
def _engine_cache_key(engine: Engine) -> str:
    return str(engine.url)


def advisor_snapshot_has_generation_status(session: Session) -> bool:
    engine = session.get_bind()
    key = _engine_cache_key(engine)
    if key not in _GEN_STATUS_COLUMN_CACHE:
        try:
            cols = {c["name"] for c in sa_inspect(engine).get_columns("p90_collector_advisor_snapshot")}
            _GEN_STATUS_COLUMN_CACHE[key] = "generation_status" in cols
        except Exception:  # noqa: BLE001
            _GEN_STATUS_COLUMN_CACHE[key] = False
    return _GEN_STATUS_COLUMN_CACHE[key]


def _json_param(value: Any) -> str:
    return json.dumps(value if value is not None else [])


def _row_from_mapping(data: dict[str, Any]) -> P90CollectorAdvisorSnapshot:
    return P90CollectorAdvisorSnapshot(
        id=int(data.get("id") or 0),
        owner_user_id=int(data["owner_user_id"]),
        snapshot_date=data["snapshot_date"],
        buy_actions=data.get("buy_actions") or [],
        sell_actions=data.get("sell_actions") or [],
        grade_actions=data.get("grade_actions") or [],
        watch_actions=data.get("watch_actions") or [],
        todays_actions=data.get("todays_actions") or [],
        recent_activity=data.get("recent_activity") or [],
        market_alerts=data.get("market_alerts") or [],
        total_actions=int(data.get("total_actions") or 0),
        estimated_profit=float(data.get("estimated_profit") or 0),
        estimated_savings=float(data.get("estimated_savings") or 0),
        portfolio_score=float(data.get("portfolio_score") or 0),
        generation_status=str(data.get("generation_status") or ""),
        created_at=data.get("created_at") or utc_now(),
    )


def find_advisor_snapshot_for_day(
    session: Session,
    *,
    owner_user_id: int,
    snapshot_date: date,
) -> P90CollectorAdvisorSnapshot | None:
    if advisor_snapshot_has_generation_status(session):
        from sqlmodel import select

        return session.exec(
            select(P90CollectorAdvisorSnapshot)
            .where(P90CollectorAdvisorSnapshot.owner_user_id == owner_user_id)
            .where(P90CollectorAdvisorSnapshot.snapshot_date == snapshot_date)
            .order_by(P90CollectorAdvisorSnapshot.id.desc())
            .limit(1)
        ).first()

    try:
        result = session.execute(
            text(
                """
                SELECT id, owner_user_id, snapshot_date, buy_actions, sell_actions, grade_actions,
                       watch_actions, todays_actions, recent_activity, market_alerts, total_actions,
                       estimated_profit, estimated_savings, portfolio_score, created_at
                FROM p90_collector_advisor_snapshot
                WHERE owner_user_id = :owner_user_id AND snapshot_date = :snapshot_date
                ORDER BY id DESC
                LIMIT 1
                """
            ),
            {"owner_user_id": owner_user_id, "snapshot_date": snapshot_date},
        )
        row = result.mappings().first()
    except Exception as exc:  # noqa: BLE001
        if is_missing_relation_error(exc):
            p90_rollback_session(session)
            return None
        raise
    if row is None:
        return None
    return _row_from_mapping(dict(row))


def latest_advisor_snapshot_row(session: Session, *, owner_user_id: int) -> P90CollectorAdvisorSnapshot | None:
    if advisor_snapshot_has_generation_status(session):
        from sqlmodel import select

        return session.exec(
            select(P90CollectorAdvisorSnapshot)
            .where(P90CollectorAdvisorSnapshot.owner_user_id == owner_user_id)
            .order_by(P90CollectorAdvisorSnapshot.snapshot_date.desc(), P90CollectorAdvisorSnapshot.id.desc())
            .limit(1)
        ).first()

    try:
        result = session.execute(
            text(
                """
                SELECT id, owner_user_id, snapshot_date, buy_actions, sell_actions, grade_actions,
                       watch_actions, todays_actions, recent_activity, market_alerts, total_actions,
                       estimated_profit, estimated_savings, portfolio_score, created_at
                FROM p90_collector_advisor_snapshot
                WHERE owner_user_id = :owner_user_id
                ORDER BY snapshot_date DESC, id DESC
                LIMIT 1
                """
            ),
            {"owner_user_id": owner_user_id},
        )
        row = result.mappings().first()
    except Exception as exc:  # noqa: BLE001
        if is_missing_relation_error(exc):
            p90_rollback_session(session)
            return None
        raise
    if row is None:
        return None
    return _row_from_mapping(dict(row))


def persist_advisor_snapshot(
    session: Session,
    *,
    owner_user_id: int,
    snapshot_date: date,
    existing: P90CollectorAdvisorSnapshot | None,
    buy_actions: list,
    sell_actions: list,
    grade_actions: list,
    watch_actions: list,
    todays_actions: list,
    recent_activity: list,
    market_alerts: list,
    total_actions: int,
    estimated_profit: float,
    estimated_savings: float,
    portfolio_score: float,
    generation_status: str,
    created_at: datetime | None = None,
) -> int:
    created = created_at or utc_now()
    if advisor_snapshot_has_generation_status(session):
        row = existing or P90CollectorAdvisorSnapshot(owner_user_id=owner_user_id, snapshot_date=snapshot_date)
        row.buy_actions = buy_actions
        row.sell_actions = sell_actions
        row.grade_actions = grade_actions
        row.watch_actions = watch_actions
        row.todays_actions = todays_actions
        row.recent_activity = recent_activity
        row.market_alerts = market_alerts
        row.total_actions = total_actions
        row.estimated_profit = estimated_profit
        row.estimated_savings = estimated_savings
        row.portfolio_score = portfolio_score
        row.generation_status = generation_status
        row.created_at = created
        session.add(row)
        session.flush()
        return int(row.id or 0)

    params = {
        "owner_user_id": owner_user_id,
        "snapshot_date": snapshot_date,
        "buy_actions": _json_param(buy_actions),
        "sell_actions": _json_param(sell_actions),
        "grade_actions": _json_param(grade_actions),
        "watch_actions": _json_param(watch_actions),
        "todays_actions": _json_param(todays_actions),
        "recent_activity": _json_param(recent_activity),
        "market_alerts": _json_param(market_alerts),
        "total_actions": total_actions,
        "estimated_profit": estimated_profit,
        "estimated_savings": estimated_savings,
        "portfolio_score": portfolio_score,
        "created_at": created,
    }
    try:
        if existing and existing.id:
            session.execute(
                text(
                    """
                    UPDATE p90_collector_advisor_snapshot SET
                      buy_actions = CAST(:buy_actions AS JSON),
                      sell_actions = CAST(:sell_actions AS JSON),
                      grade_actions = CAST(:grade_actions AS JSON),
                      watch_actions = CAST(:watch_actions AS JSON),
                      todays_actions = CAST(:todays_actions AS JSON),
                      recent_activity = CAST(:recent_activity AS JSON),
                      market_alerts = CAST(:market_alerts AS JSON),
                      total_actions = :total_actions,
                      estimated_profit = :estimated_profit,
                      estimated_savings = :estimated_savings,
                      portfolio_score = :portfolio_score,
                      created_at = :created_at
                    WHERE id = :id
                    """
                ),
                {**params, "id": int(existing.id)},
            )
            session.flush()
            return int(existing.id)
        insert_result = session.execute(
            text(
                """
                INSERT INTO p90_collector_advisor_snapshot (
                  owner_user_id, snapshot_date, buy_actions, sell_actions, grade_actions, watch_actions,
                  todays_actions, recent_activity, market_alerts, total_actions, estimated_profit,
                  estimated_savings, portfolio_score, created_at
                ) VALUES (
                  :owner_user_id, :snapshot_date,
                  CAST(:buy_actions AS JSON), CAST(:sell_actions AS JSON), CAST(:grade_actions AS JSON),
                  CAST(:watch_actions AS JSON), CAST(:todays_actions AS JSON), CAST(:recent_activity AS JSON),
                  CAST(:market_alerts AS JSON), :total_actions, :estimated_profit, :estimated_savings,
                  :portfolio_score, :created_at
                )
                RETURNING id
                """
            ),
            params,
        )
        new_id = int(insert_result.one()[0])
        session.flush()
        return new_id
    except Exception as exc:  # noqa: BLE001
        p90_rollback_session(session)
        logger.exception("legacy advisor snapshot persist failed owner=%s: %s", owner_user_id, exc)
        raise


def persist_empty_advisor_snapshot(
    session: Session,
    *,
    owner_user_id: int,
    snapshot_date: date,
    generation_status: str = "GATHER_FAILED",
) -> None:
    existing = find_advisor_snapshot_for_day(session, owner_user_id=owner_user_id, snapshot_date=snapshot_date)
    persist_advisor_snapshot(
        session,
        owner_user_id=owner_user_id,
        snapshot_date=snapshot_date,
        existing=existing,
        buy_actions=[],
        sell_actions=[],
        grade_actions=[],
        watch_actions=[],
        todays_actions=[],
        recent_activity=[],
        market_alerts=[],
        total_actions=0,
        estimated_profit=0.0,
        estimated_savings=0.0,
        portfolio_score=0.0,
        generation_status=generation_status if advisor_snapshot_has_generation_status(session) else "",
    )
