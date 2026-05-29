from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import (
    MarketplaceAccount,
    MarketplaceInventoryConflict,
    MarketplaceInventoryState,
    MarketplaceInventorySyncEvent,
    MarketplaceInventorySyncRun,
    MarketplaceListingDraft,
)
from app.schemas.marketplace_inventory_sync import (
    MarketplaceInventoryConflictListResponse,
    MarketplaceInventoryConflictResponse,
    MarketplaceInventoryDiagnosticsResponse,
    MarketplaceInventoryReconcileRequest,
    MarketplaceInventoryReconciliationReportResponse,
    MarketplaceInventoryStateListResponse,
    MarketplaceInventoryStateResponse,
    MarketplaceInventorySyncPermissionResponse,
    MarketplaceInventorySyncRunListResponse,
    MarketplaceInventorySyncRunRequest,
    MarketplaceInventorySyncRunResponse,
    MarketplaceInventorySyncSummaryResponse,
)
from app.services.marketplace_account_service import ACCOUNT_STATUS_CONNECTED
from app.services.marketplace_inventory_projection import generate_sync_diagnostics
from app.services.marketplace_inventory_reconciliation import (
    CONFLICT_TYPE_STALE_MARKETPLACE_STATE,
    InventoryDifference,
    detect_inventory_conflicts,
    generate_reconciliation_report,
)
from app.services.marketplace_listing_validation import LISTING_STATUS_ARCHIVED
from app.services.marketplace_permissions import (
    MarketplacePermissionResolution,
    resolve_marketplace_permissions,
)

SYNC_STATUS_PENDING = "pending"
SYNC_STATUS_RUNNING = "running"
SYNC_STATUS_COMPLETED = "completed"
SYNC_STATUS_FAILED = "failed"
SYNC_STATUSES = {SYNC_STATUS_PENDING, SYNC_STATUS_RUNNING, SYNC_STATUS_COMPLETED, SYNC_STATUS_FAILED}

CONFLICT_STATUS_DETECTED = "detected"
CONFLICT_STATUS_REVIEWED = "reviewed"
CONFLICT_STATUS_RESOLVED = "resolved"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def clamp_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 200), max(offset, 0)


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _permission_response(resolution: MarketplacePermissionResolution) -> MarketplaceInventorySyncPermissionResponse:
    return MarketplaceInventorySyncPermissionResponse(can_view=resolution.can_view, can_manage=resolution.can_manage)


def _to_state_response(row: MarketplaceInventoryState) -> MarketplaceInventoryStateResponse:
    return MarketplaceInventoryStateResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        marketplace_account_id=row.marketplace_account_id,
        marketplace_listing_draft_id=row.marketplace_listing_draft_id,
        marketplace_listing_identifier=row.marketplace_listing_identifier,
        inventory_item_id=row.inventory_item_id,
        local_quantity=row.local_quantity,
        marketplace_quantity=row.marketplace_quantity,
        sync_status=row.sync_status,
        last_sync_at=row.last_sync_at,
        created_at=row.created_at,
    )


def _to_run_response(row: MarketplaceInventorySyncRun) -> MarketplaceInventorySyncRunResponse:
    return MarketplaceInventorySyncRunResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        marketplace_account_id=row.marketplace_account_id,
        sync_run_type=row.sync_run_type,
        sync_status=row.sync_status,
        records_processed=row.records_processed,
        conflicts_detected=row.conflicts_detected,
        started_at=row.started_at,
        completed_at=row.completed_at,
    )


def _to_conflict_response(row: MarketplaceInventoryConflict) -> MarketplaceInventoryConflictResponse:
    return MarketplaceInventoryConflictResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        marketplace_inventory_state_id=row.marketplace_inventory_state_id,
        conflict_type=row.conflict_type,
        local_value_json=dict(row.local_value_json or {}),
        marketplace_value_json=dict(row.marketplace_value_json or {}),
        conflict_status=row.conflict_status,
        detected_at=row.detected_at,
        resolved_at=row.resolved_at,
    )


