"""Materialize confirmed retailer orders into customer orders and inventory.

Confirm is deliberately split into two phases:

1. A synchronous, fast, local-only phase that creates the customer order and
   inventory copies and commits them. This is what the HTTP request waits on and
   must return within a few seconds even for 13-41 item orders.
2. A best-effort enrichment phase (catalog matching + cover resolution, which can
   make slow external network calls) that runs *after* inventory is durably
   committed. It must never block the confirm response, so it is dispatched through
   a pluggable scheduler that defaults to a fire-and-forget background thread.
"""

from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from app.services.legacy_spine_availability import (
    legacy_comic_issue_table_exists,
    legacy_customer_order_table_exists,
)
from app.services.legacy_customer_orders_policy import legacy_customer_orders_writes_enabled

from app.models import (
    Acquisition,
    DraftImport,
    InventoryCopy,
    Order,
    OrderItem,
    Portfolio,
    PortfolioItem,
    RetailerOrderItemSnapshot,
    RetailerOrderSnapshot,
    User,
)
from app.models.acquisition import ACQUISITION_STATUS_OPEN, ACQUISITION_TYPE_LCS
from app.schemas.ai import ParseOrderResponse
from app.services.acquisition.acquisition_cost_allocation_service import quantize_money
from app.services.acquisition.acquisition_inventory_service import (
    RECEIVED_VIA_RETAILER_ORDER,
    create_received_catalog_copy,
    create_received_placeholder_copy,
)
from app.services.acquisition.acquisition_service import recompute_actual_book_count
from app.services.catalog_issue_link_service import resolve_catalog_issue_link
from app.services.imports import confirm_import_for_user
from app.services.retailer_draft_import_prep import prepare_draft_import_for_retailer_confirm
from app.services.retailer_order_catalog_enrichment import (
    apply_retailer_enrichment_to_confirmed_order,
    enrich_retailer_draft_import_for_confirm,
)
from app.services.retailer_sync.retailer_cover_urls import resolve_retailer_cover_url
from app.services.retailer_order_draft_sync import (
    list_retailer_order_item_snapshots,
    sync_isolated_draft_import_for_retailer_order,
)

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# --- Background enrichment dispatch ------------------------------------------------
#
# Enrichment runs after inventory is committed. The scheduler is pluggable so tests
# can run it synchronously (deterministic) or capture it (to prove the confirm
# response does not wait on it). Production uses a daemon thread with its own DB
# session so slow/blocking catalog lookups can never hold the HTTP response.

EnrichmentTask = Callable[[], None]


def _default_enrichment_scheduler(task: EnrichmentTask) -> None:
    thread = threading.Thread(target=task, name="retailer-order-enrichment", daemon=True)
    thread.start()


_enrichment_scheduler: Callable[[EnrichmentTask], None] = _default_enrichment_scheduler


def set_enrichment_scheduler(scheduler: Callable[[EnrichmentTask], None]) -> None:
    """Override how post-confirm enrichment is dispatched (used by tests)."""
    global _enrichment_scheduler
    _enrichment_scheduler = scheduler


def reset_enrichment_scheduler() -> None:
    global _enrichment_scheduler
    _enrichment_scheduler = _default_enrichment_scheduler


def run_retailer_order_enrichment(
    *,
    owner_user_id: int,
    order_snapshot_id: int,
    draft_id: int,
    order_id: int | None = None,
    acquisition_id: int | None = None,
) -> None:
    """Run best-effort catalog/cover enrichment after confirm (order or acquisition spine)."""
    from app.db.session import get_engine
    from app.services.retailer_order_catalog_enrichment import (
        apply_retailer_enrichment_to_acquisition_inventory,
        apply_retailer_enrichment_to_confirmed_order,
    )

    start = time.monotonic()
    logger.info(
        "retailer_confirm_stage start stage=enrichment order_id=%s acquisition_id=%s",
        order_id,
        acquisition_id,
    )
    try:
        with Session(get_engine()) as bg_session:
            draft = bg_session.get(DraftImport, draft_id)
            if draft is None:
                logger.warning(
                    "retailer_confirm_enrichment missing draft draft_id=%s order_id=%s acquisition_id=%s",
                    draft_id,
                    order_id,
                    acquisition_id,
                )
                return
            summary = enrich_retailer_draft_import_for_confirm(
                bg_session,
                owner_user_id=owner_user_id,
                draft_import=draft,
            )
            item_snapshots = list_retailer_order_item_snapshots(
                bg_session, order_snapshot_id=order_snapshot_id
            )
            if order_id is not None:
                apply_retailer_enrichment_to_confirmed_order(
                    bg_session,
                    owner_user_id=owner_user_id,
                    order_id=order_id,
                    draft_import=draft,
                    item_snapshots=item_snapshots,
                )
            elif acquisition_id is not None:
                apply_retailer_enrichment_to_acquisition_inventory(
                    bg_session,
                    owner_user_id=owner_user_id,
                    acquisition_id=acquisition_id,
                    draft_import=draft,
                    item_snapshots=item_snapshots,
                )
            order = bg_session.get(RetailerOrderSnapshot, order_snapshot_id)
            if order is not None:
                raw = dict(order.raw_snapshot_json or {})
                raw["comicos_enrichment_summary"] = summary.as_dict()
                order.raw_snapshot_json = raw
                order.updated_at = utc_now()
                bg_session.add(order)
            bg_session.commit()
            logger.info(
                "retailer_confirm_stage done stage=enrichment order_id=%s elapsed=%.3fs summary=%s",
                order_id,
                time.monotonic() - start,
                summary.as_dict(),
            )
    except Exception:
        logger.warning(
            "retailer_confirm_stage failed stage=enrichment order_id=%s elapsed=%.3fs",
            order_id,
            time.monotonic() - start,
            exc_info=True,
        )


