from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, func, select

from app.models import (
    ConventionSession,
    InventoryCopy,
    MarketplaceListingDraft,
    MobileDevice,
    OfflineInventoryChange,
    OfflineInventoryRecord,
    OfflineSyncQueue,
    OrganizationInventoryAssignment,
    QuickSale,
    QuickSaleEvent,
    QuickSaleLineItem,
    QuickSalePayment,
)
from app.schemas.quick_sales import (
    QuickSaleCreateRequest,
    QuickSaleDetailResponse,
    QuickSaleEventResponse,
    QuickSaleLineItemCreateRequest,
    QuickSaleLineItemResponse,
    QuickSaleLineItemUpdateRequest,
    QuickSaleListResponse,
    QuickSalePaymentCreateRequest,
    QuickSalePaymentResponse,
    QuickSalePermissionResponse,
    QuickSaleResponse,
)
from app.services.marketplace_permissions import MarketplacePermissionResolution
from app.services.mobile_device_security_service import validate_mobile_device_access
from app.services.offline_sync_registry import CHANGE_TYPE_UPDATE, QUEUE_STATUS_PENDING
from app.services.quick_sale_permissions import (
    validate_quick_sale_manage_access,
    validate_quick_sale_view_access,
)
from app.services.quick_sale_registry import (
    LINE_ITEM_STATUS_ADDED,
    LINE_ITEM_STATUS_REMOVED,
    LINE_ITEM_STATUS_SOLD,
    PAYMENT_STATUS_RECORDED,
    PAYMENT_STATUS_VOIDED,
    SALE_SOURCE_OFFLINE,
    SALE_STATUS_COMPLETED,
    SALE_STATUS_DRAFT,
    SALE_STATUS_VOIDED,
    can_transition_line_item_status,
    can_transition_payment_status,
    can_transition_sale_status,
    list_line_item_statuses,
    list_payment_methods,
    list_payment_statuses,
    list_sale_sources,
    list_sale_statuses,
    validate_line_item_status,
    validate_payment_method,
    validate_sale_source,
)
from app.services.shared_inventory_service import ACTIVE_ASSIGNMENT_STATUS

RESERVED_HOLD_STATUS = "reserved_for_sale"
SOLD_HOLD_STATUS = "sold_internal"
AVAILABLE_HOLD_STATUS = "hold"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _money(value: Decimal | int | float | str) -> Decimal:
    if isinstance(value, Decimal):
        decimal_value = value
    else:
        decimal_value = Decimal(str(value))
    return decimal_value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, Decimal):
        return str(_money(value))
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _permission_response(resolution: MarketplacePermissionResolution) -> QuickSalePermissionResponse:
    return QuickSalePermissionResponse(can_view=resolution.can_view, can_manage=resolution.can_manage)


def create_quick_sale_event(
    session: Session,
    *,
    organization_id: int,
    quick_sale_id: int | None,
    actor_user_id: int | None,
    event_type: str,
    event_payload_json: dict | None = None,
) -> QuickSaleEvent:
    row = QuickSaleEvent(
        organization_id=organization_id,
        quick_sale_id=quick_sale_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        event_payload_json=_json_safe(event_payload_json or {}),
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return row


def _sale_response(row: QuickSale) -> QuickSaleResponse:
    return QuickSaleResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        convention_session_id=row.convention_session_id,
        mobile_device_id=row.mobile_device_id,
        sale_identifier=row.sale_identifier,
        sale_status=row.sale_status,
        buyer_label=row.buyer_label,
        subtotal_amount=_money(row.subtotal_amount),
        discount_amount=_money(row.discount_amount),
        total_amount=_money(row.total_amount),
        currency=row.currency,
        sale_source=row.sale_source,
        created_by_user_id=row.created_by_user_id,
        created_at=row.created_at,
        completed_at=row.completed_at,
        voided_at=row.voided_at,
    )


def _line_item_response(row: QuickSaleLineItem) -> QuickSaleLineItemResponse:
    return QuickSaleLineItemResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        quick_sale_id=row.quick_sale_id,
        inventory_item_id=row.inventory_item_id,
        offline_inventory_record_id=row.offline_inventory_record_id,
        marketplace_listing_draft_id=row.marketplace_listing_draft_id,
        quantity=row.quantity,
        unit_price=_money(row.unit_price),
        discount_amount=_money(row.discount_amount),
        line_total=_money(row.line_total),
        line_status=row.line_status,
        created_at=row.created_at,
    )