def _account_or_404(session: Session, *, organization_id: int, marketplace_account_id: int) -> MarketplaceAccount:
    account = session.get(MarketplaceAccount, marketplace_account_id)
    if account is None or account.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Marketplace account not found.")
    return account


def _drafts_for_sync(
    session: Session,
    *,
    organization_id: int,
    marketplace_account_id: int | None,
) -> list[MarketplaceListingDraft]:
    query = select(MarketplaceListingDraft).where(MarketplaceListingDraft.organization_id == organization_id)
    if marketplace_account_id is not None:
        query = query.where(MarketplaceListingDraft.marketplace_account_id == marketplace_account_id)
    rows = session.exec(
        query.order_by(MarketplaceListingDraft.created_at.asc(), MarketplaceListingDraft.id.asc())
    ).all()
    return list(rows)


def create_sync_event(
    session: Session,
    *,
    organization_id: int,
    marketplace_account_id: int | None,
    sync_run_id: int | None,
    actor_user_id: int | None,
    event_type: str,
    event_payload_json: dict[str, Any],
) -> MarketplaceInventorySyncEvent:
    row = MarketplaceInventorySyncEvent(
        organization_id=organization_id,
        marketplace_account_id=marketplace_account_id,
        sync_run_id=sync_run_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        event_payload_json=_json_safe(event_payload_json),
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return row


def _validate_sync_visibility(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    marketplace_account_id: int | None = None,
    action: str = "marketplace_sync:view",
) -> MarketplacePermissionResolution:
    resolution = resolve_marketplace_permissions(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
    )
    if not resolution.can_view:
        create_sync_event(
            session,
            organization_id=organization_id,
            marketplace_account_id=marketplace_account_id,
            sync_run_id=None,
            actor_user_id=actor_user_id,
            event_type="unauthorized_marketplace_sync_access_attempt",
            event_payload_json={"action": action, "reason": resolution.reason},
        )
        session.commit()
        raise HTTPException(status_code=403, detail="Marketplace sync visibility is denied for this organization.")
    if marketplace_account_id is not None:
        _account_or_404(session, organization_id=organization_id, marketplace_account_id=marketplace_account_id)
    return resolution


def _validate_sync_management(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    marketplace_account_id: int | None = None,
    action: str = "marketplace_sync:manage",
) -> MarketplacePermissionResolution:
    resolution = resolve_marketplace_permissions(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
    )
    if not resolution.can_manage:
        create_sync_event(
            session,
            organization_id=organization_id,
            marketplace_account_id=marketplace_account_id,
            sync_run_id=None,
            actor_user_id=actor_user_id,
            event_type="unauthorized_marketplace_sync_access_attempt",
            event_payload_json={"action": action, "reason": resolution.reason},
        )
        session.commit()
        raise HTTPException(status_code=403, detail="Marketplace sync management is denied for this organization.")
    if marketplace_account_id is not None:
        account = _account_or_404(session, organization_id=organization_id, marketplace_account_id=marketplace_account_id)
        if account.account_status != ACCOUNT_STATUS_CONNECTED:
            raise HTTPException(status_code=409, detail="Marketplace account must be connected for sync runs.")
    return resolution


def create_sync_run(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    marketplace_account_id: int | None,
    sync_run_type: str,
) -> MarketplaceInventorySyncRun:
    _validate_sync_management(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        marketplace_account_id=marketplace_account_id,
    )
    run = MarketplaceInventorySyncRun(
        organization_id=organization_id,
        marketplace_account_id=marketplace_account_id,
        sync_run_type=sync_run_type.strip().lower(),
        sync_status=SYNC_STATUS_RUNNING,
        records_processed=0,
        conflicts_detected=0,
        started_at=utc_now(),
    )
    session.add(run)
    session.flush()
    create_sync_event(
        session,
        organization_id=organization_id,
        marketplace_account_id=marketplace_account_id,
        sync_run_id=int(run.id or 0),
        actor_user_id=actor_user_id,
        event_type="marketplace_sync_started",
        event_payload_json={"sync_run_type": run.sync_run_type},
    )
    return run


def register_marketplace_inventory_state(
    session: Session,
    *,
    organization_id: int,
    account: MarketplaceAccount,
    draft: MarketplaceListingDraft,
) -> MarketplaceInventoryState:
    now = utc_now()
    existing = session.exec(
        select(MarketplaceInventoryState)
        .where(MarketplaceInventoryState.marketplace_account_id == int(account.id or 0))
        .where(MarketplaceInventoryState.marketplace_listing_draft_id == int(draft.id or 0))
        .order_by(MarketplaceInventoryState.id.asc())
    ).first()
    listing_identifier = (
        existing.marketplace_listing_identifier
        if existing is not None
        else f"{account.marketplace_type}:{int(draft.id or 0)}"
    )
    local_quantity = 0 if draft.listing_status == LISTING_STATUS_ARCHIVED else int(draft.listing_quantity)
    if existing is None:
        existing = MarketplaceInventoryState(
            organization_id=organization_id,
            marketplace_account_id=int(account.id or 0),
            marketplace_listing_draft_id=int(draft.id or 0),
            marketplace_listing_identifier=listing_identifier,
            inventory_item_id=int(draft.inventory_item_id),
            local_quantity=local_quantity,
            marketplace_quantity=0,
            sync_status=SYNC_STATUS_PENDING,
            last_sync_at=now,
            created_at=now,
        )
    else:
        existing.inventory_item_id = int(draft.inventory_item_id)
        existing.marketplace_listing_identifier = listing_identifier
        existing.local_quantity = local_quantity
        existing.last_sync_at = now
    session.add(existing)
    session.flush()
    return existing


def _upsert_conflicts(
    session: Session,
    *,
    state: MarketplaceInventoryState,
    differences: tuple[InventoryDifference, ...],
) -> list[MarketplaceInventoryConflict]:
    existing_rows = session.exec(
        select(MarketplaceInventoryConflict)
        .where(MarketplaceInventoryConflict.marketplace_inventory_state_id == int(state.id or 0))
        .where(MarketplaceInventoryConflict.conflict_status != CONFLICT_STATUS_RESOLVED)
        .order_by(MarketplaceInventoryConflict.detected_at.asc(), MarketplaceInventoryConflict.id.asc())
    ).all()
    by_type = {row.conflict_type: row for row in existing_rows}
    touched_types = {row.conflict_type for row in differences}
    now = utc_now()
    created_or_updated: list[MarketplaceInventoryConflict] = []
    for diff in differences:
        row = by_type.get(diff.conflict_type)
        if row is None:
            row = MarketplaceInventoryConflict(
                organization_id=state.organization_id,
                marketplace_inventory_state_id=int(state.id or 0),
                conflict_type=diff.conflict_type,
                local_value_json=_json_safe(diff.local_value_json),
                marketplace_value_json=_json_safe(diff.marketplace_value_json),
                conflict_status=CONFLICT_STATUS_DETECTED,
                detected_at=now,
            )
        else:
            row.local_value_json = _json_safe(diff.local_value_json)
            row.marketplace_value_json = _json_safe(diff.marketplace_value_json)
            row.conflict_status = CONFLICT_STATUS_DETECTED
            row.detected_at = now
            row.resolved_at = None
        session.add(row)
        session.flush()
        created_or_updated.append(row)

    for row in existing_rows:
        if row.conflict_type in touched_types:
            continue
        if row.conflict_status != CONFLICT_STATUS_RESOLVED:
            row.conflict_status = CONFLICT_STATUS_RESOLVED
            row.resolved_at = now
            session.add(row)
    return created_or_updated


def process_inventory_sync(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    payload: MarketplaceInventorySyncRunRequest,
) -> MarketplaceInventorySyncRunResponse:
    run = create_sync_run(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        marketplace_account_id=payload.marketplace_account_id,
        sync_run_type=payload.sync_run_type,
    )
    conflict_count = 0
    processed = 0
    try:
        drafts = _drafts_for_sync(
            session,
            organization_id=organization_id,
            marketplace_account_id=payload.marketplace_account_id,
        )
        for draft in drafts:
            account = _account_or_404(
                session,
                organization_id=organization_id,
                marketplace_account_id=draft.marketplace_account_id,
            )
            state = register_marketplace_inventory_state(
                session,
                organization_id=organization_id,
                account=account,
                draft=draft,
            )
            differences = detect_inventory_conflicts(session, state=state)
            upserted = _upsert_conflicts(session, state=state, differences=differences)
            if differences:
                state.sync_status = SYNC_STATUS_FAILED
                for conflict in upserted:
                    create_sync_event(
                        session,
                        organization_id=organization_id,
                        marketplace_account_id=int(account.id or 0),
                        sync_run_id=int(run.id or 0),
                        actor_user_id=actor_user_id,
                        event_type="marketplace_conflict_detected",
                        event_payload_json={
                            "conflict_id": int(conflict.id or 0),
                            "conflict_type": conflict.conflict_type,
                            "marketplace_inventory_state_id": int(state.id or 0),
                        },
                    )
            else:
                state.sync_status = SYNC_STATUS_COMPLETED
            session.add(state)
            processed += 1
            conflict_count += len(differences)

        run.records_processed = processed
        run.conflicts_detected = conflict_count
        run.sync_status = SYNC_STATUS_COMPLETED
        run.completed_at = utc_now()
        session.add(run)
        create_sync_event(
            session,
            organization_id=organization_id,
            marketplace_account_id=payload.marketplace_account_id,
            sync_run_id=int(run.id or 0),
            actor_user_id=actor_user_id,
            event_type="marketplace_sync_completed",
            event_payload_json={
                "records_processed": processed,
                "conflicts_detected": conflict_count,
            },
        )
        session.commit()
    except Exception as exc:
        run.sync_status = SYNC_STATUS_FAILED
        run.completed_at = utc_now()
        session.add(run)
        create_sync_event(
            session,
            organization_id=organization_id,
            marketplace_account_id=payload.marketplace_account_id,
            sync_run_id=int(run.id or 0),
            actor_user_id=actor_user_id,
            event_type="marketplace_sync_failed",
            event_payload_json={"error": str(exc)},
        )
        session.commit()
        raise
    session.refresh(run)
    return _to_run_response(run)


def list_inventory_sync_runs(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
    marketplace_account_id: int | None = None,
) -> MarketplaceInventorySyncRunListResponse:
    _validate_sync_visibility(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        marketplace_account_id=marketplace_account_id,
    )
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    query = select(MarketplaceInventorySyncRun).where(MarketplaceInventorySyncRun.organization_id == organization_id)
    if marketplace_account_id is not None:
        query = query.where(MarketplaceInventorySyncRun.marketplace_account_id == marketplace_account_id)
    total = len(session.exec(query).all())
    rows = session.exec(
        query.order_by(MarketplaceInventorySyncRun.started_at.desc(), MarketplaceInventorySyncRun.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return MarketplaceInventorySyncRunListResponse(
        items=[_to_run_response(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_inventory_states(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
    marketplace_account_id: int | None = None,
) -> MarketplaceInventoryStateListResponse:
    _validate_sync_visibility(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        marketplace_account_id=marketplace_account_id,
    )
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    query = select(MarketplaceInventoryState).where(MarketplaceInventoryState.organization_id == organization_id)
    if marketplace_account_id is not None:
        query = query.where(MarketplaceInventoryState.marketplace_account_id == marketplace_account_id)
    total = len(session.exec(query).all())
    rows = session.exec(
        query.order_by(MarketplaceInventoryState.created_at.asc(), MarketplaceInventoryState.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return MarketplaceInventoryStateListResponse(
        items=[_to_state_response(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_inventory_conflicts(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> MarketplaceInventoryConflictListResponse:
    _validate_sync_visibility(session, organization_id=organization_id, actor_user_id=actor_user_id)
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    query = select(MarketplaceInventoryConflict).where(MarketplaceInventoryConflict.organization_id == organization_id)
    total = len(session.exec(query).all())
    rows = session.exec(
        query.order_by(MarketplaceInventoryConflict.detected_at.desc(), MarketplaceInventoryConflict.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return MarketplaceInventoryConflictListResponse(
        items=[_to_conflict_response(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def get_inventory_sync_summary(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
) -> MarketplaceInventorySyncSummaryResponse:
    resolution = _validate_sync_visibility(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
    )
    diagnostics = generate_sync_diagnostics(session, organization_id=organization_id)
    recent_runs = session.exec(
        select(MarketplaceInventorySyncRun)
        .where(MarketplaceInventorySyncRun.organization_id == organization_id)
        .order_by(MarketplaceInventorySyncRun.started_at.desc(), MarketplaceInventorySyncRun.id.desc())
        .limit(5)
    ).all()
    recent_conflicts = session.exec(
        select(MarketplaceInventoryConflict)
        .where(MarketplaceInventoryConflict.organization_id == organization_id)
        .order_by(MarketplaceInventoryConflict.detected_at.desc(), MarketplaceInventoryConflict.id.desc())
        .limit(10)
    ).all()
    recent_states = session.exec(
        select(MarketplaceInventoryState)
        .where(MarketplaceInventoryState.organization_id == organization_id)
        .order_by(MarketplaceInventoryState.created_at.asc(), MarketplaceInventoryState.id.asc())
        .limit(10)
    ).all()
    return MarketplaceInventorySyncSummaryResponse(
        diagnostics=diagnostics,
        recent_runs=[_to_run_response(row) for row in recent_runs],
        recent_conflicts=[_to_conflict_response(row) for row in recent_conflicts],
        recent_states=[_to_state_response(row) for row in recent_states],
        permissions=_permission_response(resolution),
    )


def reconcile_marketplace_inventory(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    payload: MarketplaceInventoryReconcileRequest,
) -> MarketplaceInventoryReconciliationReportResponse:
    _validate_sync_management(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        marketplace_account_id=payload.marketplace_account_id,
        action="marketplace_sync:reconcile",
    )
    states_query = select(MarketplaceInventoryState).where(MarketplaceInventoryState.organization_id == organization_id)
    if payload.marketplace_account_id is not None:
        states_query = states_query.where(MarketplaceInventoryState.marketplace_account_id == payload.marketplace_account_id)
    states = session.exec(
        states_query.order_by(MarketplaceInventoryState.created_at.asc(), MarketplaceInventoryState.id.asc())
    ).all()
    touched_conflicts: list[MarketplaceInventoryConflictResponse] = []
    for state in states:
        differences = detect_inventory_conflicts(session, state=state)
        updated = _upsert_conflicts(session, state=state, differences=differences)
        if differences:
            state.sync_status = SYNC_STATUS_FAILED
        else:
            state.sync_status = SYNC_STATUS_COMPLETED
        session.add(state)
        touched_conflicts.extend(_to_conflict_response(row) for row in updated)
    create_sync_event(
        session,
        organization_id=organization_id,
        marketplace_account_id=payload.marketplace_account_id,
        sync_run_id=None,
        actor_user_id=actor_user_id,
        event_type="marketplace_reconciliation_generated",
        event_payload_json={
            "states_evaluated": len(states),
            "conflicts_detected": len(touched_conflicts),
            "contains_stale_marketplace_state": any(
                row.conflict_type == CONFLICT_TYPE_STALE_MARKETPLACE_STATE for row in touched_conflicts
            ),
        },
    )
    session.commit()
    diagnostics = generate_sync_diagnostics(
        session,
        organization_id=organization_id,
        marketplace_account_id=payload.marketplace_account_id,
    )
    return generate_reconciliation_report(
        diagnostics=diagnostics,
        states=list(states),
        conflicts=sorted(
            touched_conflicts,
            key=lambda row: (row.detected_at, row.id),
        ),
    )