def _pending_enrichment_summary(total_items: int) -> dict[str, Any]:
    return {
        "status": "pending",
        "total_items": total_items,
        "enriched_items": 0,
        "skipped_items": 0,
        "matched_items": 0,
        "needs_review_items": 0,
        "budget_exceeded": False,
        "elapsed_seconds": 0.0,
    }


def _schedule_retailer_order_enrichment(
    *,
    owner_user_id: int,
    order_snapshot_id: int,
    draft_id: int,
    order_id: int | None = None,
    acquisition_id: int | None = None,
) -> None:
    def _task() -> None:
        run_retailer_order_enrichment(
            owner_user_id=owner_user_id,
            order_snapshot_id=order_snapshot_id,
            draft_id=draft_id,
            order_id=order_id,
            acquisition_id=acquisition_id,
        )

    try:
        _enrichment_scheduler(_task)
    except Exception:
        logger.warning(
            "retailer_confirm_enrichment_schedule_failed order_id=%s",
            order_id,
            exc_info=True,
        )


@contextmanager
def _stage_timer(stage: str, *, order_number: str):
    """Log wall-clock duration of a confirm stage so production hangs are diagnosable."""
    start = time.monotonic()
    logger.info("retailer_confirm_stage start stage=%s order=%s", stage, order_number)
    try:
        yield
    finally:
        elapsed = time.monotonic() - start
        logger.info(
            "retailer_confirm_stage done stage=%s order=%s elapsed=%.3fs",
            stage,
            order_number,
            elapsed,
        )


@dataclass(frozen=True)
class RetailerOrderMaterializationResult:
    inventory_copies_created: int
    total_ordered_quantity: int
    portfolio_items_added: int
    import_id: int | None
    order_id: int | None = None
    acquisition_id: int | None = None
    line_debug: tuple[dict, ...] = ()
    enrichment_summary: dict | None = None


def _draft_contains_retailer_order(draft: DraftImport, retailer_order_number: str) -> bool:
    payload = draft.parsed_payload_json or {}
    if not isinstance(payload, dict):
        return False
    items = payload.get("items")
    if not isinstance(items, list):
        return False
    return any(
        isinstance(item, dict) and item.get("retailer_order_number") == retailer_order_number for item in items
    )


def _find_import_for_retailer_order(
    session: Session,
    *,
    owner_user_id: int,
    retailer_order_number: str,
) -> DraftImport | None:
    imports = session.exec(
        select(DraftImport)
        .where(DraftImport.user_id == owner_user_id)
        .order_by(DraftImport.updated_at.desc(), DraftImport.id.desc())
    ).all()
    for draft in imports:
        if _draft_contains_retailer_order(draft, retailer_order_number):
            return draft
    return None


def _linked_order_id(order: RetailerOrderSnapshot) -> int | None:
    raw = order.raw_snapshot_json or {}
    if not isinstance(raw, dict):
        return None
    value = raw.get("comicos_linked_order_id")
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _linked_acquisition_id(order: RetailerOrderSnapshot) -> int | None:
    raw = order.raw_snapshot_json or {}
    if not isinstance(raw, dict):
        return None
    value = raw.get("comicos_linked_acquisition_id")
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _inventory_stats_for_acquisition(
    session: Session,
    *,
    owner_user_id: int,
    acquisition_id: int,
) -> tuple[int, int]:
    copy_count = int(
        session.exec(
            select(func.count())
            .select_from(InventoryCopy)
            .where(
                InventoryCopy.acquisition_id == acquisition_id,
                InventoryCopy.user_id == owner_user_id,
            )
        ).one()
    )
    return copy_count, copy_count


