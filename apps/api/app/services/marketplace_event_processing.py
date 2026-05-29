from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import (
    MarketplaceAccount,
    MarketplaceEvent,
    MarketplaceEventLineage,
    MarketplaceEventProcessingRun,
)
from app.schemas.marketplace_events import (
    MarketplaceEventDetailResponse,
    MarketplaceEventListResponse,
    MarketplaceEventPermissionResponse,
    MarketplaceEventProcessingRunListResponse,
    MarketplaceEventProcessingRunResponse,
    MarketplaceEventResponse,
    MarketplaceEventSummaryResponse,
    MarketplaceEventValidationErrorResponse,
    MarketplaceEventLineageResponse,
)
from app.services.marketplace_event_validation import (
    MarketplaceEventValidationResult,
    detect_duplicate_event,
    resolve_event_validation_errors,
    validate_marketplace_event,
)
from app.services.marketplace_permissions import (
    MarketplacePermissionResolution,
    resolve_marketplace_permissions,
)

EVENT_STATUS_RECEIVED = "received"
EVENT_STATUS_VALIDATED = "validated"
EVENT_STATUS_PROCESSED = "processed"
EVENT_STATUS_FAILED = "failed"
EVENT_STATUSES = {EVENT_STATUS_RECEIVED, EVENT_STATUS_VALIDATED, EVENT_STATUS_PROCESSED, EVENT_STATUS_FAILED}

PROCESSING_STATUS_PENDING = "pending"
PROCESSING_STATUS_RUNNING = "running"
PROCESSING_STATUS_COMPLETED = "completed"
PROCESSING_STATUS_FAILED = "failed"
PROCESSING_STATUSES = {
    PROCESSING_STATUS_PENDING,
    PROCESSING_STATUS_RUNNING,
    PROCESSING_STATUS_COMPLETED,
    PROCESSING_STATUS_FAILED,
}

ENDPOINT_STATUS_ACTIVE = "active"
ENDPOINT_STATUS_INACTIVE = "inactive"


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


def _permission_response(resolution: MarketplacePermissionResolution) -> MarketplaceEventPermissionResponse:
    return MarketplaceEventPermissionResponse(can_view=resolution.can_view, can_manage=resolution.can_manage)


def _event_or_404(session: Session, *, organization_id: int, marketplace_event_id: int) -> MarketplaceEvent:
    event = session.get(MarketplaceEvent, marketplace_event_id)
    if event is None or event.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Marketplace event not found.")
    return event


def _account_or_404(session: Session, *, organization_id: int, marketplace_account_id: int) -> MarketplaceAccount:
    account = session.get(MarketplaceAccount, marketplace_account_id)
    if account is None or account.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Marketplace account not found.")
    return account


