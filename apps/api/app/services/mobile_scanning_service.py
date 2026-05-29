from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, col, func, select

from app.models import (
    MarketplaceListingDraft,
    OrganizationInventoryAssignment,
    ShopifyProductMapping,
)
from app.models.mobile_foundation import MobileDevice
from app.models.mobile_scanning import IntakeStagingRecord, ScanCapture, ScanEvent, ScanLookupResult
from app.models.offline_inventory import OfflineInventoryRecord
from app.schemas.mobile_scanning import (
    IntakeStagingCreateRequest,
    IntakeStagingListResponse,
    IntakeStagingRecordResponse,
    IntakeStagingUpdateRequest,
    MobileScanningDashboardResponse,
    MobileScanPermissionResponse,
    ScanCaptureDetailResponse,
    ScanCaptureListResponse,
    ScanCaptureRequest,
    ScanCaptureResponse,
    ScanEventResponse,
    ScanLookupListResponse,
    ScanLookupResultResponse,
)
from app.services.marketplace_permissions import MarketplacePermissionResolution
from app.services.mobile_device_security_service import validate_mobile_device_access
from app.services.mobile_scan_registry import (
    LOOKUP_TYPE_INVENTORY_ITEM,
    LOOKUP_TYPE_KNOWN_UPC,
    LOOKUP_TYPE_MARKETPLACE_LISTING,
    LOOKUP_TYPE_STOREFRONT_MAPPING,
    SCAN_STATUS_CAPTURED,
    SCAN_STATUS_LOOKUP_COMPLETE,
    SCAN_STATUS_STAGED,
    STAGING_STATUS_APPROVED,
    STAGING_STATUS_ARCHIVED,
    STAGING_STATUS_PENDING,
    can_transition_scan_status,
    can_transition_staging_status,
    list_lookup_types,
    list_scan_statuses,
    list_scan_types,
    list_staging_statuses,
    normalize_scan_value,
    validate_scan_type,
    validate_staging_status,
)
from app.services.mobile_scan_upc_registry import lookup_known_upc
from app.services.mobile_scanning_permissions import (
    validate_mobile_scan_manage_access,
    validate_mobile_scan_view_access,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _permission_response(resolution: MarketplacePermissionResolution) -> MobileScanPermissionResponse:
    return MobileScanPermissionResponse(can_view=resolution.can_view, can_manage=resolution.can_manage)


def create_scan_event(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int | None,
    event_type: str,
    event_payload_json: dict | None = None,
) -> ScanEvent:
    row = ScanEvent(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        event_payload_json=_json_safe(event_payload_json or {}),
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return row


def _capture_response(row: ScanCapture) -> ScanCaptureResponse:
    return ScanCaptureResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        device_id=row.device_id,
        scan_type=row.scan_type,
        scan_value=row.scan_value,
        normalized_value=row.normalized_value,
        scan_status=row.scan_status,
        created_at=row.created_at,
    )


def _lookup_response(row: ScanLookupResult) -> ScanLookupResultResponse:
    return ScanLookupResultResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        scan_capture_id=row.scan_capture_id,
        lookup_type=row.lookup_type,
        lookup_payload_json=row.lookup_payload_json,
        created_at=row.created_at,
    )


def _staging_response(row: IntakeStagingRecord) -> IntakeStagingRecordResponse:
    return IntakeStagingRecordResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        scan_capture_id=row.scan_capture_id,
        staging_status=row.staging_status,
        staging_payload_json=row.staging_payload_json,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _event_response(row: ScanEvent) -> ScanEventResponse:
    return ScanEventResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        actor_user_id=row.actor_user_id,
        event_type=row.event_type,
        event_payload_json=row.event_payload_json,
        created_at=row.created_at,
    )


def _get_org_device(session: Session, *, organization_id: int, device_id: int) -> MobileDevice:
    device = session.get(MobileDevice, device_id)
    if device is None or device.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Mobile device not found.")
    return device


def _get_org_capture(session: Session, *, organization_id: int, scan_capture_id: int) -> ScanCapture:
    row = session.get(ScanCapture, scan_capture_id)
    if row is None or row.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Scan capture not found.")
    return row