def _attach_inventory_ids_to_default_portfolio(
    session: Session,
    *,
    owner_user_id: int,
    inventory_ids: list[int],
) -> int:
    if not inventory_ids:
        return 0
    portfolio = _ensure_default_portfolio(session, owner_user_id=owner_user_id)
    portfolio_id = int(portfolio.id or 0)
    added = 0
    for inventory_id in inventory_ids:
        existing = session.exec(
            select(PortfolioItem).where(
                PortfolioItem.portfolio_id == portfolio_id,
                PortfolioItem.inventory_item_id == inventory_id,
                PortfolioItem.removed_at.is_(None),
            )
        ).first()
        if existing is not None:
            continue
        session.add(
            PortfolioItem(
                portfolio_id=portfolio_id,
                inventory_item_id=inventory_id,
                allocation_role="holding",
            )
        )
        added += 1
    if added:
        session.flush()
    return added


def _attach_acquisition_inventory_to_default_portfolio(
    session: Session,
    *,
    owner_user_id: int,
    acquisition_id: int,
) -> int:
    inventory_ids = list(
        session.scalars(
            select(InventoryCopy.id)
            .where(
                InventoryCopy.acquisition_id == acquisition_id,
                InventoryCopy.user_id == owner_user_id,
            )
            .order_by(InventoryCopy.id.asc())
        ).all()
    )
    return _attach_inventory_ids_to_default_portfolio(
        session, owner_user_id=owner_user_id, inventory_ids=inventory_ids
    )


def _mark_retailer_draft_confirmed_without_legacy_order(
    session: Session,
    *,
    draft: DraftImport,
    owner_user_id: int,
    total_copies_created: int,
    total_items: int,
) -> None:
    draft.status = "confirmed"
    draft.linked_order_id = None
    draft.updated_at = utc_now()
    session.add(draft)
    from app.services.p92_guided_import_service import record_import_health_event

    record_import_health_event(
        session,
        owner_user_id=owner_user_id,
        event_type="import_confirmed",
        draft_import_id=int(draft.id or 0),
        payload={
            "total_items": total_items,
            "total_copies_created": total_copies_created,
            "materialization_mode": "acquisition",
        },
    )


def _seller_label_for_retailer_order(*, account, order: RetailerOrderSnapshot) -> str:
    display = getattr(account, "display_name", None)
    if isinstance(display, str) and display.strip():
        return display.strip()
    retailer = (order.retailer or "").strip()
    return retailer or "Retailer"


def _infer_retailer_order_total(
    order: RetailerOrderSnapshot,
    item_snapshots: list[RetailerOrderItemSnapshot],
) -> Decimal:
    if order.order_total is not None:
        return quantize_money(order.order_total)
    subtotal = Decimal("0")
    for snapshot in item_snapshots:
        qty = max(1, int(snapshot.quantity or 0))
        if snapshot.total_price is not None:
            subtotal += quantize_money(snapshot.total_price)
        elif snapshot.unit_price is not None:
            subtotal += quantize_money(snapshot.unit_price) * qty
    return quantize_money(subtotal)


def _create_retailer_order_acquisition(
    session: Session,
    *,
    owner_user_id: int,
    order: RetailerOrderSnapshot,
    account,
    expected_qty: int,
    item_snapshots: list[RetailerOrderItemSnapshot],
) -> Acquisition:
    acquisition = Acquisition(
        user_id=owner_user_id,
        acquisition_type=ACQUISITION_TYPE_LCS,
        purchase_date=order.order_date,
        seller_name=_seller_label_for_retailer_order(account=account, order=order),
        total_paid=_infer_retailer_order_total(order, item_snapshots),
        expected_book_count=expected_qty,
        status=ACQUISITION_STATUS_OPEN,
        notes=f"Retailer order #{order.retailer_order_number}",
    )
    session.add(acquisition)
    session.flush()
    return acquisition