def create_event_lineage(
    session: Session,
    *,
    organization_id: int,
    marketplace_event_id: int | None,
    actor_user_id: int | None,
    lineage_event_type: str,
    lineage_payload_json: dict[str, Any],
) -> MarketplaceEventLineage:
    row = MarketplaceEventLineage(
        organization_id=organization_id,
        marketplace_event_id=marketplace_event_id,
        actor_user_id=actor_user_id,
        lineage_event_type=lineage_event_type,
        lineage_payload_json=_json_safe(lineage_payload_json),
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return row


def create_processing_run(
    session: Session,
    *,
    organization_id: int,
    marketplace_event_id: int,
    processing_status: str = PROCESSING_STATUS_PENDING,
    processing_result_json: dict[str, Any] | None = None,
) -> MarketplaceEventProcessingRun:
    row = MarketplaceEventProcessingRun(
        organization_id=organization_id,
        marketplace_event_id=marketplace_event_id,
        processing_status=processing_status,
        processing_result_json=_json_safe(processing_result_json or {}),
        started_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return row


def _validate_visibility(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    action: str,
) -> MarketplacePermissionResolution:
    resolution = resolve_marketplace_permissions(session, organization_id=organization_id, actor_user_id=actor_user_id)
    if not resolution.can_view:
        create_event_lineage(
            session,
            organization_id=organization_id,
            marketplace_event_id=None,
            actor_user_id=actor_user_id,
            lineage_event_type="unauthorized_marketplace_event_access_attempt",
            lineage_payload_json={"action": action, "reason": resolution.reason},
        )
        session.commit()
        raise HTTPException(status_code=403, detail="Marketplace event visibility is denied for this organization.")
    return resolution


def _validate_management(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    marketplace_account_id: int,
    action: str,
) -> MarketplacePermissionResolution:
    resolution = resolve_marketplace_permissions(session, organization_id=organization_id, actor_user_id=actor_user_id)
    if not resolution.can_manage:
        create_event_lineage(
            session,
            organization_id=organization_id,
            marketplace_event_id=None,
            actor_user_id=actor_user_id,
            lineage_event_type="unauthorized_marketplace_event_access_attempt",
            lineage_payload_json={
                "action": action,
                "reason": resolution.reason,
                "marketplace_account_id": marketplace_account_id,
            },
        )
        session.commit()
        raise HTTPException(status_code=403, detail="Marketplace event management is denied for this organization.")
    _account_or_404(session, organization_id=organization_id, marketplace_account_id=marketplace_account_id)
    return resolution


def _to_event_response(row: MarketplaceEvent) -> MarketplaceEventResponse:
    return MarketplaceEventResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        marketplace_account_id=row.marketplace_account_id,
        marketplace_type=row.marketplace_type,
        external_event_identifier=row.external_event_identifier,
        event_type=row.event_type,
        event_status=row.event_status,
        event_payload_json=dict(row.event_payload_json or {}),
        received_at=row.received_at,
        processed_at=row.processed_at,
        created_at=row.created_at,
    )


def _to_run_response(row: MarketplaceEventProcessingRun) -> MarketplaceEventProcessingRunResponse:
    return MarketplaceEventProcessingRunResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        marketplace_event_id=row.marketplace_event_id,
        processing_status=row.processing_status,
        processing_result_json=dict(row.processing_result_json or {}),
        started_at=row.started_at,
        completed_at=row.completed_at,
    )


def _to_lineage_response(row: MarketplaceEventLineage) -> MarketplaceEventLineageResponse:
    return MarketplaceEventLineageResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        marketplace_event_id=row.marketplace_event_id,
        actor_user_id=row.actor_user_id,
        lineage_event_type=row.lineage_event_type,
        lineage_payload_json=dict(row.lineage_payload_json or {}),
        created_at=row.created_at,
    )


def _event_detail(
    session: Session,
    *,
    event: MarketplaceEvent,
    resolution: MarketplacePermissionResolution,
) -> MarketplaceEventDetailResponse:
    runs = session.exec(
        select(MarketplaceEventProcessingRun)
        .where(MarketplaceEventProcessingRun.marketplace_event_id == event.id)
        .order_by(MarketplaceEventProcessingRun.started_at.asc(), MarketplaceEventProcessingRun.id.asc())
    ).all()
    lineage = session.exec(
        select(MarketplaceEventLineage)
        .where(MarketplaceEventLineage.marketplace_event_id == event.id)
        .order_by(MarketplaceEventLineage.created_at.asc(), MarketplaceEventLineage.id.asc())
    ).all()
    validation_errors = [
        MarketplaceEventValidationErrorResponse(code=error.get("code", "validation_error"), message=error.get("message", "Validation failed."))
        for error in event.event_payload_json.get("validation_errors", [])
        if isinstance(error, dict)
    ]
    return MarketplaceEventDetailResponse(
        event=_to_event_response(event),
        validation_errors=validation_errors,
        permissions=_permission_response(resolution),
        processing_runs=[_to_run_response(row) for row in runs],
        lineage=[_to_lineage_response(row) for row in lineage],
    )