def _payment_response(row: QuickSalePayment) -> QuickSalePaymentResponse:
    return QuickSalePaymentResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        quick_sale_id=row.quick_sale_id,
        payment_method=row.payment_method,
        payment_status=row.payment_status,
        amount=_money(row.amount),
        currency=row.currency,
        payment_reference=row.payment_reference,
        created_at=row.created_at,
    )


def _event_response(row: QuickSaleEvent) -> QuickSaleEventResponse:
    return QuickSaleEventResponse(
        id=int(row.id or 0),
        organization_id=row.organization_id,
        quick_sale_id=row.quick_sale_id,
        actor_user_id=row.actor_user_id,
        event_type=row.event_type,
        event_payload_json=row.event_payload_json,
        created_at=row.created_at,
    )


def _get_org_sale(session: Session, *, organization_id: int, sale_id: int) -> QuickSale:
    row = session.get(QuickSale, sale_id)
    if row is None or row.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Quick sale not found.")
    return row


def _get_org_line_item(session: Session, *, organization_id: int, sale_id: int, line_item_id: int) -> QuickSaleLineItem:
    row = session.get(QuickSaleLineItem, line_item_id)
    if row is None or row.organization_id != organization_id or row.quick_sale_id != sale_id:
        raise HTTPException(status_code=404, detail="Quick sale line item not found.")
    return row


def _get_org_mobile_device(session: Session, *, organization_id: int, mobile_device_id: int) -> MobileDevice:
    row = session.get(MobileDevice, mobile_device_id)
    if row is None or row.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Mobile device not found.")
    return row


def _get_org_convention_session(session: Session, *, organization_id: int, convention_session_id: int) -> ConventionSession:
    row = session.get(ConventionSession, convention_session_id)
    if row is None or row.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Convention session not found.")
    return row


def _get_org_offline_record(session: Session, *, organization_id: int, offline_inventory_record_id: int) -> OfflineInventoryRecord:
    row = session.get(OfflineInventoryRecord, offline_inventory_record_id)
    if row is None or row.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Offline inventory record not found.")
    return row


def _get_org_listing_draft(session: Session, *, organization_id: int, marketplace_listing_draft_id: int) -> MarketplaceListingDraft:
    row = session.get(MarketplaceListingDraft, marketplace_listing_draft_id)
    if row is None or row.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Marketplace listing draft not found.")
    return row


def _active_inventory_assignment(
    session: Session,
    *,
    organization_id: int,
    inventory_item_id: int,
) -> OrganizationInventoryAssignment | None:
    return session.exec(
        select(OrganizationInventoryAssignment)
        .where(OrganizationInventoryAssignment.organization_id == organization_id)
        .where(OrganizationInventoryAssignment.inventory_item_id == inventory_item_id)
        .where(OrganizationInventoryAssignment.assignment_status == ACTIVE_ASSIGNMENT_STATUS)
        .order_by(OrganizationInventoryAssignment.assigned_at.asc(), OrganizationInventoryAssignment.id.asc())
    ).first()


