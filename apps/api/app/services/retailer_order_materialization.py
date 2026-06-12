"""Materialize confirmed retailer orders into customer orders and inventory."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from app.models import (
    DraftImport,
    InventoryCopy,
    Order,
    OrderItem,
    Portfolio,
    PortfolioItem,
    RetailerOrderSnapshot,
    User,
)
from app.services.imports import confirm_import_for_user
from app.services.retailer_draft_import_prep import prepare_draft_import_for_retailer_confirm
from app.services.retailer_sync.retailer_import_enrichment import enrich_drafts_from_retailer_orders


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class RetailerOrderMaterializationResult:
    order_id: int
    inventory_copies_created: int
    total_ordered_quantity: int
    portfolio_items_added: int
    import_id: int | None


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
    return added


def _persist_materialization_on_snapshot(
    session: Session,
    *,
    order: RetailerOrderSnapshot,
    order_id: int,
    import_id: int | None,
    portfolio_items_added: int,
) -> None:
    raw = dict(order.raw_snapshot_json or {})
    raw["comicos_linked_order_id"] = int(order_id)
    if import_id is not None:
        raw["comicos_linked_import_id"] = int(import_id)
    raw["comicos_materialized_at"] = utc_now().isoformat()
    raw["comicos_portfolio_items_added"] = portfolio_items_added
    raw["comicos_import_status"] = "imported"
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
) -> RetailerOrderMaterializationResult:
    portfolio_added = _attach_inventory_to_default_portfolio(
        session,
        owner_user_id=owner_user_id,
        order_id=order_id,
    )
    copies, total_qty = _inventory_stats_for_order(session, owner_user_id=owner_user_id, order_id=order_id)
    _persist_materialization_on_snapshot(
        session,
        order=order,
        order_id=order_id,
        import_id=import_id,
        portfolio_items_added=portfolio_added,
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
    )


def materialize_retailer_order_inventory(
    session: Session,
    *,
    owner_user_id: int,
    order: RetailerOrderSnapshot,
    account,
) -> RetailerOrderMaterializationResult:
    """Create or reuse order/inventory from a retailer snapshot."""
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
        )

    touched = enrich_drafts_from_retailer_orders(
        session,
        account=account,
        order_snapshots=[order],
    )
    if not touched:
        raise HTTPException(status_code=422, detail="Could not build an import draft for this retailer order.")

    draft = _find_import_for_retailer_order(
        session,
        owner_user_id=owner_user_id,
        retailer_order_number=order.retailer_order_number,
    )
    if draft is None:
        draft = session.get(DraftImport, touched[0])
    if draft is None or draft.id is None:
        raise HTTPException(status_code=422, detail="Retailer import draft was not found after enrichment.")

    if draft.status == "confirmed" and draft.linked_order_id:
        return _finalize_existing_order(
            session,
            owner_user_id=owner_user_id,
            order=order,
            order_id=int(draft.linked_order_id),
            import_id=int(draft.id),
        )

    prepare_draft_import_for_retailer_confirm(session, draft)

    user = session.get(User, owner_user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    confirm_result = confirm_import_for_user(session, user, int(draft.id))
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
    _persist_materialization_on_snapshot(
        session,
        order=order,
        order_id=int(confirm_result.order_id),
        import_id=int(confirm_result.import_id),
        portfolio_items_added=portfolio_added,
    )
    raw = dict(order.raw_snapshot_json or {})
    raw["comicos_inventory_copies_created"] = copies
    raw["comicos_total_ordered_quantity"] = total_qty
    order.raw_snapshot_json = raw
    session.add(order)
    session.commit()

    return RetailerOrderMaterializationResult(
        order_id=int(confirm_result.order_id),
        inventory_copies_created=copies,
        total_ordered_quantity=total_qty,
        portfolio_items_added=portfolio_added,
        import_id=int(confirm_result.import_id),
    )
