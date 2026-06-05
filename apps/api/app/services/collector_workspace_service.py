"""P65-01 Collector Workspace — action tasks from P61–P64 outputs (read-only upstream)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models.collector_assistant import (
    LANE_ACQUIRE,
    LANE_BUY,
    LANE_GRADE,
    LANE_HOLD,
    LANE_SELL,
    LANE_WATCH,
    RUN_STATUS_SUCCESS,
)
from app.models.collector_experience import (
    TASK_STATUS_DISMISSED,
    TASK_STATUS_NEW,
    TASK_TYPE_ACQUIRE,
    TASK_TYPE_BUY,
    TASK_TYPE_GRADE,
    TASK_TYPE_REVIEW,
    TASK_TYPE_SELL,
    TASK_TYPE_WATCH,
    CollectorTaskItem,
    CollectorTaskSnapshot,
    utc_now,
)
from app.services.collector_assistant_context_service import load_collector_assistant_context
from app.services.collector_assistant_orchestrator import get_latest_run, list_all_recommendations_for_run

_LANE_TO_TASK = {
    LANE_BUY: TASK_TYPE_BUY,
    LANE_SELL: TASK_TYPE_SELL,
    LANE_GRADE: TASK_TYPE_GRADE,
    LANE_ACQUIRE: TASK_TYPE_ACQUIRE,
    LANE_WATCH: TASK_TYPE_WATCH,
    LANE_HOLD: TASK_TYPE_REVIEW,
}

READINESS_NOT_READY = "NOT_READY"
READINESS_SUCCESS = "SUCCESS"


@dataclass
class _TaskDraft:
    task_type: str
    title: str
    publisher: str
    issue_number: str
    priority_score: float
    source_system: str
    source_ref_json: dict
    explanation: str
    action_hint: str


def _stable_key(task_type: str, source_system: str, source_ref_json: dict) -> str:
    payload = json.dumps({"t": task_type, "s": source_system, "r": source_ref_json}, sort_keys=True)
    return payload


def get_latest_task_snapshot(session: Session, *, owner_user_id: int) -> CollectorTaskSnapshot | None:
    return session.exec(
        select(CollectorTaskSnapshot)
        .where(CollectorTaskSnapshot.owner_user_id == owner_user_id)
        .order_by(CollectorTaskSnapshot.generated_at.desc(), CollectorTaskSnapshot.id.desc())
    ).first()


def list_task_items(
    session: Session,
    *,
    snapshot_id: int,
    task_type: str | None = None,
    limit: int = 200,
) -> list[CollectorTaskItem]:
    q = select(CollectorTaskItem).where(CollectorTaskItem.snapshot_id == snapshot_id)
    if task_type:
        q = q.where(CollectorTaskItem.task_type == task_type)
    q = q.order_by(CollectorTaskItem.priority_score.desc(), CollectorTaskItem.id.asc()).limit(limit)
    return list(session.exec(q).all())


def _prior_status_map(session: Session, *, owner_user_id: int) -> dict[str, tuple[str, list]]:
    prev = get_latest_task_snapshot(session, owner_user_id=owner_user_id)
    if prev is None:
        return {}
    out: dict[str, tuple[str, list]] = {}
    for row in list_task_items(session, snapshot_id=int(prev.id or 0), limit=500):
        key = _stable_key(row.task_type, row.source_system, row.source_ref_json or {})
        out[key] = (row.status, list(row.status_history_json or []))
    return out


def _build_drafts(session: Session, *, owner_user_id: int) -> tuple[list[_TaskDraft], dict, str]:
    ctx = load_collector_assistant_context(session, owner_user_id=owner_user_id)
    drafts: list[_TaskDraft] = []
    seen: set[str] = set()

    def add(d: _TaskDraft) -> None:
        key = _stable_key(d.task_type, d.source_system, d.source_ref_json)
        if key in seen:
            return
        seen.add(key)
        drafts.append(d)

    for row in ctx.buy_queue_items:
        add(
            _TaskDraft(
                task_type=TASK_TYPE_BUY,
                title=str(getattr(row, "title", "") or ""),
                publisher=str(getattr(row, "publisher", "") or ""),
                issue_number=str(getattr(row, "issue_number", "") or ""),
                priority_score=float(getattr(row, "priority_score", 0) or 0),
                source_system="BUY_QUEUE",
                source_ref_json={"buy_queue_item_id": int(getattr(row, "id", 0) or 0)},
                explanation=str(getattr(row, "explanation", "") or getattr(row, "reason", "") or "Buy Queue opportunity."),
                action_hint="REVIEW_BUY",
            )
        )

    for row in ctx.sell_items:
        add(
            _TaskDraft(
                task_type=TASK_TYPE_SELL,
                title=str(getattr(row, "title", "") or ""),
                publisher=str(getattr(row, "publisher", "") or ""),
                issue_number=str(getattr(row, "issue_number", "") or ""),
                priority_score=float(getattr(row, "sell_score", 0) or getattr(row, "priority_score", 0) or 0),
                source_system="SELL_SIGNAL",
                source_ref_json={"sell_signal_item_id": int(getattr(row, "id", 0) or 0)},
                explanation=str(getattr(row, "reason", "") or "Sell signal from market intelligence."),
                action_hint="REVIEW_SELL",
            )
        )

    for row in ctx.acquisition_items:
        add(
            _TaskDraft(
                task_type=TASK_TYPE_ACQUIRE,
                title=str(getattr(row, "title", "") or ""),
                publisher=str(getattr(row, "publisher", "") or ""),
                issue_number=str(getattr(row, "issue_number", "") or ""),
                priority_score=float(getattr(row, "priority_score", 0) or getattr(row, "score", 0) or 0),
                source_system="ACQUISITION",
                source_ref_json={"acquisition_item_id": int(getattr(row, "id", 0) or 0)},
                explanation=str(getattr(row, "reason", "") or "Acquisition opportunity."),
                action_hint="REVIEW_ACQUIRE",
            )
        )

    for row in ctx.foc_items:
        add(
            _TaskDraft(
                task_type=TASK_TYPE_BUY,
                title=str(getattr(row, "title", "") or getattr(row, "series_title", "") or "FOC alert"),
                publisher=str(getattr(row, "publisher", "") or ""),
                issue_number=str(getattr(row, "issue_number", "") or ""),
                priority_score=float(getattr(row, "urgency_score", 0) or 50),
                source_system="FOC_ALERT",
                source_ref_json={"foc_item_id": int(getattr(row, "id", 0) or 0)},
                explanation=str(getattr(row, "message", "") or "FOC deadline approaching."),
                action_hint="PREORDER",
            )
        )

    for row in ctx.watchlist_items:
        add(
            _TaskDraft(
                task_type=TASK_TYPE_WATCH,
                title=str(getattr(row, "title", "") or getattr(row, "series_name", "") or "Watchlist"),
                publisher=str(getattr(row, "publisher", "") or ""),
                issue_number=str(getattr(row, "issue_number", "") or ""),
                priority_score=40.0,
                source_system="WATCHLIST",
                source_ref_json={"watchlist_item_id": int(getattr(row, "id", 0) or 0)},
                explanation="On your watchlist.",
                action_hint="WATCH",
            )
        )

    run = get_latest_run(session, owner_user_id=owner_user_id)
    if run and run.status == RUN_STATUS_SUCCESS:
        lanes = list_all_recommendations_for_run(session, run_id=int(run.id or 0))
        for lane, items in lanes.items():
            task_type = _LANE_TO_TASK.get(lane, TASK_TYPE_REVIEW)
            for row in items[:40]:
                add(
                    _TaskDraft(
                        task_type=task_type,
                        title=row.title,
                        publisher=row.publisher,
                        issue_number=row.issue_number,
                        priority_score=float(row.priority_score),
                        source_system="COLLECTOR_ASSISTANT",
                        source_ref_json={
                            "collector_recommendation_item_id": int(row.id or 0),
                            "lane": lane,
                        },
                        explanation=row.explanation or "",
                        action_hint=row.recommended_action or "REVIEW",
                    )
                )

    fingerprint = {
        "ctx": ctx.fingerprint,
        "run_id": int(run.id or 0) if run else 0,
    }
    meta = {"freshness": ctx.freshness, "ready": ctx.ready}
    return drafts, fingerprint, ctx.fingerprint


def build_collector_tasks(session: Session, *, owner_user_id: int) -> CollectorTaskSnapshot:
    drafts, fingerprint, _fp = _build_drafts(session, owner_user_id=owner_user_id)
    status_map = _prior_status_map(session, owner_user_id=owner_user_id)
    snap = CollectorTaskSnapshot(
        owner_user_id=owner_user_id,
        total_items=len(drafts),
        source_fingerprint_json=fingerprint,
        metadata_json={"build": "P65-01"},
    )
    session.add(snap)
    session.flush()
    for d in sorted(drafts, key=lambda x: (-x.priority_score, x.title)):
        key = _stable_key(d.task_type, d.source_system, d.source_ref_json)
        status, history = status_map.get(key, (TASK_STATUS_NEW, []))
        if status == TASK_STATUS_DISMISSED:
            continue
        session.add(
            CollectorTaskItem(
                snapshot_id=int(snap.id or 0),
                owner_user_id=owner_user_id,
                task_type=d.task_type,
                status=status,
                title=d.title,
                publisher=d.publisher,
                issue_number=d.issue_number,
                priority_score=d.priority_score,
                source_system=d.source_system,
                source_ref_json=d.source_ref_json,
                explanation=d.explanation,
                action_hint=d.action_hint,
                status_history_json=history,
            )
        )
    session.commit()
    session.refresh(snap)
    return snap


def get_task_item(session: Session, *, owner_user_id: int, task_id: int) -> CollectorTaskItem | None:
    row = session.get(CollectorTaskItem, task_id)
    if row is None or row.owner_user_id != owner_user_id:
        return None
    return row


def update_task_status(
    session: Session,
    *,
    owner_user_id: int,
    task_id: int,
    status: str,
) -> CollectorTaskItem | None:
    row = get_task_item(session, owner_user_id=owner_user_id, task_id=task_id)
    if row is None:
        return None
    history = list(row.status_history_json or [])
    history.append({"from": row.status, "to": status, "at": datetime.now(timezone.utc).isoformat()})
    row.status = status
    row.status_history_json = history
    row.updated_at = utc_now()
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def bulk_update_task_status(
    session: Session,
    *,
    owner_user_id: int,
    task_ids: list[int],
    status: str,
) -> int:
    updated = 0
    for tid in task_ids:
        if update_task_status(session, owner_user_id=owner_user_id, task_id=tid, status=status):
            updated += 1
    return updated


def list_task_history(session: Session, *, owner_user_id: int, limit: int = 20) -> list[CollectorTaskSnapshot]:
    return list(
        session.exec(
            select(CollectorTaskSnapshot)
            .where(CollectorTaskSnapshot.owner_user_id == owner_user_id)
            .order_by(CollectorTaskSnapshot.generated_at.desc(), CollectorTaskSnapshot.id.desc())
            .limit(limit)
        ).all()
    )