def normalize_scan(scan_type: str, scan_value: str) -> str:
    try:
        return normalize_scan_value(scan_type, scan_value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _set_scan_status(session: Session, capture: ScanCapture, target: str) -> None:
    if not can_transition_scan_status(capture.scan_status, target):
        raise HTTPException(status_code=422, detail="Invalid scan status transition.")
    capture.scan_status = target
    session.add(capture)


def lookup_inventory(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    scan_capture_id: int,
    normalized_value: str,
) -> list[ScanLookupResult]:
    capture = _get_org_capture(session, organization_id=organization_id, scan_capture_id=scan_capture_id)
    candidates: list[tuple[str, dict[str, Any]]] = []

    known = lookup_known_upc(normalized_value)
    if known is not None:
        candidates.append((LOOKUP_TYPE_KNOWN_UPC, known))

    if normalized_value.isdigit():
        inventory_id = int(normalized_value)
        assignment = session.exec(
            select(OrganizationInventoryAssignment)
            .where(OrganizationInventoryAssignment.organization_id == organization_id)
            .where(OrganizationInventoryAssignment.inventory_item_id == inventory_id)
            .order_by(OrganizationInventoryAssignment.assigned_at.asc(), OrganizationInventoryAssignment.id.asc())
        ).first()
        if assignment is not None:
            candidates.append(
                (
                    LOOKUP_TYPE_INVENTORY_ITEM,
                    {
                        "inventory_item_id": inventory_id,
                        "assignment_id": int(assignment.id or 0),
                        "assignment_status": assignment.assignment_status,
                    },
                )
            )

    offline = session.exec(
        select(OfflineInventoryRecord)
        .where(OfflineInventoryRecord.organization_id == organization_id)
        .where(OfflineInventoryRecord.local_record_identifier == normalized_value)
        .order_by(OfflineInventoryRecord.created_at.asc(), OfflineInventoryRecord.id.asc())
    ).first()
    if offline is not None:
        candidates.append(
            (
                LOOKUP_TYPE_INVENTORY_ITEM,
                {
                    "offline_record_id": int(offline.id or 0),
                    "local_record_identifier": offline.local_record_identifier,
                    "inventory_item_id": offline.inventory_item_id,
                },
            )
        )

    listings = session.exec(
        select(MarketplaceListingDraft)
        .where(MarketplaceListingDraft.organization_id == organization_id)
        .where(MarketplaceListingDraft.listing_title == normalized_value)
        .order_by(MarketplaceListingDraft.created_at.asc(), MarketplaceListingDraft.id.asc())
        .limit(5)
    ).all()
    for listing in listings:
        candidates.append(
            (
                LOOKUP_TYPE_MARKETPLACE_LISTING,
                {
                    "listing_draft_id": int(listing.id or 0),
                    "listing_title": listing.listing_title,
                    "inventory_item_id": listing.inventory_item_id,
                },
            )
        )

    mappings = session.exec(
        select(ShopifyProductMapping)
        .where(ShopifyProductMapping.organization_id == organization_id)
        .where(ShopifyProductMapping.storefront_product_identifier == normalized_value)
        .order_by(ShopifyProductMapping.updated_at.asc(), ShopifyProductMapping.id.asc())
        .limit(5)
    ).all()
    for mapping in mappings:
        candidates.append(
            (
                LOOKUP_TYPE_STOREFRONT_MAPPING,
                {
                    "mapping_id": int(mapping.id or 0),
                    "storefront_product_identifier": mapping.storefront_product_identifier,
                    "inventory_item_id": mapping.inventory_item_id,
                },
            )
        )

    candidates.sort(key=lambda item: (item[0], str(item[1].get("inventory_item_id", "")), str(item[1])))

    results: list[ScanLookupResult] = []
    for lookup_type, payload in candidates:
        row = ScanLookupResult(
            organization_id=organization_id,
            scan_capture_id=scan_capture_id,
            lookup_type=lookup_type,
            lookup_payload_json=_json_safe(payload),
            created_at=utc_now(),
        )
        session.add(row)
        session.flush()
        results.append(row)

    _set_scan_status(session, capture, SCAN_STATUS_LOOKUP_COMPLETE)
    create_scan_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type="inventory_lookup_completed",
        event_payload_json={
            "scan_capture_id": scan_capture_id,
            "normalized_value": normalized_value,
            "result_count": len(results),
        },
    )
    return results