def ingest_marketplace_event(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    marketplace_account_id: int,
    external_event_identifier: str,
    event_type: str,
    event_payload_json: dict[str, Any],
    received_at: datetime | None = None,
) -> MarketplaceEventDetailResponse:
    _validate_management(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        marketplace_account_id=marketplace_account_id,
        action="marketplace_event:ingest",
    )
    duplicate = detect_duplicate_event(
        session,
        marketplace_account_id=marketplace_account_id,
        external_event_identifier=external_event_identifier,
    )
    if duplicate is not None:
        create_event_lineage(
            session,
            organization_id=organization_id,
            marketplace_event_id=duplicate.id,
            actor_user_id=actor_user_id,
            lineage_event_type="marketplace_duplicate_event_detected",
            lineage_payload_json={
                "external_event_identifier": duplicate.external_event_identifier,
                "event_type": duplicate.event_type,
            },
        )
        session.commit()
        return _event_detail(session, event=duplicate, resolution=resolve_marketplace_permissions(session, organization_id=organization_id, actor_user_id=actor_user_id))

    account = _account_or_404(session, organization_id=organization_id, marketplace_account_id=marketplace_account_id)
    validation = validate_marketplace_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        marketplace_account_id=marketplace_account_id,
        external_event_identifier=external_event_identifier,
        event_type=event_type,
        event_payload_json=event_payload_json,
    )
    if not validation.is_valid:
        event = MarketplaceEvent(
            organization_id=organization_id,
            marketplace_account_id=marketplace_account_id,
            marketplace_type=account.marketplace_type,
            external_event_identifier=external_event_identifier.strip(),
            event_type=validation.event_type,
            event_status=EVENT_STATUS_FAILED,
            event_payload_json=_json_safe({"validation_errors": resolve_event_validation_errors(validation.errors), "original_payload": event_payload_json}),
            received_at=received_at or utc_now(),
            created_at=utc_now(),
        )
        session.add(event)
        session.flush()
        create_event_lineage(
            session,
            organization_id=organization_id,
            marketplace_event_id=int(event.id or 0),
            actor_user_id=actor_user_id,
            lineage_event_type="marketplace_event_ingested",
            lineage_payload_json={"event_type": event.event_type, "external_event_identifier": event.external_event_identifier},
        )
        event.event_status = EVENT_STATUS_FAILED
        session.add(event)
        create_event_lineage(
            session,
            organization_id=organization_id,
            marketplace_event_id=int(event.id or 0),
            actor_user_id=actor_user_id,
            lineage_event_type="marketplace_event_validation_failed",
            lineage_payload_json={"validation_errors": resolve_event_validation_errors(validation.errors)},
        )
        session.commit()
        return _event_detail(session, event=event, resolution=resolve_marketplace_permissions(session, organization_id=organization_id, actor_user_id=actor_user_id))

    event = MarketplaceEvent(
        organization_id=organization_id,
        marketplace_account_id=marketplace_account_id,
        marketplace_type=account.marketplace_type,
        external_event_identifier=external_event_identifier.strip(),
        event_type=validation.event_type,
        event_status=EVENT_STATUS_VALIDATED,
        event_payload_json=_json_safe(event_payload_json),
        received_at=received_at or utc_now(),
        created_at=utc_now(),
    )
    session.add(event)
    session.flush()
    create_event_lineage(
        session,
        organization_id=organization_id,
        marketplace_event_id=int(event.id or 0),
        actor_user_id=actor_user_id,
        lineage_event_type="marketplace_event_ingested",
        lineage_payload_json={"event_type": event.event_type, "external_event_identifier": event.external_event_identifier},
    )
    session.add(event)
    session.commit()
    return _event_detail(session, event=event, resolution=resolve_marketplace_permissions(session, organization_id=organization_id, actor_user_id=actor_user_id))