def _materialize_copies_on_acquisition(
    session: Session,
    *,
    acquisition: Acquisition,
    order: RetailerOrderSnapshot,
    account,
    item_snapshots: list[RetailerOrderItemSnapshot],
    draft_items: list,
) -> tuple[list[int], tuple[dict, ...]]:
    """Create inventory copies on an acquisition (unified spine, no customer_order)."""
    owner_user_id = int(acquisition.user_id or 0)
    retailer_key = (order.retailer or account.retailer or "").strip() or None
    inventory_ids: list[int] = []
    lines: list[dict] = []
    for index, snapshot in enumerate(item_snapshots):
        draft_item = draft_items[index] if index < len(draft_items) else None
        title = (snapshot.title or "").strip() or "Unknown Title"
        publisher = (snapshot.publisher or "").strip() or None
        issue_number = (snapshot.issue_number or "").strip() or None
        unit_price = snapshot.unit_price
        if draft_item is not None:
            title = (getattr(draft_item, "title", None) or title).strip() or title
            publisher = (getattr(draft_item, "publisher", None) or publisher) or publisher
            issue_number = (getattr(draft_item, "issue_number", None) or issue_number) or issue_number
            if getattr(draft_item, "raw_item_price", None) is not None:
                unit_price = draft_item.raw_item_price
        qty = int(snapshot.quantity or 0)
        line_copy_ids: list[int] = []
        catalog_link = resolve_catalog_issue_link(
            session,
            series=title,
            issue_number=issue_number,
            publisher=publisher,
        )
        image_url = resolve_retailer_cover_url(
            snapshot.raw_item_json if isinstance(snapshot.raw_item_json, dict) else None,
            retailer=snapshot.retailer,
            fallback_image_url=snapshot.image_url,
            fallback_cover_image_url=snapshot.thumbnail_url,
        )
        if draft_item is not None:
            image_url = (
                getattr(draft_item, "cover_thumbnail_url", None)
                or getattr(draft_item, "cover_image_url", None)
                or getattr(draft_item, "retailer_cover_url", None)
                or image_url
            )
        unit_cost = quantize_money(unit_price)
        for _ in range(qty):
            if catalog_link.catalog_issue_id is not None:
                copy = create_received_catalog_copy(
                    session,
                    acquisition=acquisition,
                    catalog_issue_id=int(catalog_link.catalog_issue_id),
                    series_id=None,
                    issue_number=issue_number,
                    catalog_variant_id=catalog_link.catalog_variant_id,
                    source_image_url=image_url,
                    received_via=RECEIVED_VIA_RETAILER_ORDER,
                )
            else:
                copy = create_received_placeholder_copy(
                    session,
                    acquisition=acquisition,
                    title=title,
                    issue_number=issue_number,
                    publisher=publisher,
                    source_image_url=image_url,
                    received_via=RECEIVED_VIA_RETAILER_ORDER,
                )
            copy.order_retailer = retailer_key
            copy.order_date = order.order_date
            copy.order_source_type = "retailer_account"
            copy.order_raw_item_price = unit_cost
            copy.acquisition_cost = unit_cost
            session.add(copy)
            session.flush()
            copy_id = int(copy.id or 0)
            line_copy_ids.append(copy_id)
            inventory_ids.append(copy_id)
        lines.append(
            {
                "title": snapshot.title,
                "parsed_qty": qty,
                "order_item_qty": qty,
                "copies_created": len(line_copy_ids),
                "retailer_item_id": snapshot.retailer_item_id,
            }
        )
        logger.info(
            "retailer_materialize_acquisition line title=%r parsed_qty=%s copies_created=%s",
            snapshot.title,
            qty,
            len(line_copy_ids),
        )
    recompute_actual_book_count(session, acquisition)
    return inventory_ids, tuple(lines)


def _finalize_existing_acquisition(
    session: Session,
    *,
    owner_user_id: int,
    order: RetailerOrderSnapshot,
    acquisition_id: int,
    import_id: int | None = None,
    item_snapshots: list[RetailerOrderItemSnapshot] | None = None,
) -> RetailerOrderMaterializationResult:
    if item_snapshots is None:
        item_snapshots = list_retailer_order_item_snapshots(session, order_snapshot_id=int(order.id or 0))
    logger.info(
        "retailer_confirm idempotent_recovery order=%s linked_acquisition_id=%s",
        order.retailer_order_number,
        acquisition_id,
    )
    portfolio_added = _attach_acquisition_inventory_to_default_portfolio(
        session,
        owner_user_id=owner_user_id,
        acquisition_id=acquisition_id,
    )
    copies, total_qty = _inventory_stats_for_acquisition(
        session, owner_user_id=owner_user_id, acquisition_id=acquisition_id
    )
    existing_raw = order.raw_snapshot_json if isinstance(order.raw_snapshot_json, dict) else {}
    line_debug_raw = existing_raw.get("comicos_materialization_line_debug")
    line_debug: tuple[dict, ...] = tuple(line_debug_raw) if isinstance(line_debug_raw, list) else ()
    enrichment_summary = existing_raw.get("comicos_enrichment_summary")
    if not isinstance(enrichment_summary, dict):
        enrichment_summary = None
    _persist_materialization_on_snapshot(
        session,
        order=order,
        order_id=None,
        acquisition_id=acquisition_id,
        import_id=import_id,
        portfolio_items_added=portfolio_added,
        line_debug=line_debug,
        enrichment_summary=enrichment_summary,
    )
    raw = dict(order.raw_snapshot_json or {})
    raw["comicos_inventory_copies_created"] = copies
    raw["comicos_total_ordered_quantity"] = total_qty
    order.raw_snapshot_json = raw
    session.add(order)
    session.commit()
    return RetailerOrderMaterializationResult(
        order_id=None,
        acquisition_id=acquisition_id,
        inventory_copies_created=copies,
        total_ordered_quantity=total_qty,
        portfolio_items_added=portfolio_added,
        import_id=import_id,
        line_debug=line_debug,
        enrichment_summary=enrichment_summary,
    )