def capture_scan(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    payload: ScanCaptureRequest,
) -> ScanCaptureDetailResponse:
    validate_mobile_scan_manage_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    _get_org_device(session, organization_id=organization_id, device_id=payload.device_id)
    validate_mobile_device_access(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        mobile_device_id=payload.device_id,
        action="mobile_scanning:capture",
        require_active_session=True,
    )
    try:
        validate_scan_type(payload.scan_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    normalized = normalize_scan(payload.scan_type, payload.scan_value)
    now = utc_now()
    capture = ScanCapture(
        organization_id=organization_id,
        device_id=payload.device_id,
        scan_type=payload.scan_type,
        scan_value=payload.scan_value.strip(),
        normalized_value=normalized,
        scan_status=SCAN_STATUS_CAPTURED,
        created_at=now,
    )
    session.add(capture)
    session.flush()
    capture_id = int(capture.id or 0)

    create_scan_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type="scan_captured",
        event_payload_json={"scan_capture_id": capture_id, "scan_type": payload.scan_type},
    )
    create_scan_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type="scan_normalized",
        event_payload_json={
            "scan_capture_id": capture_id,
            "scan_value": capture.scan_value,
            "normalized_value": normalized,
        },
    )

    lookup_rows = lookup_inventory(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        scan_capture_id=capture_id,
        normalized_value=normalized,
    )
    session.commit()
    session.refresh(capture)
    for row in lookup_rows:
        session.refresh(row)
    return ScanCaptureDetailResponse(
        capture=_capture_response(capture),
        lookup_results=[_lookup_response(row) for row in lookup_rows],
    )


def create_staging_record(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    payload: IntakeStagingCreateRequest,
) -> IntakeStagingRecordResponse:
    validate_mobile_scan_manage_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    capture = _get_org_capture(session, organization_id=organization_id, scan_capture_id=payload.scan_capture_id)
    validate_mobile_device_access(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        mobile_device_id=capture.device_id,
        action="mobile_scanning:staging_create",
        require_active_session=True,
    )
    if capture.scan_status not in {SCAN_STATUS_LOOKUP_COMPLETE, SCAN_STATUS_CAPTURED}:
        raise HTTPException(status_code=422, detail="Scan capture is not eligible for intake staging.")
    now = utc_now()
    row = IntakeStagingRecord(
        organization_id=organization_id,
        scan_capture_id=payload.scan_capture_id,
        staging_status=STAGING_STATUS_PENDING,
        staging_payload_json=_json_safe(payload.staging_payload_json),
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    _set_scan_status(session, capture, SCAN_STATUS_STAGED)
    create_scan_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type="intake_record_created",
        event_payload_json={"staging_id": int(row.id or 0), "scan_capture_id": payload.scan_capture_id},
    )
    session.commit()
    session.refresh(row)
    return _staging_response(row)


def approve_staging_record(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    staging_id: int,
) -> IntakeStagingRecordResponse:
    return _update_staging_status(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        staging_id=staging_id,
        target_status=STAGING_STATUS_APPROVED,
        event_type="intake_record_approved",
    )


def archive_staging_record(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    staging_id: int,
) -> IntakeStagingRecordResponse:
    return _update_staging_status(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        staging_id=staging_id,
        target_status=STAGING_STATUS_ARCHIVED,
        event_type="intake_record_archived",
    )


