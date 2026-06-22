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
from typing import Any, Callable

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from app.services.legacy_spine_availability import legacy_customer_order_table_exists

from app.models import (
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
from app.services.imports import confirm_import_for_user
from app.services.retailer_draft_import_prep import prepare_draft_import_for_retailer_confirm
from app.services.retailer_order_catalog_enrichment import (
    apply_retailer_enrichment_to_confirmed_order,
    enrich_retailer_draft_import_for_confirm,
)
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
    order_id: int,
    draft_id: int,
) -> None:
    """Run best-effort catalog/cover enrichment against an already-confirmed order.

    Opens its own DB session so it is safe to run on a background thread after the
    confirm request has returned. All failures are logged, never raised.
    """
    from app.db.session import get_engine

    start = time.monotonic()
    logger.info("retailer_confirm_stage start stage=enrichment order_id=%s", order_id)
    try:
        with Session(get_engine()) as bg_session:
            draft = bg_session.get(DraftImport, draft_id)
            if draft is None:
                logger.warning("retailer_confirm_enrichment missing draft draft_id=%s order_id=%s", draft_id, order_id)
                return
            summary = enrich_retailer_draft_import_for_confirm(
                bg_session,
                owner_user_id=owner_user_id,
                draft_import=draft,
            )
            item_snapshots = list_retailer_order_item_snapshots(
                bg_session, order_snapshot_id=order_snapshot_id
            )
            apply_retailer_enrichment_to_confirmed_order(
                bg_session,
                owner_user_id=owner_user_id,
                order_id=order_id,
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
    order_id: int,
    draft_id: int,
) -> None:
    def _task() -> None:
        run_retailer_order_enrichment(
            owner_user_id=owner_user_id,
            order_snapshot_id=order_snapshot_id,
            order_id=order_id,
            draft_id=draft_id,
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
    order_id: int
    inventory_copies_created: int
    total_ordered_quantity: int
    portfolio_items_added: int
    import_id: int | None
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
    order_id: int,
    import_id: int | None,
    portfolio_items_added: int,
    line_debug: tuple[dict, ...] = (),
    enrichment_summary: dict | None = None,
) -> None:
    raw = dict(order.raw_snapshot_json or {})
    raw["comicos_linked_order_id"] = int(order_id)
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


def materialize_retailer_order_inventory(
    session: Session,
    *,
    owner_user_id: int,
    order: RetailerOrderSnapshot,
    account,
) -> RetailerOrderMaterializationResult:
    """Create or reuse order/inventory from a retailer snapshot."""
    item_snapshots = list_retailer_order_item_snapshots(session, order_snapshot_id=int(order.id or 0))
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
        confirm_result = confirm_import_for_user(session, user, int(draft.id))

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