def _materialize_retailer_order_inventory_acquisition(
    session: Session,
    *,
    owner_user_id: int,
    order: RetailerOrderSnapshot,
    account,
    item_snapshots: list[RetailerOrderItemSnapshot],
) -> RetailerOrderMaterializationResult:
    expected_qty = _expected_quantity_from_snapshots(item_snapshots)
    order_number = order.retailer_order_number

    existing_acquisition_id = _linked_acquisition_id(order)
    if existing_acquisition_id is not None:
        linked = session.get(Acquisition, existing_acquisition_id)
        if linked is not None and linked.user_id == owner_user_id:
            existing_draft = _find_import_for_retailer_order(
                session,
                owner_user_id=owner_user_id,
                retailer_order_number=order.retailer_order_number,
            )
            import_id = int(existing_draft.id) if existing_draft is not None else None
            return _finalize_existing_acquisition(
                session,
                owner_user_id=owner_user_id,
                order=order,
                acquisition_id=existing_acquisition_id,
                import_id=import_id,
                item_snapshots=item_snapshots,
            )

    existing_draft = _find_import_for_retailer_order(
        session,
        owner_user_id=owner_user_id,
        retailer_order_number=order.retailer_order_number,
    )
    if existing_draft is not None and existing_draft.status == "confirmed":
        acq_id = _linked_acquisition_id(order)
        if acq_id is not None:
            return _finalize_existing_acquisition(
                session,
                owner_user_id=owner_user_id,
                order=order,
                acquisition_id=acq_id,
                import_id=int(existing_draft.id or 0),
                item_snapshots=item_snapshots,
            )

    with _stage_timer("draft_sync", order_number=order_number):
        draft = sync_isolated_draft_import_for_retailer_order(
            session,
            account=account,
            order=order,
            item_snapshots=item_snapshots,
        )
    if draft.id is None:
        raise HTTPException(status_code=422, detail="Retailer import draft could not be created.")

    if draft.status == "confirmed":
        acq_id = _linked_acquisition_id(order)
        if acq_id is not None:
            return _finalize_existing_acquisition(
                session,
                owner_user_id=owner_user_id,
                order=order,
                acquisition_id=acq_id,
                import_id=int(draft.id),
                item_snapshots=item_snapshots,
            )

    with _stage_timer("draft_prepare", order_number=order_number):
        prepare_draft_import_for_retailer_confirm(session, draft)

    payload = ParseOrderResponse.model_validate(draft.parsed_payload_json or {})
    draft_items = list(payload.items)

    with _stage_timer("acquisition_inventory_create", order_number=order_number):
        acquisition = _create_retailer_order_acquisition(
            session,
            owner_user_id=owner_user_id,
            order=order,
            account=account,
            expected_qty=expected_qty,
            item_snapshots=item_snapshots,
        )
        inventory_ids, line_debug = _materialize_copies_on_acquisition(
            session,
            acquisition=acquisition,
            order=order,
            account=account,
            item_snapshots=item_snapshots,
            draft_items=draft_items,
        )

    copies = len(inventory_ids)
    total_qty = copies
    _validate_materialized_quantities(
        item_snapshots=item_snapshots,
        copy_count=copies,
        total_qty=total_qty,
        line_debug=line_debug,
    )
    if copies != expected_qty:
        raise HTTPException(
            status_code=422,
            detail=f"Expected {expected_qty} inventory copies for order {order_number}, got {copies}.",
        )

    with _stage_timer("portfolio_creation", order_number=order_number):
        portfolio_added = _attach_inventory_ids_to_default_portfolio(
            session,
            owner_user_id=owner_user_id,
            inventory_ids=inventory_ids,
        )

    _mark_retailer_draft_confirmed_without_legacy_order(
        session,
        draft=draft,
        owner_user_id=owner_user_id,
        total_copies_created=copies,
        total_items=len(item_snapshots),
    )

    enrichment_summary = _pending_enrichment_summary(len(item_snapshots))
    acquisition_id = int(acquisition.id or 0)
    _persist_materialization_on_snapshot(
        session,
        order=order,
        order_id=None,
        acquisition_id=acquisition_id,
        import_id=int(draft.id),
        portfolio_items_added=portfolio_added,
        line_debug=line_debug,
        enrichment_summary=enrichment_summary,
    )
    raw = dict(order.raw_snapshot_json or {})
    raw["comicos_inventory_copies_created"] = copies
    raw["comicos_total_ordered_quantity"] = total_qty
    order.raw_snapshot_json = raw
    session.add(order)
    with _stage_timer("commit", order_number=order_number):
        session.commit()

    _schedule_retailer_order_enrichment(
        owner_user_id=owner_user_id,
        order_snapshot_id=int(order.id or 0),
        draft_id=int(draft.id),
        acquisition_id=acquisition_id,
    )

    return RetailerOrderMaterializationResult(
        order_id=None,
        acquisition_id=acquisition_id,
        inventory_copies_created=copies,
        total_ordered_quantity=total_qty,
        portfolio_items_added=portfolio_added,
        import_id=int(draft.id),
        line_debug=line_debug,
        enrichment_summary=enrichment_summary,
    )


