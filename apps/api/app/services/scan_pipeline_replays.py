"""Scan pipeline deterministic replay bookkeeping (pure reads + persisted diff rows).

Does not enqueue OCR jobs, persists no QA rows, persists no routing rows, deletes nothing.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import (
    CoverImage,
    HighResReviewRequest,
    QueueRoutingRecommendation,
    ScanPipelineReplayItem,
    ScanPipelineReplayRun,
    ScanQaResult,
    ScanSession,
    ScanSessionItem,
)
from app.models.asset_ledger import utc_now
from app.schemas.queue_routing import QueueRoutingRecommendationRead
from app.schemas.scan_pipeline_replays import (
    ScanPipelineReplayCreatePayload,
    ScanPipelineReplayItemRead,
    ScanPipelineReplayListRead,
    ScanPipelineReplayRunRead,
    ScanPipelineReplayRunSummaryRead,
)
from app.schemas.scan_qa import ScanQaItemRead
from app.services.queue_routing import _persisted_routing_rows_for_session, compute_pure_live_routing_reads
from app.services.scan_qa import compute_qa_items_for_scan_session
from app.services.scan_sessions import _sorted_items
from app.tasks.queue import cover_image_ocr_job_ui_status

REPLAY_ALGORITHM_VERSION = "scan-pipeline-replay-v1"
DEFAULT_SCOPE_SET = frozenset({"ingest", "qa", "routing", "ocr_visibility", "high_res_review"})
RUN_TERMINAL_STATUSES = frozenset({"completed", "completed_with_failures", "cancelled"})


def replay_item_to_read(row: ScanPipelineReplayItem) -> ScanPipelineReplayItemRead:
    if row.id is None:
        raise ValueError("flush replay item")
    cats = list(row.diff_categories_json or []) if isinstance(row.diff_categories_json, list) else []
    return ScanPipelineReplayItemRead(
        id=int(row.id),
        replay_run_id=int(row.replay_run_id),
        scan_session_item_id=int(row.scan_session_item_id),
        result_state=str(row.result_state),
        diff_categories=cats,
        baseline_snapshot_json=dict(row.baseline_snapshot_json or {}),
        replay_snapshot_json=dict(row.replay_snapshot_json or {}),
        diff_summary_json=dict(row.diff_summary_json or {}),
        last_error=row.last_error,
        created_at=row.created_at,
        updated_at=row.updated_at,
        completed_at=row.completed_at,
    )


def replay_run_to_read(session: Session, row: ScanPipelineReplayRun) -> ScanPipelineReplayRunRead:
    assert row.id is not None
    items = session.exec(
        select(ScanPipelineReplayItem)
        .where(ScanPipelineReplayItem.replay_run_id == row.id)
        .order_by(ScanPipelineReplayItem.scan_session_item_id.asc(), ScanPipelineReplayItem.id.asc())
    ).all()
    scopes_raw = row.scopes_json or []
    scopes_norm = scopes_raw if isinstance(scopes_raw, list) else list(scopes_raw)
    return ScanPipelineReplayRunRead(
        id=int(row.id),
        scan_session_id=int(row.scan_session_id),
        owner_user_id=int(row.owner_user_id),
        replay_version=str(row.replay_version),
        scopes_json=[str(s) for s in scopes_norm],
        cancellation_requested=bool(row.cancellation_requested),
        status=str(row.status),
        total_items=int(row.total_items),
        changed_items=int(row.changed_items),
        unchanged_items=int(row.unchanged_items),
        failed_items=int(row.failed_items),
        cancelled_items=int(row.cancelled_items),
        notes=row.notes,
        created_at=row.created_at,
        updated_at=row.updated_at,
        started_at=row.started_at,
        completed_at=row.completed_at,
        items=[replay_item_to_read(r) for r in items],
    )


def _validate_scopes(scopes: list[str]) -> list[str]:
    unknown = sorted(set(scopes) - DEFAULT_SCOPE_SET)
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unsupported scopes: {', '.join(unknown)}")
    return sorted(set(scopes))


def _assert_session_visible(session: Session, *, scan_session_id: int, owner_user_id: int | None) -> ScanSession:
    sess = session.get(ScanSession, scan_session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="Scan session not found")
    if owner_user_id is not None and sess.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Scan session not found")
    return sess


def _persisted_qa_map(session: Session, scan_session_id: int) -> dict[int, ScanQaResult]:
    rows = session.exec(select(ScanQaResult).where(ScanQaResult.scan_session_id == scan_session_id)).all()
    return {int(r.scan_session_item_id): r for r in rows}


def _persisted_routing_map(session: Session, scan_session_id: int) -> dict[int, QueueRoutingRecommendation]:
    mapped: dict[int, QueueRoutingRecommendation] = {}
    for row in _persisted_routing_rows_for_session(session, scan_session_id):
        if row.scan_session_item_id is not None:
            mapped[int(row.scan_session_item_id)] = row
    return mapped


def _ingest_slice(row: ScanSessionItem) -> dict[str, Any]:
    w = row.image_width
    h = row.image_height
    if w is None or h is None:
        dims: list[int | None] | None = [None, None]
    else:
        dims = sorted([int(w), int(h)])
    return {
        "ingest_status": row.ingest_status,
        "ingest_error_text": (row.ingest_error or "")[:2000],
        "image_dimensions": dims,
        "image_sha256_preview": (row.image_sha256 or "")[:24],
        "inventory_copy_id": row.inventory_copy_id,
        "cover_image_id": row.cover_image_id,
        "sequence_index": row.sequence_index,
    }


def _qa_live_slice(q: ScanQaItemRead | None) -> dict[str, Any]:
    if q is None:
        return {"present": False}
    return {
        "present": True,
        "qa_classification": q.qa_classification,
        "routing_recommendation": q.routing_recommendation,
        "severity": q.severity,
    }


def _qa_persist_slice(r: ScanQaResult | None) -> dict[str, Any]:
    if r is None:
        return {"persisted": False}
    return {
        "persisted": True,
        "qa_classification": r.qa_classification,
        "routing_recommendation": r.routing_recommendation,
        "severity": r.severity,
    }


def _routing_canonical(evidence: dict[str, Any], recommendation_type: str, priority: str) -> dict[str, Any]:
    reasons = evidence.get("reasons")
    if isinstance(reasons, list):
        normalized = tuple(sorted(str(x) for x in reasons))
    else:
        normalized = ()
    signals = evidence.get("signals")
    signals_norm: list[Any] = []
    if isinstance(signals, list):
        for sig in signals:
            if isinstance(sig, dict):
                signals_norm.append({k: sig.get(k) for k in sorted(sig.keys())})
    return {"recommendation_type": recommendation_type, "priority": priority, "reasons_sorted": list(normalized)}


def _routing_persist_slice(row: QueueRoutingRecommendation | None) -> dict[str, Any]:
    if row is None:
        return {"present": False}
    return {
        "present": True,
        **_routing_canonical(dict(row.evidence_json or {}), row.recommendation_type, row.priority),
        "routing_status": row.routing_status,
    }


def _routing_live_slice(ro: QueueRoutingRecommendationRead | None) -> dict[str, Any]:
    if ro is None:
        return {"present": False}
    return {
        "present": True,
        **_routing_canonical(dict(ro.evidence_json or {}), ro.recommendation_type, ro.priority),
        "routing_status": ro.routing_status,
    }


def _ocr_visibility_slice(session: Session, cover_image_id: int | None) -> dict[str, Any]:
    if cover_image_id is None:
        return {"cover_present": False, "job_ui_status": "n/a"}
    cov = session.get(CoverImage, cover_image_id)
    return {
        "cover_present": True,
        "cover_image_id": int(cover_image_id),
        "job_ui_status": cover_image_ocr_job_ui_status(int(cover_image_id)),
        "processing_status": cov.processing_status if cov else None,
        "matching_status": cov.matching_status if cov else None,
    }


def _high_res_slice(session: Session, *, scan_session_item_id: int) -> dict[str, Any]:
    stmt = (
        select(HighResReviewRequest.id, HighResReviewRequest.status, HighResReviewRequest.priority)
        .where(HighResReviewRequest.source_scan_session_item_id == scan_session_item_id)
        .order_by(HighResReviewRequest.id.asc())
    )
    rows = session.exec(stmt).all()
    payload = [(int(a), str(b), str(c)) for a, b, c in rows]
    return {"rows": sorted(payload, key=lambda r: r[0])}


def _compare_slices(
    baseline: dict[str, Any],
    replay: dict[str, Any],
) -> bool:
    return baseline != replay


def create_scan_pipeline_replay_run(
    session: Session,
    *,
    owner_user_id: int,
    payload: ScanPipelineReplayCreatePayload,
) -> ScanPipelineReplayRunRead:
    _assert_session_visible(session, scan_session_id=payload.scan_session_id, owner_user_id=owner_user_id)
    scopes = _validate_scopes([str(s) for s in payload.scopes])
    now = utc_now()
    row = ScanPipelineReplayRun(
        scan_session_id=payload.scan_session_id,
        owner_user_id=owner_user_id,
        replay_version=REPLAY_ALGORITHM_VERSION,
        scopes_json=scopes,
        cancellation_requested=False,
        status="pending",
        total_items=0,
        changed_items=0,
        unchanged_items=0,
        failed_items=0,
        cancelled_items=0,
        notes=payload.notes.strip() if payload.notes else None,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return replay_run_to_read(session, row)


def list_scan_pipeline_replay_runs_owner(
    session: Session,
    *,
    owner_user_id: int,
    scan_session_id: int | None,
    limit: int,
    offset: int,
) -> ScanPipelineReplayListRead:
    stmt = select(ScanPipelineReplayRun).where(ScanPipelineReplayRun.owner_user_id == owner_user_id)
    if scan_session_id is not None:
        stmt = stmt.where(ScanPipelineReplayRun.scan_session_id == scan_session_id)
    stmt = stmt.order_by(ScanPipelineReplayRun.created_at.desc(), ScanPipelineReplayRun.id.desc()).offset(offset).limit(limit)
    rows = session.exec(stmt).all()
    return ScanPipelineReplayListRead(items=[replay_run_to_read(session, row) for row in rows])


def list_scan_pipeline_replay_runs_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    scan_session_id: int | None,
    limit: int,
    offset: int,
) -> ScanPipelineReplayListRead:
    stmt = select(ScanPipelineReplayRun)
    if owner_user_id is not None:
        stmt = stmt.where(ScanPipelineReplayRun.owner_user_id == owner_user_id)
    if scan_session_id is not None:
        stmt = stmt.where(ScanPipelineReplayRun.scan_session_id == scan_session_id)
    stmt = stmt.order_by(
        ScanPipelineReplayRun.created_at.desc(),
        ScanPipelineReplayRun.id.desc(),
    ).offset(offset).limit(limit)
    rows = session.exec(stmt).all()
    return ScanPipelineReplayListRead(items=[replay_run_to_read(session, row) for row in rows])


def get_scan_pipeline_replay_run_for_owner(session: Session, *, owner_user_id: int | None, replay_id: int) -> ScanPipelineReplayRunRead:
    row = session.get(ScanPipelineReplayRun, replay_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Replay run not found")
    if owner_user_id is not None and row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Replay run not found")
    return replay_run_to_read(session, row)


def get_scan_pipeline_replay_run_ops(session: Session, *, replay_id: int) -> ScanPipelineReplayRunRead:
    return get_scan_pipeline_replay_run_for_owner(session, owner_user_id=None, replay_id=replay_id)


def cancel_scan_pipeline_replay_run(
    session: Session,
    *,
    owner_user_id: int | None,
    replay_id: int,
) -> ScanPipelineReplayRunRead:
    row = session.get(ScanPipelineReplayRun, replay_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Replay run not found")
    if owner_user_id is not None and row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Replay run not found")
    status = str(row.status)
    if status in RUN_TERMINAL_STATUSES:
        raise HTTPException(status_code=400, detail="Replay run already finalized")
    now = utc_now()
    row.cancellation_requested = True
    row.updated_at = now
    if status == "pending":
        row.status = "cancelled"
        row.completed_at = now
    session.add(row)
    session.commit()
    session.refresh(row)
    return replay_run_to_read(session, row)


def start_scan_pipeline_replay_run(
    session: Session,
    *,
    owner_user_id: int | None,
    replay_id: int,
) -> ScanPipelineReplayRunRead:
    run = session.get(ScanPipelineReplayRun, replay_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Replay run not found")
    if owner_user_id is not None and run.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Replay run not found")
    if str(run.status) != "pending":
        raise HTTPException(status_code=400, detail="Replay can only start while pending")
    replay_pk = int(run.id or 0)
    if replay_pk <= 0:
        raise HTTPException(status_code=500, detail="Replay run primary key unavailable")

    scan_session_id = int(run.scan_session_id)
    sess_row = session.get(ScanSession, scan_session_id)
    if sess_row is None:
        raise HTTPException(status_code=404, detail="Scan session missing for replay")

    scopes_map: dict[str, bool] = {}
    scopes_raw = run.scopes_json or []
    for name in scopes_raw:
        scopes_map[str(name)] = True

    qa_map_persist = _persisted_qa_map(session, scan_session_id)
    routing_map_persist = _persisted_routing_map(session, scan_session_id)

    live_qa: list[ScanQaItemRead] = compute_qa_items_for_scan_session(session, scan_session=sess_row)
    live_qa_dict = {r.scan_session_item_id: r for r in live_qa}

    live_routes = compute_pure_live_routing_reads(session, scan_session=sess_row, qa_rows=live_qa)
    routing_live_lookup: dict[int, QueueRoutingRecommendationRead] = {}
    for rr in live_routes:
        if rr.scan_session_item_id is None:
            continue
        routing_live_lookup[int(rr.scan_session_item_id)] = rr

    ordered_items = _sorted_items(
        session.exec(select(ScanSessionItem).where(ScanSessionItem.scan_session_id == scan_session_id)).all(),
    )

    item_ids_ordered = [int(r.id or 0) for r in ordered_items if r.id]

    changed = unchanged = failed = cancelled = 0
    stopped_by_cancel = False
    started = utc_now()
    run.status = "running"
    run.started_at = started
    run.total_items = len(item_ids_ordered)
    run.updated_at = started
    session.add(run)
    session.commit()

    for idx, item_id in enumerate(item_ids_ordered):
        ctl = session.get(ScanPipelineReplayRun, replay_pk)
        assert ctl is not None
        session.refresh(ctl)
        if bool(ctl.cancellation_requested):
            cancelled += append_cancel_stubs(session, ctl, item_ids_ordered[idx:])
            stopped_by_cancel = True
            break

        item_row_db = session.get(ScanSessionItem, item_id)
        if item_row_db is None:
            failed += 1
            _finalize_item_placeholder(
                session,
                replay_run_id=replay_pk,
                scan_session_item_id=item_id,
                state="failed",
                last_error="Scan session item row missing.",
            )
            _sync_run_counters(session, replay_pk, changed=changed, unchanged=unchanged, failed=failed, cancelled=cancelled)
            continue

        baseline: dict[str, Any] = {"scopes_requested": sorted(scopes_map.keys())}
        replay_sn: dict[str, Any] = {"scopes_requested": sorted(scopes_map.keys())}
        diffs: list[str] = []

        try:
            if scopes_map.get("ingest"):
                b = _ingest_slice(item_row_db)
                baseline["ingest"] = b
                session.refresh(item_row_db)
                r = _ingest_slice(item_row_db)
                replay_sn["ingest"] = r
                if _compare_slices(b, r):
                    diffs.append("ingest_state_changed")

            if scopes_map.get("qa"):
                qa_persist = qa_map_persist.get(item_id)
                baseline["qa_persisted"] = _qa_persist_slice(qa_persist)
                live_q_row = live_qa_dict.get(item_id)
                replay_sn["qa_live"] = _qa_live_slice(live_q_row)
                if _qa_persist_slice_for_compare(qa_persist, live_q_row):
                    diffs.append("qa_changed")

            if scopes_map.get("routing"):
                route_persist = routing_map_persist.get(item_id)
                baseline["routing_persisted"] = _routing_persist_slice(route_persist)
                live_rr = routing_live_lookup.get(item_id)
                replay_sn["routing_live"] = _routing_live_slice(live_rr)
                if _routing_logic_changed(route_persist, live_rr):
                    diffs.append("routing_changed")

            if scopes_map.get("ocr_visibility"):
                cid = item_row_db.cover_image_id
                cov_id = int(cid) if cid is not None else None
                baseline["ocr_visibility"] = _ocr_visibility_slice(session, cov_id)
                replay_sn["ocr_visibility"] = _ocr_visibility_slice(session, cov_id)
                if baseline["ocr_visibility"] != replay_sn["ocr_visibility"]:
                    diffs.append("OCR_visibility_changed")

            if scopes_map.get("high_res_review"):
                baseline["high_res_review"] = _high_res_slice(session, scan_session_item_id=item_id)
                replay_sn["high_res_review"] = _high_res_slice(session, scan_session_item_id=item_id)
                if baseline["high_res_review"] != replay_sn["high_res_review"]:
                    diffs.append("review_state_changed")

            deterministic_diffs = sorted(set(diffs))
            state = "changed" if deterministic_diffs else "unchanged"
            if deterministic_diffs:
                changed += 1
            else:
                unchanged += 1

            summary = {"diff_categories": deterministic_diffs, "scopes": sorted(scopes_map.keys())}
            completed_at = utc_now()
            replay_item_row = ScanPipelineReplayItem(
                replay_run_id=replay_pk,
                scan_session_item_id=item_id,
                result_state=state,
                baseline_snapshot_json=baseline,
                replay_snapshot_json=replay_sn,
                diff_categories_json=deterministic_diffs,
                diff_summary_json=summary,
                created_at=completed_at,
                updated_at=completed_at,
                completed_at=completed_at,
            )
            session.add(replay_item_row)

            run_ref = session.get(ScanPipelineReplayRun, replay_pk)
            assert run_ref is not None
            run_ref.changed_items = changed
            run_ref.unchanged_items = unchanged
            run_ref.failed_items = failed
            run_ref.cancelled_items = cancelled
            run_ref.updated_at = completed_at
            session.add(run_ref)
            session.commit()
        except Exception as exc:
            failed += 1
            err_txt = str(exc)[:1200]
            _finalize_item_placeholder(
                session,
                replay_run_id=replay_pk,
                scan_session_item_id=item_id,
                state="failed",
                last_error=err_txt,
                baseline=baseline if "baseline" in locals() else {},
                replay=replay_sn if "replay_sn" in locals() else {},
            )
            _sync_run_counters(session, replay_pk, changed=changed, unchanged=unchanged, failed=failed, cancelled=cancelled)

    run_final = session.get(ScanPipelineReplayRun, replay_pk)
    assert run_final is not None
    session.refresh(run_final)
    if str(run_final.status) == "running":
        terminal_now = utc_now()
        if stopped_by_cancel:
            run_final.status = "cancelled"
        elif failed > 0:
            run_final.status = "completed_with_failures"
        else:
            run_final.status = "completed"
        run_final.completed_at = terminal_now
        run_final.updated_at = terminal_now
        session.add(run_final)
        session.commit()

    final_read = session.get(ScanPipelineReplayRun, replay_pk)
    assert final_read is not None
    return replay_run_to_read(session, final_read)


def append_cancel_stubs(session: Session, run_row: ScanPipelineReplayRun, item_ids_tail: list[int]) -> int:
    if not item_ids_tail:
        return 0
    replay_pk = int(run_row.id or 0)
    rows = session.exec(select(ScanPipelineReplayItem).where(ScanPipelineReplayItem.replay_run_id == replay_pk)).all()
    existed = {int(r.scan_session_item_id) for r in rows if r.scan_session_item_id is not None}
    incremental = 0
    ts = utc_now()
    summary = {"cancelled": True, "note": "cooperative replay cancellation"}
    for cid in item_ids_tail:
        if int(cid) in existed:
            continue
        session.add(
            ScanPipelineReplayItem(
                replay_run_id=replay_pk,
                scan_session_item_id=int(cid),
                result_state="cancelled",
                baseline_snapshot_json={"reason": "cancelled_before_evaluation"},
                replay_snapshot_json={"reason": "cancelled_before_evaluation"},
                diff_categories_json=[],
                diff_summary_json=summary,
                created_at=ts,
                updated_at=ts,
                completed_at=ts,
            ),
        )
        incremental += 1
    refreshed = session.get(ScanPipelineReplayRun, replay_pk)
    if refreshed is None:
        return incremental
    refreshed.cancelled_items = int(refreshed.cancelled_items) + incremental
    refreshed.updated_at = ts
    session.add(refreshed)
    session.commit()
    return incremental


def _sync_run_counters(
    session: Session,
    replay_pk: int,
    *,
    changed: int,
    unchanged: int,
    failed: int,
    cancelled: int,
) -> None:
    run_ref = session.get(ScanPipelineReplayRun, replay_pk)
    assert run_ref is not None
    run_ref.changed_items = changed
    run_ref.unchanged_items = unchanged
    run_ref.failed_items = failed
    run_ref.cancelled_items = cancelled
    run_ref.updated_at = utc_now()
    session.add(run_ref)
    session.commit()


def _qa_persist_slice_for_compare(row: ScanQaResult | None, live_q: ScanQaItemRead | None) -> bool:
    bp = _qa_persist_slice(row)
    rq = _qa_live_slice(live_q)
    if bp.get("persisted") is False:
        persisted_equiv = {"present": False}
    else:
        persisted_equiv = {
            "present": True,
            "qa_classification": bp.get("qa_classification"),
            "routing_recommendation": bp.get("routing_recommendation"),
            "severity": bp.get("severity"),
        }
    return persisted_equiv != rq


def _routing_logic_changed(route_persist: QueueRoutingRecommendation | None, live_rr: QueueRoutingRecommendationRead | None) -> bool:
    persisted_norm = _routing_persist_slice(route_persist)
    live_norm = _routing_live_slice(live_rr)
    if persisted_norm["present"] is False:
        left = {"present": False}
    else:
        left = {
            "present": True,
            "recommendation_type": persisted_norm.get("recommendation_type"),
            "priority": persisted_norm.get("priority"),
            "reasons_sorted": persisted_norm.get("reasons_sorted", []),
        }
    right = (
        {"present": False}
        if live_norm["present"] is False
        else {
            "present": True,
            "recommendation_type": live_norm.get("recommendation_type"),
            "priority": live_norm.get("priority"),
            "reasons_sorted": live_norm.get("reasons_sorted", []),
        }
    )
    return left != right


def _finalize_item_placeholder(
    session: Session,
    *,
    replay_run_id: int,
    scan_session_item_id: int,
    state: str,
    last_error: str | None,
    baseline: dict[str, Any] | None = None,
    replay: dict[str, Any] | None = None,
) -> None:
    ts = utc_now()
    baseline = baseline or {}
    replay = replay or {}
    summary = {"error": True, "categories": [], "scopes": baseline.get("scopes_requested", [])}
    existing = session.exec(
        select(ScanPipelineReplayItem).where(
            ScanPipelineReplayItem.replay_run_id == replay_run_id,
            ScanPipelineReplayItem.scan_session_item_id == scan_session_item_id,
        )
    ).first()
    if existing:
        existing.result_state = state
        existing.baseline_snapshot_json = baseline or {}
        existing.replay_snapshot_json = replay or {}
        existing.diff_categories_json = []
        existing.diff_summary_json = summary
        existing.last_error = last_error
        existing.updated_at = ts
        existing.completed_at = ts
        session.add(existing)
        session.flush()
        return

    session.add(
        ScanPipelineReplayItem(
            replay_run_id=replay_run_id,
            scan_session_item_id=scan_session_item_id,
            result_state=state,
            baseline_snapshot_json=baseline,
            replay_snapshot_json=replay,
            diff_categories_json=[],
            diff_summary_json=summary,
            last_error=last_error,
            created_at=ts,
            updated_at=ts,
            completed_at=ts,
        ),
    )
    session.flush()


def latest_replay_summary_for_scan_session(session: Session, *, scan_session_id: int) -> ScanPipelineReplayRunSummaryRead | None:
    stmt = (
        select(ScanPipelineReplayRun)
        .where(ScanPipelineReplayRun.scan_session_id == scan_session_id)
        .order_by(ScanPipelineReplayRun.created_at.desc(), ScanPipelineReplayRun.id.desc())
        .limit(1)
    )
    row = session.exec(stmt).first()
    if row is None or row.id is None:
        return None
    return ScanPipelineReplayRunSummaryRead.model_validate(row, from_attributes=True)