def _update_staging_status(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    staging_id: int,
    target_status: str,
    event_type: str,
) -> IntakeStagingRecordResponse:
    validate_mobile_scan_manage_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    row = session.get(IntakeStagingRecord, staging_id)
    if row is None or row.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Intake staging record not found.")
    capture = _get_org_capture(session, organization_id=organization_id, scan_capture_id=row.scan_capture_id)
    validate_mobile_device_access(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        mobile_device_id=capture.device_id,
        action="mobile_scanning:staging_update",
        require_active_session=True,
    )
    try:
        validate_staging_status(target_status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not can_transition_staging_status(row.staging_status, target_status):
        raise HTTPException(status_code=422, detail="Invalid staging status transition.")
    if row.staging_status == target_status:
        return _staging_response(row)
    previous = row.staging_status
    row.staging_status = target_status
    row.updated_at = utc_now()
    session.add(row)
    create_scan_event(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        event_payload_json={"staging_id": staging_id, "previous_status": previous, "staging_status": target_status},
    )
    session.commit()
    session.refresh(row)
    return _staging_response(row)


def update_staging_record(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    staging_id: int,
    payload: IntakeStagingUpdateRequest,
) -> IntakeStagingRecordResponse:
    if payload.staging_status == STAGING_STATUS_APPROVED:
        return approve_staging_record(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            staging_id=staging_id,
        )
    if payload.staging_status == STAGING_STATUS_ARCHIVED:
        return archive_staging_record(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            staging_id=staging_id,
        )
    raise HTTPException(status_code=422, detail="Unsupported staging status update.")


def list_scans(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> ScanCaptureListResponse:
    resolution = validate_mobile_scan_view_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    total_count = session.exec(
        select(func.count()).select_from(ScanCapture).where(ScanCapture.organization_id == organization_id)
    ).one()
    rows = session.exec(
        select(ScanCapture)
        .where(ScanCapture.organization_id == organization_id)
        .order_by(ScanCapture.created_at.asc(), ScanCapture.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return ScanCaptureListResponse(
        organization_id=organization_id,
        permissions=_permission_response(resolution),
        items=[_capture_response(row) for row in rows],
        total_items=int(total_count),
        limit=limit,
        offset=offset,
    )


def list_lookup_results(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> ScanLookupListResponse:
    resolution = validate_mobile_scan_view_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    total_count = session.exec(
        select(func.count()).select_from(ScanLookupResult).where(ScanLookupResult.organization_id == organization_id)
    ).one()
    rows = session.exec(
        select(ScanLookupResult)
        .where(ScanLookupResult.organization_id == organization_id)
        .order_by(ScanLookupResult.created_at.asc(), ScanLookupResult.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return ScanLookupListResponse(
        organization_id=organization_id,
        permissions=_permission_response(resolution),
        items=[_lookup_response(row) for row in rows],
        total_items=int(total_count),
        limit=limit,
        offset=offset,
    )


def list_staging_records(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> IntakeStagingListResponse:
    resolution = validate_mobile_scan_view_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    total_count = session.exec(
        select(func.count()).select_from(IntakeStagingRecord).where(IntakeStagingRecord.organization_id == organization_id)
    ).one()
    rows = session.exec(
        select(IntakeStagingRecord)
        .where(IntakeStagingRecord.organization_id == organization_id)
        .order_by(IntakeStagingRecord.created_at.asc(), IntakeStagingRecord.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return IntakeStagingListResponse(
        organization_id=organization_id,
        permissions=_permission_response(resolution),
        items=[_staging_response(row) for row in rows],
        total_items=int(total_count),
        limit=limit,
        offset=offset,
    )


def build_mobile_scanning_dashboard(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
) -> MobileScanningDashboardResponse:
    resolution = validate_mobile_scan_view_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    scan_count = session.exec(
        select(func.count()).select_from(ScanCapture).where(ScanCapture.organization_id == organization_id)
    ).one()
    lookup_count = session.exec(
        select(func.count()).select_from(ScanLookupResult).where(ScanLookupResult.organization_id == organization_id)
    ).one()
    staging_count = session.exec(
        select(func.count()).select_from(IntakeStagingRecord).where(IntakeStagingRecord.organization_id == organization_id)
    ).one()
    pending_staging = session.exec(
        select(func.count())
        .select_from(IntakeStagingRecord)
        .where(IntakeStagingRecord.organization_id == organization_id)
        .where(IntakeStagingRecord.staging_status == STAGING_STATUS_PENDING)
    ).one()
    events = session.exec(
        select(ScanEvent)
        .where(ScanEvent.organization_id == organization_id)
        .order_by(col(ScanEvent.created_at).desc(), col(ScanEvent.id).desc())
        .limit(20)
    ).all()
    return MobileScanningDashboardResponse(
        organization_id=organization_id,
        permissions=_permission_response(resolution),
        summary={
            "scans": {"total": int(scan_count)},
            "lookups": {"total": int(lookup_count)},
            "staging": {"total": int(staging_count), "pending": int(pending_staging)},
        },
        runtime_registry={
            "scan_types": list(list_scan_types()),
            "scan_statuses": list(list_scan_statuses()),
            "staging_statuses": list(list_staging_statuses()),
            "lookup_types": list(list_lookup_types()),
        },
        recent_events=[_event_response(row) for row in events],
    )