def _inventory_stats_for_order(
    session: Session,
    *,
    owner_user_id: int,
    order_id: int,
) -> tuple[int, int]:
    if not legacy_customer_order_table_exists(session):
        return 0, 0
    copy_count = int(
        session.exec(
            select(func.count())
            .select_from(InventoryCopy)
            .join(OrderItem, InventoryCopy.order_item_id == OrderItem.id)
            .where(OrderItem.order_id == order_id, InventoryCopy.user_id == owner_user_id)
        ).one()
    )
    total_qty = int(
        session.exec(
            select(func.coalesce(func.sum(OrderItem.quantity), 0)).where(OrderItem.order_id == order_id)
        ).one()
    )
    return copy_count, total_qty


def _ensure_default_portfolio(session: Session, *, owner_user_id: int) -> Portfolio:
    portfolio = session.exec(
        select(Portfolio)
        .where(Portfolio.owner_user_id == owner_user_id, Portfolio.status == "ACTIVE")
        .order_by(Portfolio.id.asc())
    ).first()
    if portfolio is not None:
        return portfolio
    portfolio = Portfolio(
        owner_user_id=owner_user_id,
        name="Collection",
        description="Default collection portfolio",
        portfolio_type="collection",
        status="ACTIVE",
        replay_key="default-collection",
    )
    session.add(portfolio)
    session.flush()
    return portfolio


def _attach_inventory_to_default_portfolio(
    session: Session,
    *,
    owner_user_id: int,
    order_id: int,
) -> int:
    if not legacy_customer_order_table_exists(session):
        return 0
    inventory_ids = list(
        session.scalars(
            select(InventoryCopy.id)
            .join(OrderItem, InventoryCopy.order_item_id == OrderItem.id)
            .where(OrderItem.order_id == order_id, InventoryCopy.user_id == owner_user_id)
            .order_by(InventoryCopy.id.asc())
        ).all()
    )
    return _attach_inventory_ids_to_default_portfolio(
        session, owner_user_id=owner_user_id, inventory_ids=inventory_ids
    )


def _expected_quantity_from_snapshots(item_snapshots: list[RetailerOrderItemSnapshot]) -> int:
    return sum(int(snapshot.quantity or 0) for snapshot in item_snapshots)


def _build_materialization_line_debug(
    session: Session,
    *,
    order_id: int,
    item_snapshots: list[RetailerOrderItemSnapshot],
) -> tuple[dict, ...]:
    order_items = session.exec(
        select(OrderItem).where(OrderItem.order_id == order_id).order_by(OrderItem.id.asc())
    ).all()
    if len(order_items) != len(item_snapshots):
        logger.warning(
            "retailer_materialize line count mismatch order_id=%s snapshots=%s order_items=%s",
            order_id,
            len(item_snapshots),
            len(order_items),
        )
    lines: list[dict] = []
    for index, snapshot in enumerate(item_snapshots):
        order_item = order_items[index] if index < len(order_items) else None
        copies_created = 0
        order_item_qty = None
        if order_item is not None:
            order_item_qty = int(order_item.quantity)
            copies_created = int(
                session.exec(
                    select(func.count())
                    .select_from(InventoryCopy)
                    .where(InventoryCopy.order_item_id == order_item.id)
                ).one()
            )
        row = {
            "title": snapshot.title,
            "parsed_qty": int(snapshot.quantity or 0),
            "order_item_qty": order_item_qty,
            "copies_created": copies_created,
            "retailer_item_id": snapshot.retailer_item_id,
        }
        lines.append(row)
        logger.info(
            "retailer_materialize line title=%r parsed_qty=%s order_item_qty=%s copies_created=%s",
            row["title"],
            row["parsed_qty"],
            row["order_item_qty"],
            row["copies_created"],
        )
    return tuple(lines)


