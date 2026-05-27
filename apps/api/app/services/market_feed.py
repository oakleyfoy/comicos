from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.models import (
    MarketIntelligenceFeedCursor,
    MarketIntelligenceFeedEvent,
    MarketIntelligenceFeedHistory,
    MarketIntelligenceFeedSnapshot,
)
from app.schemas.market_feed import (
    MarketIntelligenceFeedCursorRead,
    MarketIntelligenceFeedEventListResponse,
    MarketIntelligenceFeedEventRead,
    MarketIntelligenceFeedHistoryRead,
    MarketIntelligenceFeedReplayPayload,
    MarketIntelligenceFeedReplayResponse,
    MarketIntelligenceFeedSnapshotListResponse,
    MarketIntelligenceFeedSnapshotRead,
    MarketIntelligenceFeedTimelineItem,
    MarketIntelligenceFeedTimelineResponse,
)

FEED_EVENT_TYPES = {
    "INGESTION_BATCH_CREATED",
    "INGESTION_BATCH_COMPLETED",
    "NORMALIZATION_RUN_STARTED",
    "NORMALIZATION_RUN_COMPLETED",
    "SCORING_RUN_COMPLETED",
    "SIGNALS_GENERATED",
    "OPPORTUNITIES_GENERATED",
    "COUPLING_GENERATED",
    "SNAPSHOT_CREATED",
}