def validate_inventory_sale_eligibility(
    session: Session,
    *,
    organization_id: int,
    inventory_item_id: int,
) -> InventoryCopy:
    inventory_row = session.get(InventoryCopy, inventory_item_id)
    if inventory_row is None:
        raise HTTPException(status_code=404, detail="Inventory item not found.")
    assignment = _active_inventory_assignment(session, organization_id=organization_id, inventory_item_id=inventory_item_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Inventory item is not assigned to this organization.")
    if inventory_row.hold_status == SOLD_HOLD_STATUS:
        raise HTTPException(status_code=409, detail="Inventory item has already been sold internally.")
    if inventory_row.hold_status == RESERVED_HOLD_STATUS:
        raise HTTPException(status_code=409, detail="Inventory item is already reserved for a sale.")
    return inventory_row


def reserve_inventory_for_sale(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    sale_id: int,
    inventory_item_id: int,
) -> InventoryCopy:
    inventory_row = validate_inventory_sale_eligibility(
        session,
        organization_id=organization_id,
        inventory_item_id=inventory_item_id,
    )
    inventory_row.hold_status = RESERVED_HOLD_STATUS
    session.add(inventory_row)
    create_quick_sale_event(
        session,
        organization_id=organization_id,
        quick_sale_id=sale_id,
        actor_user_id=actor_user_id,
        event_type="quick_sale_inventory_reserved",
        event_payload_json={"inventory_item_id": inventory_item_id},
    )
    return inventory_row


def mark_inventory_sold_internal(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    sale_id: int,
    inventory_item_id: int,
) -> InventoryCopy:
    inventory_row = session.get(InventoryCopy, inventory_item_id)
    if inventory_row is None:
        raise HTTPException(status_code=404, detail="Inventory item not found.")
    assignment = _active_inventory_assignment(session, organization_id=organization_id, inventory_item_id=inventory_item_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Inventory item is not assigned to this organization.")
    inventory_row.hold_status = SOLD_HOLD_STATUS
    session.add(inventory_row)
    create_quick_sale_event(
        session,
        organization_id=organization_id,
        quick_sale_id=sale_id,
        actor_user_id=actor_user_id,
        event_type="quick_sale_inventory_sold",
        event_payload_json={"inventory_item_id": inventory_item_id},
    )
    return inventory_row


def release_inventory_reservation(
    session: Session,
    *,
    organization_id: int,
    inventory_item_id: int,
) -> InventoryCopy | None:
    inventory_row = session.get(InventoryCopy, inventory_item_id)
    if inventory_row is None:
        return None
    assignment = _active_inventory_assignment(session, organization_id=organization_id, inventory_item_id=inventory_item_id)
    if assignment is None:
        return None
    if inventory_row.hold_status == RESERVED_HOLD_STATUS:
        inventory_row.hold_status = AVAILABLE_HOLD_STATUS
        session.add(inventory_row)
    return inventory_row


def recalculate_sale_totals(session: Session, *, sale: QuickSale) -> QuickSale:
    rows = session.exec(
        select(QuickSaleLineItem)
        .where(QuickSaleLineItem.quick_sale_id == sale.id)
        .where(QuickSaleLineItem.organization_id == sale.organization_id)
        .where(QuickSaleLineItem.line_status != LINE_ITEM_STATUS_REMOVED)
        .order_by(QuickSaleLineItem.created_at.asc(), QuickSaleLineItem.id.asc())
    ).all()
    subtotal = _money(sum((_money(row.unit_price) * row.quantity for row in rows), Decimal("0.00")))
    discount = _money(sum((_money(row.discount_amount) for row in rows), Decimal("0.00")))
    sale.subtotal_amount = subtotal
    sale.discount_amount = discount
    sale.total_amount = _money(subtotal - discount)
    session.add(sale)
    session.flush()
    return sale


def _line_items_for_sale(session: Session, *, sale_id: int) -> list[QuickSaleLineItem]:
    return session.exec(
        select(QuickSaleLineItem)
        .where(QuickSaleLineItem.quick_sale_id == sale_id)
        .order_by(QuickSaleLineItem.created_at.asc(), QuickSaleLineItem.id.asc())
    ).all()


def _payments_for_sale(session: Session, *, sale_id: int) -> list[QuickSalePayment]:
    return session.exec(
        select(QuickSalePayment)
        .where(QuickSalePayment.quick_sale_id == sale_id)
        .order_by(QuickSalePayment.created_at.asc(), QuickSalePayment.id.asc())
    ).all()


def _events_for_sale(session: Session, *, sale_id: int) -> list[QuickSaleEvent]:
    return session.exec(
        select(QuickSaleEvent)
        .where(QuickSaleEvent.quick_sale_id == sale_id)
        .order_by(QuickSaleEvent.created_at.asc(), QuickSaleEvent.id.asc())
    ).all()


def get_quick_sale(session: Session, *, organization_id: int, actor_user_id: int, sale_id: int) -> QuickSaleDetailResponse:
    validate_quick_sale_view_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    sale = _get_org_sale(session, organization_id=organization_id, sale_id=sale_id)
    return QuickSaleDetailResponse(
        sale=_sale_response(sale),
        line_items=[_line_item_response(row) for row in _line_items_for_sale(session, sale_id=int(sale.id or 0))],
        payments=[_payment_response(row) for row in _payments_for_sale(session, sale_id=int(sale.id or 0))],
        events=[_event_response(row) for row in _events_for_sale(session, sale_id=int(sale.id or 0))],
    )


def create_quick_sale(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    payload: QuickSaleCreateRequest,
) -> tuple[QuickSaleDetailResponse, bool]:
    validate_quick_sale_manage_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    try:
        validate_sale_source(payload.sale_source)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if payload.mobile_device_id is not None:
        _get_org_mobile_device(session, organization_id=organization_id, mobile_device_id=payload.mobile_device_id)
        validate_mobile_device_access(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            mobile_device_id=payload.mobile_device_id,
            action="quick_sales:create",
            require_active_session=True,
            offline_action=payload.sale_source == SALE_SOURCE_OFFLINE,
        )
    if payload.convention_session_id is not None:
        _get_org_convention_session(session, organization_id=organization_id, convention_session_id=payload.convention_session_id)

    existing = session.exec(
        select(QuickSale)
        .where(QuickSale.organization_id == organization_id)
        .where(QuickSale.sale_identifier == payload.sale_identifier)
    ).first()
    if existing is not None:
        return get_quick_sale(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            sale_id=int(existing.id or 0),
        ), False

    row = QuickSale(
        organization_id=organization_id,
        convention_session_id=payload.convention_session_id,
        mobile_device_id=payload.mobile_device_id,
        sale_identifier=payload.sale_identifier,
        sale_status=SALE_STATUS_DRAFT,
        buyer_label=payload.buyer_label,
        subtotal_amount=_money("0.00"),
        discount_amount=_money("0.00"),
        total_amount=_money("0.00"),
        currency=payload.currency,
        sale_source=payload.sale_source,
        created_by_user_id=actor_user_id,
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    sale_id = int(row.id or 0)
    create_quick_sale_event(
        session,
        organization_id=organization_id,
        quick_sale_id=sale_id,
        actor_user_id=actor_user_id,
        event_type="quick_sale_created",
        event_payload_json={"sale_identifier": payload.sale_identifier, "sale_source": payload.sale_source},
    )
    session.commit()
    session.refresh(row)
    return get_quick_sale(session, organization_id=organization_id, actor_user_id=actor_user_id, sale_id=sale_id), True


def _resolve_line_item_inventory_reference(
    session: Session,
    *,
    organization_id: int,
    payload: QuickSaleLineItemCreateRequest,
) -> tuple[int | None, int | None, int | None]:
    inventory_item_id = payload.inventory_item_id
    offline_inventory_record_id = payload.offline_inventory_record_id
    marketplace_listing_draft_id = payload.marketplace_listing_draft_id

    if offline_inventory_record_id is not None:
        offline_row = _get_org_offline_record(
            session,
            organization_id=organization_id,
            offline_inventory_record_id=offline_inventory_record_id,
        )
        if inventory_item_id is None:
            inventory_item_id = offline_row.inventory_item_id
    if marketplace_listing_draft_id is not None:
        listing_row = _get_org_listing_draft(
            session,
            organization_id=organization_id,
            marketplace_listing_draft_id=marketplace_listing_draft_id,
        )
        if inventory_item_id is None:
            inventory_item_id = listing_row.inventory_item_id
    return inventory_item_id, offline_inventory_record_id, marketplace_listing_draft_id


def add_quick_sale_line_item(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    sale_id: int,
    payload: QuickSaleLineItemCreateRequest,
) -> QuickSaleDetailResponse:
    validate_quick_sale_manage_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    sale = _get_org_sale(session, organization_id=organization_id, sale_id=sale_id)
    if sale.mobile_device_id is not None:
        validate_mobile_device_access(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            mobile_device_id=sale.mobile_device_id,
            action="quick_sales:add_line_item",
            require_active_session=True,
            offline_action=sale.sale_source == SALE_SOURCE_OFFLINE,
        )
    if sale.sale_status != SALE_STATUS_DRAFT:
        raise HTTPException(status_code=409, detail="Line items can only be added to draft sales.")

    inventory_item_id, offline_inventory_record_id, marketplace_listing_draft_id = _resolve_line_item_inventory_reference(
        session,
        organization_id=organization_id,
        payload=payload,
    )
    if inventory_item_id is None:
        raise HTTPException(status_code=422, detail="A resolvable inventory item is required for quick-sale line items.")
    if payload.quantity != 1:
        raise HTTPException(status_code=422, detail="Quick-sale line items currently support quantity 1 per inventory item.")

    duplicate = session.exec(
        select(QuickSaleLineItem)
        .where(QuickSaleLineItem.quick_sale_id == sale_id)
        .where(QuickSaleLineItem.inventory_item_id == inventory_item_id)
        .where(QuickSaleLineItem.line_status != LINE_ITEM_STATUS_REMOVED)
        .order_by(QuickSaleLineItem.created_at.asc(), QuickSaleLineItem.id.asc())
    ).first()
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="Inventory item is already attached to this quick sale.")

    reserve_inventory_for_sale(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        sale_id=sale_id,
        inventory_item_id=inventory_item_id,
    )
    unit_price = _money(payload.unit_price)
    discount_amount = _money(payload.discount_amount)
    line_total = _money((unit_price * payload.quantity) - discount_amount)
    row = QuickSaleLineItem(
        organization_id=organization_id,
        quick_sale_id=sale_id,
        inventory_item_id=inventory_item_id,
        offline_inventory_record_id=offline_inventory_record_id,
        marketplace_listing_draft_id=marketplace_listing_draft_id,
        quantity=payload.quantity,
        unit_price=unit_price,
        discount_amount=discount_amount,
        line_total=line_total,
        line_status=LINE_ITEM_STATUS_ADDED,
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    recalculate_sale_totals(session, sale=sale)
    create_quick_sale_event(
        session,
        organization_id=organization_id,
        quick_sale_id=sale_id,
        actor_user_id=actor_user_id,
        event_type="quick_sale_line_item_added",
        event_payload_json={
            "line_item_id": int(row.id or 0),
            "inventory_item_id": inventory_item_id,
            "line_total": line_total,
        },
    )
    session.commit()
    return get_quick_sale(session, organization_id=organization_id, actor_user_id=actor_user_id, sale_id=sale_id)


def remove_quick_sale_line_item(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    sale_id: int,
    line_item_id: int,
) -> QuickSaleDetailResponse:
    validate_quick_sale_manage_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    sale = _get_org_sale(session, organization_id=organization_id, sale_id=sale_id)
    if sale.mobile_device_id is not None:
        validate_mobile_device_access(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            mobile_device_id=sale.mobile_device_id,
            action="quick_sales:remove_line_item",
            require_active_session=True,
            offline_action=sale.sale_source == SALE_SOURCE_OFFLINE,
        )
    if sale.sale_status != SALE_STATUS_DRAFT:
        raise HTTPException(status_code=409, detail="Line items can only be removed from draft sales.")
    row = _get_org_line_item(session, organization_id=organization_id, sale_id=sale_id, line_item_id=line_item_id)
    if not can_transition_line_item_status(row.line_status, LINE_ITEM_STATUS_REMOVED):
        raise HTTPException(status_code=422, detail="Invalid quick-sale line item transition.")
    if row.line_status == LINE_ITEM_STATUS_REMOVED:
        return get_quick_sale(session, organization_id=organization_id, actor_user_id=actor_user_id, sale_id=sale_id)
    if row.inventory_item_id is not None:
        release_inventory_reservation(session, organization_id=organization_id, inventory_item_id=row.inventory_item_id)
    row.line_status = LINE_ITEM_STATUS_REMOVED
    session.add(row)
    recalculate_sale_totals(session, sale=sale)
    create_quick_sale_event(
        session,
        organization_id=organization_id,
        quick_sale_id=sale_id,
        actor_user_id=actor_user_id,
        event_type="quick_sale_line_item_removed",
        event_payload_json={"line_item_id": line_item_id, "inventory_item_id": row.inventory_item_id},
    )
    session.commit()
    return get_quick_sale(session, organization_id=organization_id, actor_user_id=actor_user_id, sale_id=sale_id)


def record_quick_sale_payment(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    sale_id: int,
    payload: QuickSalePaymentCreateRequest,
) -> QuickSaleDetailResponse:
    validate_quick_sale_manage_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    sale = _get_org_sale(session, organization_id=organization_id, sale_id=sale_id)
    if sale.mobile_device_id is not None:
        validate_mobile_device_access(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            mobile_device_id=sale.mobile_device_id,
            action="quick_sales:record_payment",
            require_active_session=True,
            offline_action=sale.sale_source == SALE_SOURCE_OFFLINE,
        )
    if sale.sale_status != SALE_STATUS_DRAFT:
        raise HTTPException(status_code=409, detail="Payments can only be recorded on draft sales.")
    try:
        validate_payment_method(payload.payment_method)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    row = QuickSalePayment(
        organization_id=organization_id,
        quick_sale_id=sale_id,
        payment_method=payload.payment_method,
        payment_status=PAYMENT_STATUS_RECORDED,
        amount=_money(payload.amount),
        currency=payload.currency,
        payment_reference=payload.payment_reference,
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    create_quick_sale_event(
        session,
        organization_id=organization_id,
        quick_sale_id=sale_id,
        actor_user_id=actor_user_id,
        event_type="quick_sale_payment_recorded",
        event_payload_json={
            "payment_id": int(row.id or 0),
            "payment_method": row.payment_method,
            "amount": row.amount,
        },
    )
    session.commit()
    return get_quick_sale(session, organization_id=organization_id, actor_user_id=actor_user_id, sale_id=sale_id)


def reconcile_offline_sale_payload(
    session: Session,
    *,
    sale: QuickSale,
) -> dict[str, Any]:
    line_items = _line_items_for_sale(session, sale_id=int(sale.id or 0))
    payments = _payments_for_sale(session, sale_id=int(sale.id or 0))
    payload = {
        "sale_id": int(sale.id or 0),
        "sale_identifier": sale.sale_identifier,
        "sale_source": sale.sale_source,
        "total_amount": _money(sale.total_amount),
        "currency": sale.currency,
        "line_items": [
            {
                "line_item_id": int(row.id or 0),
                "inventory_item_id": row.inventory_item_id,
                "line_total": _money(row.line_total),
                "line_status": row.line_status,
            }
            for row in line_items
        ],
        "payments": [
            {
                "payment_id": int(row.id or 0),
                "payment_method": row.payment_method,
                "amount": _money(row.amount),
                "payment_status": row.payment_status,
            }
            for row in payments
        ],
    }
    return _json_safe(payload)


def register_offline_sale_change(
    session: Session,
    *,
    organization_id: int,
    sale: QuickSale,
    payload: dict[str, Any],
) -> OfflineInventoryChange | None:
    if sale.mobile_device_id is None:
        return None
    first_inventory_item_id = None
    for row in _line_items_for_sale(session, sale_id=int(sale.id or 0)):
        if row.inventory_item_id is not None:
            first_inventory_item_id = row.inventory_item_id
            break
    change = OfflineInventoryChange(
        organization_id=organization_id,
        device_id=sale.mobile_device_id,
        inventory_item_id=first_inventory_item_id,
        change_type=CHANGE_TYPE_UPDATE,
        change_payload_json=payload,
        created_at=utc_now(),
    )
    session.add(change)
    session.flush()
    return change


def queue_offline_sale_operation(
    session: Session,
    *,
    organization_id: int,
    sale: QuickSale,
    payload: dict[str, Any],
) -> OfflineSyncQueue | None:
    if sale.mobile_device_id is None:
        return None
    queue_row = OfflineSyncQueue(
        organization_id=organization_id,
        device_id=sale.mobile_device_id,
        queue_status=QUEUE_STATUS_PENDING,
        queue_payload_json=payload,
        queued_at=utc_now(),
    )
    session.add(queue_row)
    session.flush()
    return queue_row


def complete_quick_sale(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    sale_id: int,
) -> QuickSaleDetailResponse:
    validate_quick_sale_manage_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    sale = _get_org_sale(session, organization_id=organization_id, sale_id=sale_id)
    if sale.mobile_device_id is not None:
        validate_mobile_device_access(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            mobile_device_id=sale.mobile_device_id,
            action="quick_sales:complete",
            require_active_session=True,
            offline_action=sale.sale_source == SALE_SOURCE_OFFLINE,
        )
    if not can_transition_sale_status(sale.sale_status, SALE_STATUS_COMPLETED):
        raise HTTPException(status_code=422, detail="Quick sale cannot be completed from its current status.")
    line_items = _line_items_for_sale(session, sale_id=sale_id)
    active_lines = [row for row in line_items if row.line_status == LINE_ITEM_STATUS_ADDED]
    if not active_lines:
        raise HTTPException(status_code=422, detail="Quick sale requires at least one active line item.")
    for row in active_lines:
        if not can_transition_line_item_status(row.line_status, LINE_ITEM_STATUS_SOLD):
            raise HTTPException(status_code=422, detail="Invalid quick-sale line item transition.")
        row.line_status = LINE_ITEM_STATUS_SOLD
        session.add(row)
        if row.inventory_item_id is not None:
            mark_inventory_sold_internal(
                session,
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                sale_id=sale_id,
                inventory_item_id=row.inventory_item_id,
            )
    sale.sale_status = SALE_STATUS_COMPLETED
    sale.completed_at = utc_now()
    recalculate_sale_totals(session, sale=sale)
    session.add(sale)
    create_quick_sale_event(
        session,
        organization_id=organization_id,
        quick_sale_id=sale_id,
        actor_user_id=actor_user_id,
        event_type="quick_sale_completed",
        event_payload_json={"total_amount": sale.total_amount, "currency": sale.currency},
    )
    if sale.sale_source == SALE_SOURCE_OFFLINE:
        offline_payload = reconcile_offline_sale_payload(session, sale=sale)
        register_offline_sale_change(session, organization_id=organization_id, sale=sale, payload=offline_payload)
        queue_offline_sale_operation(session, organization_id=organization_id, sale=sale, payload=offline_payload)
        create_quick_sale_event(
            session,
            organization_id=organization_id,
            quick_sale_id=sale_id,
            actor_user_id=actor_user_id,
            event_type="quick_sale_offline_queued",
            event_payload_json={"sale_identifier": sale.sale_identifier},
        )
    session.commit()
    return get_quick_sale(session, organization_id=organization_id, actor_user_id=actor_user_id, sale_id=sale_id)


def void_quick_sale(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    sale_id: int,
) -> QuickSaleDetailResponse:
    validate_quick_sale_manage_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    sale = _get_org_sale(session, organization_id=organization_id, sale_id=sale_id)
    if sale.mobile_device_id is not None:
        validate_mobile_device_access(
            session,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            mobile_device_id=sale.mobile_device_id,
            action="quick_sales:void",
            require_active_session=True,
            offline_action=sale.sale_source == SALE_SOURCE_OFFLINE,
        )
    if not can_transition_sale_status(sale.sale_status, SALE_STATUS_VOIDED):
        raise HTTPException(status_code=422, detail="Quick sale cannot be voided from its current status.")
    for row in _line_items_for_sale(session, sale_id=sale_id):
        if row.line_status == LINE_ITEM_STATUS_ADDED and row.inventory_item_id is not None:
            release_inventory_reservation(session, organization_id=organization_id, inventory_item_id=row.inventory_item_id)
        if row.line_status == LINE_ITEM_STATUS_ADDED:
            row.line_status = LINE_ITEM_STATUS_REMOVED
            session.add(row)
    for payment in _payments_for_sale(session, sale_id=sale_id):
        if can_transition_payment_status(payment.payment_status, PAYMENT_STATUS_VOIDED):
            payment.payment_status = PAYMENT_STATUS_VOIDED
            session.add(payment)
    sale.sale_status = SALE_STATUS_VOIDED
    sale.voided_at = utc_now()
    recalculate_sale_totals(session, sale=sale)
    session.add(sale)
    create_quick_sale_event(
        session,
        organization_id=organization_id,
        quick_sale_id=sale_id,
        actor_user_id=actor_user_id,
        event_type="quick_sale_voided",
        event_payload_json={"sale_identifier": sale.sale_identifier},
    )
    session.commit()
    return get_quick_sale(session, organization_id=organization_id, actor_user_id=actor_user_id, sale_id=sale_id)


def list_quick_sales(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    limit: int,
    offset: int,
) -> QuickSaleListResponse:
    resolution = validate_quick_sale_view_access(session, organization_id=organization_id, actor_user_id=actor_user_id)
    total_count = session.exec(
        select(func.count()).select_from(QuickSale).where(QuickSale.organization_id == organization_id)
    ).one()
    rows = session.exec(
        select(QuickSale)
        .where(QuickSale.organization_id == organization_id)
        .order_by(QuickSale.created_at.asc(), QuickSale.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return QuickSaleListResponse(
        organization_id=organization_id,
        permissions=_permission_response(resolution),
        items=[_sale_response(row) for row in rows],
        total_items=int(total_count),
        limit=limit,
        offset=offset,
    )


def update_quick_sale_line_item(
    session: Session,
    *,
    organization_id: int,
    actor_user_id: int,
    sale_id: int,
    line_item_id: int,
    payload: QuickSaleLineItemUpdateRequest,
) -> QuickSaleDetailResponse:
    try:
        validate_line_item_status(payload.line_status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if payload.line_status != LINE_ITEM_STATUS_REMOVED:
        raise HTTPException(status_code=422, detail="Only line-item removal is supported by this API.")
    return remove_quick_sale_line_item(
        session,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        sale_id=sale_id,
        line_item_id=line_item_id,
    )