def _validate_materialized_quantities(
    *,
    item_snapshots: list[RetailerOrderItemSnapshot],
    copy_count: int,
    total_qty: int,
    line_debug: tuple[dict, ...],
) -> None:
    expected = _expected_quantity_from_snapshots(item_snapshots)
    if copy_count != expected or total_qty != expected:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Retailer order materialization quantity mismatch.",
                "expected_total_quantity": expected,
                "inventory_copy_count": copy_count,
                "order_item_quantity_sum": total_qty,
                "line_debug": list(line_debug),
            },
        )


def _persist_materialization_on_snapshot(
    session: Session,
    *,
    order: RetailerOrderSnapshot,
    import_id: int | None,
    portfolio_items_added: int,
    order_id: int | None = None,
    acquisition_id: int | None = None,
    line_debug: tuple[dict, ...] = (),
    enrichment_summary: dict | None = None,
) -> None:
    raw = dict(order.raw_snapshot_json or {})
    if order_id is not None:
        raw["comicos_linked_order_id"] = int(order_id)
    if acquisition_id is not None:
        raw["comicos_linked_acquisition_id"] = int(acquisition_id)
    if import_id is not None:
        raw["comicos_linked_import_id"] = int(import_id)
    raw["comicos_materialized_at"] = utc_now().isoformat()
    raw["comicos_portfolio_items_added"] = portfolio_items_added
    raw["comicos_import_status"] = "imported"
    if line_debug:
        raw["comicos_materialization_line_debug"] = list(line_debug)
    if enrichment_summary is not None:
        raw["comicos_enrichment_summary"] = enrichment_summary
    order.raw_snapshot_json = raw
    order.updated_at = utc_now()
    session.add(order)


def _finalize_existing_order(
    session: Session,
    *,
    owner_user_id: int,
    order: RetailerOrderSnapshot,
    order_id: int,
    import_id: int | None = None,
    item_snapshots: list[RetailerOrderItemSnapshot] | None = None,
) -> RetailerOrderMaterializationResult:
    if item_snapshots is None:
        item_snapshots = list_retailer_order_item_snapshots(session, order_snapshot_id=int(order.id or 0))
    logger.info(
        "retailer_confirm idempotent_recovery order=%s linked_order_id=%s",
        order.retailer_order_number,
        order_id,
    )
    portfolio_added = _attach_inventory_to_default_portfolio(
        session,
        owner_user_id=owner_user_id,
        order_id=order_id,
    )
    copies, total_qty = _inventory_stats_for_order(session, owner_user_id=owner_user_id, order_id=order_id)
    line_debug = _build_materialization_line_debug(
        session, order_id=order_id, item_snapshots=item_snapshots
    )
    existing_raw = order.raw_snapshot_json if isinstance(order.raw_snapshot_json, dict) else {}
    enrichment_summary = existing_raw.get("comicos_enrichment_summary")
    if not isinstance(enrichment_summary, dict):
        enrichment_summary = None
    _persist_materialization_on_snapshot(
        session,
        order=order,
        order_id=order_id,
        import_id=import_id,
        portfolio_items_added=portfolio_added,
        line_debug=line_debug,
        enrichment_summary=enrichment_summary,
    )
    raw = dict(order.raw_snapshot_json or {})
    raw["comicos_inventory_copies_created"] = copies
    raw["comicos_total_ordered_quantity"] = total_qty
    order.raw_snapshot_json = raw
    session.add(order)
    session.commit()
    return RetailerOrderMaterializationResult(
        order_id=order_id,
        inventory_copies_created=copies,
        total_ordered_quantity=total_qty,
        portfolio_items_added=portfolio_added,
        import_id=import_id,
        line_debug=line_debug,
        enrichment_summary=enrichment_summary,
    )


def _use_acquisition_retailer_materialization(session: Session) -> bool:
    """Use acquisition copies when legacy customer_order writes are retired or spine is gone."""
    if not legacy_customer_order_table_exists(session):
        return True
    if not legacy_customer_orders_writes_enabled():
        return True
    if not legacy_comic_issue_table_exists(session):
        return True
    return False