def process_marketplace_event(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    marketplace_event_id: int,
) -> MarketplaceEventDetailResponse:
    _validate_visibility(session, organization_id=organization_id, actor_user_id=actor_user_id, action="marketplace_event:process")
    event = _event_or_404(session, organization_id=organization_id, marketplace_event_id=marketplace_event_id)
    if event.event_status == EVENT_STATUS_FAILED:
        raise HTTPException(status_code=422, detail="Failed marketplace events cannot be processed.")
    if event.event_status == EVENT_STATUS_RECEIVED:
        validation = validate_marketplace_event(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            marketplace_account_id=event.marketplace_account_id,
            external_event_identifier=event.external_event_identifier,
            event_type=event.event_type,
            event_payload_json=event.event_payload_json,
            exclude_event_id=event.id,
        )
        if not validation.is_valid:
            event.event_status = EVENT_STATUS_FAILED
            event.event_payload_json = _json_safe({"validation_errors": resolve_event_validation_errors(validation.errors), "original_payload": event.event_payload_json})
            session.add(event)
            create_event_lineage(
                session,
                organization_id=organization_id,
                marketplace_event_id=int(event.id or 0),
                actor_user_id=actor_user_id,
                lineage_event_type="marketplace_event_validation_failed",
                lineage_payload_json={"validation_errors": resolve_event_validation_errors(validation.errors)},
            )
            session.commit()
            return _event_detail(session, event=event, resolution=resolve_marketplace_permissions(session, organization_id=organization_id, actor_user_id=actor_user_id))
        event.event_status = EVENT_STATUS_VALIDATED
        session.add(event)

    run = create_processing_run(
        session,
        organization_id=organization_id,
        marketplace_event_id=int(event.id or 0),
    )
    run.processing_status = PROCESSING_STATUS_RUNNING
    run.processing_result_json = {"status": "processing_started"}
    session.add(run)
    create_event_lineage(
        session,
        organization_id=organization_id,
        marketplace_event_id=int(event.id or 0),
        actor_user_id=actor_user_id,
        lineage_event_type="marketplace_processing_run_created",
        lineage_payload_json={"processing_run_id": int(run.id or 0)},
    )
    run.processing_result_json = {"status": "processing_completed", "marketplace_event_id": int(event.id or 0)}
    run.processing_status = PROCESSING_STATUS_COMPLETED
    run.completed_at = utc_now()
    event.event_status = EVENT_STATUS_PROCESSED
    event.processed_at = utc_now()
    session.add(run)
    session.add(event)
    create_event_lineage(
        session,
        organization_id=organization_id,
        marketplace_event_id=int(event.id or 0),
        actor_user_id=actor_user_id,
        lineage_event_type="marketplace_event_processed",
        lineage_payload_json={"processing_run_id": int(run.id or 0), "event_status": event.event_status},
    )
    session.commit()
    return _event_detail(session, event=event, resolution=resolve_marketplace_permissions(session, organization_id=organization_id, actor_user_id=actor_user_id))


def list_marketplace_events(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> MarketplaceEventListResponse:
    resolution = _validate_visibility(session, organization_id=organization_id, actor_user_id=actor_user_id, action="marketplace_event:view")
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    base = select(MarketplaceEvent).where(MarketplaceEvent.organization_id == organization_id)
    total = len(session.exec(base).all())
    all_rows = session.exec(base).all()
    rows = session.exec(
        base.order_by(MarketplaceEvent.received_at.desc(), MarketplaceEvent.id.desc()).offset(offset).limit(limit)
    ).all()
    summary = MarketplaceEventSummaryResponse(
        total_events=total,
        received_events=sum(1 for row in all_rows if row.event_status == EVENT_STATUS_RECEIVED),
        validated_events=sum(1 for row in all_rows if row.event_status == EVENT_STATUS_VALIDATED),
        processed_events=sum(1 for row in all_rows if row.event_status == EVENT_STATUS_PROCESSED),
        failed_events=sum(1 for row in all_rows if row.event_status == EVENT_STATUS_FAILED),
    )
    return MarketplaceEventListResponse(
        items=[_to_event_response(row) for row in rows],
        permissions=_permission_response(resolution),
        summary=summary,
        total_items=total,
        limit=limit,
        offset=offset,
    )


def get_marketplace_event(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    event_id: int,
) -> MarketplaceEventDetailResponse:
    resolution = _validate_visibility(session, organization_id=organization_id, actor_user_id=actor_user_id, action="marketplace_event:view")
    event = _event_or_404(session, organization_id=organization_id, marketplace_event_id=event_id)
    return _event_detail(session, event=event, resolution=resolution)


def list_processing_runs(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> MarketplaceEventProcessingRunListResponse:
    resolution = _validate_visibility(session, organization_id=organization_id, actor_user_id=actor_user_id, action="marketplace_event:view")
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    base = select(MarketplaceEventProcessingRun).where(MarketplaceEventProcessingRun.organization_id == organization_id)
    total = len(session.exec(base).all())
    rows = session.exec(
        base.order_by(MarketplaceEventProcessingRun.started_at.desc(), MarketplaceEventProcessingRun.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return MarketplaceEventProcessingRunListResponse(
        items=[_to_run_response(row) for row in rows],
        permissions=_permission_response(resolution),
        total_items=total,
        limit=limit,
        offset=offset,
    )