FEED_SEVERITIES = {"INFO", "WARNING", "CRITICAL"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _json_canonical(value: Any) -> str:
    return json.dumps(_json_safe(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_feed_checksum(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_json_canonical(payload).encode("utf-8")).hexdigest()


def _event_read(row: MarketIntelligenceFeedEvent) -> MarketIntelligenceFeedEventRead:
    return MarketIntelligenceFeedEventRead.model_validate(row, from_attributes=True)


def _snapshot_read(row: MarketIntelligenceFeedSnapshot) -> MarketIntelligenceFeedSnapshotRead:
    return MarketIntelligenceFeedSnapshotRead.model_validate(row, from_attributes=True)


def _history_read(row: MarketIntelligenceFeedHistory) -> MarketIntelligenceFeedHistoryRead:
    return MarketIntelligenceFeedHistoryRead.model_validate(row, from_attributes=True)


def _cursor_read(row: MarketIntelligenceFeedCursor) -> MarketIntelligenceFeedCursorRead:
    return MarketIntelligenceFeedCursorRead.model_validate(row, from_attributes=True)


def _coerce_owner_filter(owner_user_id: int | None):
    if owner_user_id is None:
        return MarketIntelligenceFeedEvent.owner_user_id.is_(None)
    return MarketIntelligenceFeedEvent.owner_user_id == owner_user_id


def _next_event_sequence_id(session: Session, *, owner_user_id: int | None) -> int:
    stmt = select(func.max(MarketIntelligenceFeedEvent.event_sequence_id)).where(_coerce_owner_filter(owner_user_id))
    current = session.exec(stmt).one()
    return int(current or 0) + 1


def _existing_event(
    session: Session,
    *,
    owner_user_id: int | None,
    event_type: str,
    event_checksum: str,
    ingestion_batch_id: int | None,
    normalization_run_id: int | None,
    scoring_run_id: int | None,
    signal_snapshot_id: int | None,
    opportunity_snapshot_id: int | None,
    coupling_snapshot_id: int | None,
) -> MarketIntelligenceFeedEvent | None:
    stmt = select(MarketIntelligenceFeedEvent).where(
        _coerce_owner_filter(owner_user_id),
        MarketIntelligenceFeedEvent.event_type == event_type,
        MarketIntelligenceFeedEvent.event_checksum == event_checksum,
    )
    if ingestion_batch_id is None:
        stmt = stmt.where(MarketIntelligenceFeedEvent.ingestion_batch_id.is_(None))
    else:
        stmt = stmt.where(MarketIntelligenceFeedEvent.ingestion_batch_id == ingestion_batch_id)
    if normalization_run_id is None:
        stmt = stmt.where(MarketIntelligenceFeedEvent.normalization_run_id.is_(None))
    else:
        stmt = stmt.where(MarketIntelligenceFeedEvent.normalization_run_id == normalization_run_id)
    if scoring_run_id is None:
        stmt = stmt.where(MarketIntelligenceFeedEvent.scoring_run_id.is_(None))
    else:
        stmt = stmt.where(MarketIntelligenceFeedEvent.scoring_run_id == scoring_run_id)
    if signal_snapshot_id is None:
        stmt = stmt.where(MarketIntelligenceFeedEvent.signal_snapshot_id.is_(None))
    else:
        stmt = stmt.where(MarketIntelligenceFeedEvent.signal_snapshot_id == signal_snapshot_id)
    if opportunity_snapshot_id is None:
        stmt = stmt.where(MarketIntelligenceFeedEvent.opportunity_snapshot_id.is_(None))
    else:
        stmt = stmt.where(MarketIntelligenceFeedEvent.opportunity_snapshot_id == opportunity_snapshot_id)
    if coupling_snapshot_id is None:
        stmt = stmt.where(MarketIntelligenceFeedEvent.coupling_snapshot_id.is_(None))
    else:
        stmt = stmt.where(MarketIntelligenceFeedEvent.coupling_snapshot_id == coupling_snapshot_id)
    stmt = stmt.order_by(col(MarketIntelligenceFeedEvent.event_sequence_id).desc(), col(MarketIntelligenceFeedEvent.id).desc())
    return session.exec(stmt).first()


def append_market_feed_event(
    session: Session,
    *,
    owner_user_id: int | None,
    event_type: str,
    severity: str,
    snapshot_date: date,
    event_payload_json: dict[str, Any],
    ingestion_batch_id: int | None = None,
    normalization_run_id: int | None = None,
    scoring_run_id: int | None = None,
    signal_snapshot_id: int | None = None,
    opportunity_snapshot_id: int | None = None,
    coupling_snapshot_id: int | None = None,
) -> MarketIntelligenceFeedEvent:
    if event_type not in FEED_EVENT_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid feed event type")
    if severity not in FEED_SEVERITIES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid feed severity")

    payload = _json_safe(event_payload_json)
    checksum = canonical_feed_checksum(
        {
            "owner_user_id": owner_user_id,
            "event_type": event_type,
            "severity": severity,
            "snapshot_date": snapshot_date,
            "ingestion_batch_id": ingestion_batch_id,
            "normalization_run_id": normalization_run_id,
            "scoring_run_id": scoring_run_id,
            "signal_snapshot_id": signal_snapshot_id,
            "opportunity_snapshot_id": opportunity_snapshot_id,
            "coupling_snapshot_id": coupling_snapshot_id,
            "event_payload_json": payload,
        }
    )

    existing = _existing_event(
        session,
        owner_user_id=owner_user_id,
        event_type=event_type,
        event_checksum=checksum,
        ingestion_batch_id=ingestion_batch_id,
        normalization_run_id=normalization_run_id,
        scoring_run_id=scoring_run_id,
        signal_snapshot_id=signal_snapshot_id,
        opportunity_snapshot_id=opportunity_snapshot_id,
        coupling_snapshot_id=coupling_snapshot_id,
    )
    if existing is not None:
        return existing

    event = MarketIntelligenceFeedEvent(
        owner_user_id=owner_user_id,
        event_type=event_type,
        severity=severity,
        event_sequence_id=_next_event_sequence_id(session, owner_user_id=owner_user_id),
        ingestion_batch_id=ingestion_batch_id,
        normalization_run_id=normalization_run_id,
        scoring_run_id=scoring_run_id,
        signal_snapshot_id=signal_snapshot_id,
        opportunity_snapshot_id=opportunity_snapshot_id,
        coupling_snapshot_id=coupling_snapshot_id,
        event_payload_json=payload,
        event_checksum=checksum,
        snapshot_date=snapshot_date,
        created_at=utc_now(),
    )
    session.add(event)
    session.flush()
    return event


def _event_scope_stmt(
    *,
    owner_user_id: int | None = None,
    event_type: str | None = None,
    severity: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    related_snapshot_id: int | None = None,
):
    stmt = select(MarketIntelligenceFeedEvent)
    if owner_user_id is not None:
        stmt = stmt.where(MarketIntelligenceFeedEvent.owner_user_id == owner_user_id)
    if event_type is not None:
        stmt = stmt.where(MarketIntelligenceFeedEvent.event_type == event_type)
    if severity is not None:
        stmt = stmt.where(MarketIntelligenceFeedEvent.severity == severity)
    if snapshot_date_from is not None:
        stmt = stmt.where(MarketIntelligenceFeedEvent.snapshot_date >= snapshot_date_from)
    if snapshot_date_to is not None:
        stmt = stmt.where(MarketIntelligenceFeedEvent.snapshot_date <= snapshot_date_to)
    if related_snapshot_id is not None:
        stmt = stmt.where(
            (
                (MarketIntelligenceFeedEvent.signal_snapshot_id == related_snapshot_id)
                | (MarketIntelligenceFeedEvent.opportunity_snapshot_id == related_snapshot_id)
                | (MarketIntelligenceFeedEvent.coupling_snapshot_id == related_snapshot_id)
                | (MarketIntelligenceFeedEvent.ingestion_batch_id == related_snapshot_id)
                | (MarketIntelligenceFeedEvent.normalization_run_id == related_snapshot_id)
                | (MarketIntelligenceFeedEvent.scoring_run_id == related_snapshot_id)
            )
        )
    return stmt


def list_market_feed_events(
    session: Session,
    *,
    owner_user_id: int | None = None,
    event_type: str | None = None,
    severity: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    related_snapshot_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> MarketIntelligenceFeedEventListResponse:
    limit = min(max(limit, 1), 500)
    offset = max(offset, 0)
    base = _event_scope_stmt(
        owner_user_id=owner_user_id,
        event_type=event_type,
        severity=severity,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        related_snapshot_id=related_snapshot_id,
    )
    total = int(session.exec(select(func.count()).select_from(base.subquery())).one() or 0)
    rows = list(
        session.exec(
            base.order_by(
                col(MarketIntelligenceFeedEvent.event_sequence_id).asc(),
                col(MarketIntelligenceFeedEvent.id).asc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()
    )
    return MarketIntelligenceFeedEventListResponse(
        items=[_event_read(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def get_market_feed_event(
    session: Session,
    *,
    event_id: int,
    owner_user_id: int | None = None,
    allow_cross_owner_ops: bool = False,
) -> MarketIntelligenceFeedEventRead:
    row = session.get(MarketIntelligenceFeedEvent, event_id)
    if row is None:
        raise HTTPException(status_code=404, detail="market feed event not found")
    if owner_user_id is not None and row.owner_user_id != owner_user_id and not allow_cross_owner_ops:
        raise HTTPException(status_code=404, detail="market feed event not found")
    return _event_read(row)


def build_market_feed_timeline(
    session: Session,
    *,
    owner_user_id: int | None = None,
    event_type: str | None = None,
    severity: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    related_snapshot_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> MarketIntelligenceFeedTimelineResponse:
    limit = min(max(limit, 1), 500)
    offset = max(offset, 0)
    events = list_market_feed_events(
        session,
        owner_user_id=owner_user_id,
        event_type=event_type,
        severity=severity,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        related_snapshot_id=related_snapshot_id,
        limit=limit,
        offset=offset,
    )
    items = [
        MarketIntelligenceFeedTimelineItem(
            sequence_id=row.event_sequence_id,
            event_id=row.id,
            event_type=row.event_type,
            severity=row.severity,
            created_at=row.created_at,
            snapshot_date=row.snapshot_date,
            checksum=row.event_checksum,
        )
        for row in events.items
    ]
    return MarketIntelligenceFeedTimelineResponse(
        items=items,
        total_items=events.total_items,
        limit=events.limit,
        offset=events.offset,
    )


def list_market_feed_snapshots(
    session: Session,
    *,
    owner_user_id: int | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    limit: int = 100,
    offset: int = 0,
) -> MarketIntelligenceFeedSnapshotListResponse:
    limit = min(max(limit, 1), 500)
    offset = max(offset, 0)
    stmt = select(MarketIntelligenceFeedSnapshot)
    if owner_user_id is not None:
        stmt = stmt.where(MarketIntelligenceFeedSnapshot.owner_user_id == owner_user_id)
    if snapshot_date_from is not None:
        stmt = stmt.where(MarketIntelligenceFeedSnapshot.snapshot_date >= snapshot_date_from)
    if snapshot_date_to is not None:
        stmt = stmt.where(MarketIntelligenceFeedSnapshot.snapshot_date <= snapshot_date_to)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(
                col(MarketIntelligenceFeedSnapshot.snapshot_date).desc(),
                col(MarketIntelligenceFeedSnapshot.id).desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()
    )
    return MarketIntelligenceFeedSnapshotListResponse(
        items=[_snapshot_read(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def _aggregate_events(
    rows: list[MarketIntelligenceFeedEvent],
    *,
    owner_user_id: int | None,
    snapshot_date: date,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], str]:
    type_counts = Counter(row.event_type for row in rows)
    severity_counts = Counter(row.severity for row in rows)
    latest_by_type: dict[str, dict[str, Any]] = {}
    for row in rows:
        current = latest_by_type.get(row.event_type)
        candidate = {
            "event_id": row.id,
            "event_sequence_id": row.event_sequence_id,
            "event_checksum": row.event_checksum,
            "created_at": row.created_at,
            "snapshot_date": row.snapshot_date,
            "severity": row.severity,
        }
        if current is None or int(candidate["event_sequence_id"]) > int(current["event_sequence_id"]):
            latest_by_type[row.event_type] = candidate

    timeline = [
        {
            "sequence_id": row.event_sequence_id,
            "event_id": row.id,
            "event_type": row.event_type,
            "severity": row.severity,
            "checksum": row.event_checksum,
            "created_at": row.created_at,
        }
        for row in rows
    ]

    heatmap = defaultdict(lambda: defaultdict(int))
    for row in rows:
        heatmap[row.snapshot_date.isoformat()][row.event_type] += 1

    failures = Counter(row.event_type for row in rows if row.severity in {"WARNING", "CRITICAL"})

    payload = {
        "owner_user_id": owner_user_id,
        "snapshot_date": snapshot_date,
        "total_events": len(rows),
        "latest_events_json": latest_by_type,
        "owner_timeline_json": timeline[:1000],
        "event_type_counts_json": dict(sorted(type_counts.items())),
        "severity_counts_json": dict(sorted(severity_counts.items())),
        "activity_heatmap_json": {day: dict(sorted(counts.items())) for day, counts in sorted(heatmap.items())},
        "failure_clustering_json": dict(sorted(failures.items())),
    }
    checksum = canonical_feed_checksum(payload)
    return (
        latest_by_type,
        dict(sorted(type_counts.items())),
        dict(sorted(severity_counts.items())),
        {day: dict(sorted(counts.items())) for day, counts in sorted(heatmap.items())},
        dict(sorted(failures.items())),
        checksum,
    )


def build_market_feed_snapshot(
    session: Session,
    *,
    owner_user_id: int | None = None,
    snapshot_date: date | None = None,
) -> MarketIntelligenceFeedSnapshotRead:
    snapshot_date = snapshot_date or utc_now().date()
    stmt = select(MarketIntelligenceFeedEvent)
    if owner_user_id is not None:
        stmt = stmt.where(MarketIntelligenceFeedEvent.owner_user_id == owner_user_id)
    rows = list(
        session.exec(
            stmt.order_by(
                col(MarketIntelligenceFeedEvent.event_sequence_id).asc(),
                col(MarketIntelligenceFeedEvent.id).asc(),
            )
        ).all()
    )
    latest = rows[-1] if rows else None
    latest_events_json, event_type_counts_json, severity_counts_json, activity_heatmap_json, failure_clustering_json, checksum = _aggregate_events(
        rows, owner_user_id=owner_user_id, snapshot_date=snapshot_date
    )

    snapshot = MarketIntelligenceFeedSnapshot(
        owner_user_id=owner_user_id,
        total_events=len(rows),
        latest_event_sequence_id=int(latest.event_sequence_id) if latest is not None else 0,
        latest_event_id=int(latest.id) if latest is not None and latest.id is not None else None,
        latest_events_json=_json_safe(latest_events_json),
        owner_timeline_json=_json_safe([
            {
                "sequence_id": row.event_sequence_id,
                "event_id": row.id,
                "event_type": row.event_type,
                "severity": row.severity,
                "checksum": row.event_checksum,
                "created_at": row.created_at,
            }
            for row in rows
        ]),
        event_type_counts_json=_json_safe(event_type_counts_json),
        severity_counts_json=_json_safe(severity_counts_json),
        activity_heatmap_json=_json_safe(activity_heatmap_json),
        failure_clustering_json=_json_safe(failure_clustering_json),
        snapshot_checksum=checksum,
        snapshot_date=snapshot_date,
        created_at=utc_now(),
    )
    session.add(snapshot)
    session.flush()
    return _snapshot_read(snapshot)


def build_market_feed_history(
    session: Session,
    *,
    snapshot: MarketIntelligenceFeedSnapshot,
) -> MarketIntelligenceFeedHistoryRead:
    history = MarketIntelligenceFeedHistory(
        owner_user_id=snapshot.owner_user_id,
        market_intelligence_feed_snapshot_id=int(snapshot.id or 0),
        total_events=snapshot.total_events,
        latest_event_sequence_id=snapshot.latest_event_sequence_id,
        latest_events_json=_json_safe(snapshot.latest_events_json),
        owner_timeline_json=_json_safe(snapshot.owner_timeline_json),
        event_type_counts_json=_json_safe(snapshot.event_type_counts_json),
        severity_counts_json=_json_safe(snapshot.severity_counts_json),
        snapshot_checksum=snapshot.snapshot_checksum,
        snapshot_date=snapshot.snapshot_date,
        created_at=utc_now(),
    )
    session.add(history)
    session.flush()
    return _history_read(history)


def record_feed_cursor(
    session: Session,
    *,
    owner_user_id: int | None,
    cursor_key: str,
    last_event_sequence_id: int,
    last_event_id: int | None,
    last_event_checksum: str | None,
    snapshot_date: date | None = None,
) -> MarketIntelligenceFeedCursorRead:
    snapshot_date = snapshot_date or utc_now().date()
    stmt = select(MarketIntelligenceFeedCursor).where(
        MarketIntelligenceFeedCursor.cursor_key == cursor_key,
    )
    if owner_user_id is None:
        stmt = stmt.where(MarketIntelligenceFeedCursor.owner_user_id.is_(None))
    else:
        stmt = stmt.where(MarketIntelligenceFeedCursor.owner_user_id == owner_user_id)
    row = session.exec(stmt).first()
    if row is None:
        row = MarketIntelligenceFeedCursor(
            owner_user_id=owner_user_id,
            cursor_key=cursor_key,
            last_event_sequence_id=last_event_sequence_id,
            last_event_id=last_event_id,
            last_event_checksum=last_event_checksum,
            snapshot_date=snapshot_date,
            created_at=utc_now(),
        )
        session.add(row)
    else:
        row.last_event_sequence_id = last_event_sequence_id
        row.last_event_id = last_event_id
        row.last_event_checksum = last_event_checksum
        row.snapshot_date = snapshot_date
        session.add(row)
    session.flush()
    return _cursor_read(row)


def replay_market_feed(
    session: Session,
    *,
    payload: MarketIntelligenceFeedReplayPayload,
) -> MarketIntelligenceFeedReplayResponse:
    owner_user_id = payload.owner_user_id
    snapshot_date = payload.snapshot_date or utc_now().date()
    rows = list(
        session.exec(
            select(MarketIntelligenceFeedEvent)
            .where(
                MarketIntelligenceFeedEvent.owner_user_id == owner_user_id
                if owner_user_id is not None
                else MarketIntelligenceFeedEvent.owner_user_id.is_(None)
            )
            .order_by(
                col(MarketIntelligenceFeedEvent.event_sequence_id).asc(),
                col(MarketIntelligenceFeedEvent.id).asc(),
            )
        ).all()
    )
    mismatches: list[int] = []
    expected_sequence = 1
    checksum_ok = True
    for row in rows:
        if int(row.event_sequence_id) != expected_sequence:
            mismatches.append(int(row.id or 0))
            checksum_ok = False
        recomputed = canonical_feed_checksum(
            {
                "owner_user_id": row.owner_user_id,
                "event_type": row.event_type,
                "severity": row.severity,
                "snapshot_date": row.snapshot_date,
                "ingestion_batch_id": row.ingestion_batch_id,
                "normalization_run_id": row.normalization_run_id,
                "scoring_run_id": row.scoring_run_id,
                "signal_snapshot_id": row.signal_snapshot_id,
                "opportunity_snapshot_id": row.opportunity_snapshot_id,
                "coupling_snapshot_id": row.coupling_snapshot_id,
                "event_payload_json": row.event_payload_json,
            }
        )
        if recomputed != row.event_checksum:
            mismatches.append(int(row.id or 0))
            checksum_ok = False
        expected_sequence += 1

    latest_events_json, event_type_counts_json, severity_counts_json, activity_heatmap_json, failure_clustering_json, checksum = _aggregate_events(
        rows, owner_user_id=owner_user_id, snapshot_date=snapshot_date
    )
    existing_snapshot = session.exec(
        select(MarketIntelligenceFeedSnapshot).where(
            MarketIntelligenceFeedSnapshot.owner_user_id == owner_user_id
            if owner_user_id is not None
            else MarketIntelligenceFeedSnapshot.owner_user_id.is_(None),
            MarketIntelligenceFeedSnapshot.snapshot_date == snapshot_date,
            MarketIntelligenceFeedSnapshot.snapshot_checksum == checksum,
        )
    ).first()
    if existing_snapshot is not None:
        existing_history = session.exec(
            select(MarketIntelligenceFeedHistory).where(
                MarketIntelligenceFeedHistory.market_intelligence_feed_snapshot_id == int(existing_snapshot.id or 0)
            )
        ).first()
        if existing_history is None:
            existing_history = MarketIntelligenceFeedHistory(
                owner_user_id=owner_user_id,
                market_intelligence_feed_snapshot_id=int(existing_snapshot.id or 0),
                total_events=existing_snapshot.total_events,
                latest_event_sequence_id=existing_snapshot.latest_event_sequence_id,
                latest_events_json=_json_safe(existing_snapshot.latest_events_json),
                owner_timeline_json=_json_safe(existing_snapshot.owner_timeline_json),
                event_type_counts_json=_json_safe(existing_snapshot.event_type_counts_json),
                severity_counts_json=_json_safe(existing_snapshot.severity_counts_json),
                snapshot_checksum=existing_snapshot.snapshot_checksum,
                snapshot_date=snapshot_date,
                created_at=utc_now(),
            )
            session.add(existing_history)
            session.flush()
        if payload.cursor_key:
            record_feed_cursor(
                session,
                owner_user_id=owner_user_id,
                cursor_key=payload.cursor_key,
                last_event_sequence_id=existing_snapshot.latest_event_sequence_id,
                last_event_id=existing_snapshot.latest_event_id,
                last_event_checksum=rows[-1].event_checksum if rows else None,
                snapshot_date=snapshot_date,
            )
        return MarketIntelligenceFeedReplayResponse(
            replayed=True,
            snapshot=_snapshot_read(existing_snapshot),
            history=_history_read(existing_history),
            total_events=len(rows),
            checksum_consistent=checksum_ok,
            checksum_mismatches=mismatches,
        )
    snapshot_row = MarketIntelligenceFeedSnapshot(
        owner_user_id=owner_user_id,
        total_events=len(rows),
        latest_event_sequence_id=rows[-1].event_sequence_id if rows else 0,
        latest_event_id=rows[-1].id if rows else None,
        latest_events_json=_json_safe(latest_events_json),
        owner_timeline_json=_json_safe([
            {
                "sequence_id": row.event_sequence_id,
                "event_id": row.id,
                "event_type": row.event_type,
                "severity": row.severity,
                "checksum": row.event_checksum,
                "created_at": row.created_at,
            }
            for row in rows
        ]),
        event_type_counts_json=_json_safe(event_type_counts_json),
        severity_counts_json=_json_safe(severity_counts_json),
        activity_heatmap_json=_json_safe(activity_heatmap_json),
        failure_clustering_json=_json_safe(failure_clustering_json),
        snapshot_checksum=checksum,
        snapshot_date=snapshot_date,
        created_at=utc_now(),
    )
    session.add(snapshot_row)
    session.flush()
    history_row = MarketIntelligenceFeedHistory(
        owner_user_id=owner_user_id,
        market_intelligence_feed_snapshot_id=int(snapshot_row.id or 0),
        total_events=len(rows),
        latest_event_sequence_id=snapshot_row.latest_event_sequence_id,
        latest_events_json=_json_safe(latest_events_json),
        owner_timeline_json=_json_safe(snapshot_row.owner_timeline_json),
        event_type_counts_json=_json_safe(event_type_counts_json),
        severity_counts_json=_json_safe(severity_counts_json),
        snapshot_checksum=snapshot_row.snapshot_checksum,
        snapshot_date=snapshot_date,
        created_at=utc_now(),
    )
    session.add(history_row)
    session.flush()
    if payload.cursor_key:
        record_feed_cursor(
            session,
            owner_user_id=owner_user_id,
            cursor_key=payload.cursor_key,
            last_event_sequence_id=snapshot_row.latest_event_sequence_id,
            last_event_id=snapshot_row.latest_event_id,
            last_event_checksum=rows[-1].event_checksum if rows else None,
            snapshot_date=snapshot_date,
        )
    return MarketIntelligenceFeedReplayResponse(
        replayed=True,
        snapshot=_snapshot_read(snapshot_row),
        history=_history_read(history_row),
        total_events=len(rows),
        checksum_consistent=checksum_ok,
        checksum_mismatches=mismatches,
    )