def materialize_retailer_order_inventory(
    session: Session,
    *,
    owner_user_id: int,
    order: RetailerOrderSnapshot,
    account,
) -> RetailerOrderMaterializationResult:
    """Create or reuse order/inventory from a retailer snapshot."""
    item_snapshots = list_retailer_order_item_snapshots(session, order_snapshot_id=int(order.id or 0))
    if _use_acquisition_retailer_materialization(session):
        return _materialize_retailer_order_inventory_acquisition(
            session,
            owner_user_id=owner_user_id,
            order=order,
            account=account,
            item_snapshots=item_snapshots,
        )

    expected_qty = _expected_quantity_from_snapshots(item_snapshots)

    existing_order_id = _linked_order_id(order)
    if existing_order_id is not None:
        linked = session.get(Order, existing_order_id)
        if linked is not None and linked.user_id == owner_user_id:
            existing_draft = _find_import_for_retailer_order(
                session,
                owner_user_id=owner_user_id,
                retailer_order_number=order.retailer_order_number,
            )
            import_id = int(existing_draft.id) if existing_draft is not None else None
            return _finalize_existing_order(
                session,
                owner_user_id=owner_user_id,
                order=order,
                order_id=existing_order_id,
                import_id=import_id,
                item_snapshots=item_snapshots,
            )

    existing_draft = _find_import_for_retailer_order(
        session,
        owner_user_id=owner_user_id,
        retailer_order_number=order.retailer_order_number,
    )
    if existing_draft is not None and existing_draft.status == "confirmed" and existing_draft.linked_order_id:
        return _finalize_existing_order(
            session,
            owner_user_id=owner_user_id,
            order=order,
            order_id=int(existing_draft.linked_order_id),
            import_id=int(existing_draft.id or 0),
            item_snapshots=item_snapshots,
        )

    order_number = order.retailer_order_number
    with _stage_timer("draft_sync", order_number=order_number):
        draft = sync_isolated_draft_import_for_retailer_order(
            session,
            account=account,
            order=order,
            item_snapshots=item_snapshots,
        )
    if draft.id is None:
        raise HTTPException(status_code=422, detail="Retailer import draft could not be created.")

    if draft.status == "confirmed" and draft.linked_order_id:
        return _finalize_existing_order(
            session,
            owner_user_id=owner_user_id,
            order=order,
            order_id=int(draft.linked_order_id),
            import_id=int(draft.id),
            item_snapshots=item_snapshots,
        )

    with _stage_timer("draft_prepare", order_number=order_number):
        prepare_draft_import_for_retailer_confirm(session, draft)

    user = session.get(User, owner_user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    # Phase 1 (synchronous, fast): create the order + inventory copies. Catalog
    # enrichment is intentionally deferred to phase 2 so slow external lookups can
    # never block inventory creation or the confirm response.
    with _stage_timer("order_inventory_create", order_number=order_number):
        confirm_result = confirm_import_for_user(
            session, user, int(draft.id), bypass_legacy_write_retirement=True
        )

    with _stage_timer("portfolio_creation", order_number=order_number):
        portfolio_added = _attach_inventory_to_default_portfolio(
            session,
            owner_user_id=owner_user_id,
            order_id=int(confirm_result.order_id),
        )
    copies, total_qty = _inventory_stats_for_order(
        session,
        owner_user_id=owner_user_id,
        order_id=int(confirm_result.order_id),
    )
    line_debug = _build_materialization_line_debug(
        session,
        order_id=int(confirm_result.order_id),
        item_snapshots=item_snapshots,
    )
    _validate_materialized_quantities(
        item_snapshots=item_snapshots,
        copy_count=copies,
        total_qty=total_qty,
        line_debug=line_debug,
    )
    if copies != expected_qty:
        raise HTTPException(
            status_code=422,
            detail=f"Expected {expected_qty} inventory copies for order {order_number}, got {copies}.",
        )
    pending_summary = _pending_enrichment_summary(len(item_snapshots))
    _persist_materialization_on_snapshot(
        session,
        order=order,
        order_id=int(confirm_result.order_id),
        import_id=int(confirm_result.import_id),
        portfolio_items_added=portfolio_added,
        line_debug=line_debug,
        enrichment_summary=pending_summary,
    )
    raw = dict(order.raw_snapshot_json or {})
    raw["comicos_inventory_copies_created"] = copies
    raw["comicos_total_ordered_quantity"] = total_qty
    order.raw_snapshot_json = raw
    session.add(order)
    with _stage_timer("commit", order_number=order_number):
        session.commit()

    # Phase 2 (deferred, best-effort): enrich catalog matches + covers off the
    # request path. Dispatched only after inventory is durably committed.
    _schedule_retailer_order_enrichment(
        owner_user_id=owner_user_id,
        order_snapshot_id=int(order.id or 0),
        order_id=int(confirm_result.order_id),
        draft_id=int(draft.id),
    )

    return RetailerOrderMaterializationResult(
        order_id=int(confirm_result.order_id),
        inventory_copies_created=copies,
        total_ordered_quantity=total_qty,
        portfolio_items_added=portfolio_added,
        import_id=int(confirm_result.import_id),
        line_debug=line_debug,
        enrichment_summary=pending_summary,
    )
