from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlmodel import Session, delete, select

from app.models import (
    RetailerAccount,
    RetailerOrderItemSnapshot,
    RetailerOrderSnapshot,
    RetailerSyncRun,
)
from app.services.collection_context import require_active_collection_id_for_user
from app.services.retailer_sync.midtown_parser import (
    MidtownOrderDetail,
    MidtownOrderNumberError,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class RetailerPersistenceSummary:
    orders_seen: int = 0
    orders_imported: int = 0
    items_seen: int = 0
    items_imported: int = 0
    items_updated: int = 0


def _match_existing_item(
    existing_items: list[RetailerOrderItemSnapshot],
    item,
) -> RetailerOrderItemSnapshot | None:
    for existing in existing_items:
        if item.retailer_item_id and existing.retailer_item_id == item.retailer_item_id:
            return existing
        if item.product_url and existing.product_url == item.product_url:
            return existing
        if (
            existing.title == item.title
            and existing.issue_number == item.issue_number
            and existing.cover_name == item.cover_name
            and existing.quantity == item.quantity
        ):
            return existing
    return None


def _validate_retailer_order_number(value: str | None, *, numeric_only: bool = False) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise MidtownOrderNumberError(
            "parser_no_order_number: retailer_order_number is required before persistence."
        )
    if len(cleaned) > 128:
        raise MidtownOrderNumberError(
            "parser_no_order_number: retailer_order_number must be 128 characters or fewer."
        )
    if numeric_only:
        if not re.fullmatch(r"[0-9]+", cleaned):
            raise MidtownOrderNumberError(
                "parser_no_order_number: retailer_order_number must contain only the numeric order id."
            )
    elif not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_\-]*", cleaned):
        raise MidtownOrderNumberError(
            "parser_no_order_number: retailer_order_number may only contain letters, numbers, dashes, "
            "and underscores."
        )
    return cleaned


# Backwards-compatible alias: Midtown order numbers are numeric-only.
def _validate_midtown_order_number(value: str | None) -> str:
    return _validate_retailer_order_number(value, numeric_only=True)


def _apply_item_snapshot(
    existing: RetailerOrderItemSnapshot, *, item, order_snapshot: RetailerOrderSnapshot
) -> None:
    existing.retailer = order_snapshot.retailer
    existing.retailer_order_number = order_snapshot.retailer_order_number
    existing.retailer_item_id = item.retailer_item_id
    existing.product_url = item.product_url
    existing.image_url = item.image_url
    existing.thumbnail_url = item.thumbnail_url
    existing.title = item.title
    existing.publisher = item.publisher
    existing.issue_number = item.issue_number
    existing.cover_name = item.cover_name
    existing.variant_type = item.variant_type
    existing.cover_artist = item.cover_artist
    existing.quantity = item.quantity
    existing.unit_price = item.unit_price
    existing.total_price = item.total_price
    existing.item_status = item.item_status
    existing.release_date = item.release_date
    existing.shipped_qty = item.shipped_qty
    existing.backordered_qty = item.backordered_qty
    existing.unavailable_qty = item.unavailable_qty
    existing.returned_qty = item.returned_qty
    existing.raw_item_json = item.to_dict()
    existing.updated_at = utc_now()


def upsert_retailer_order_snapshots(
    session: Session,
    *,
    account: RetailerAccount,
    sync_run: RetailerSyncRun,
    orders: list[MidtownOrderDetail],
) -> RetailerPersistenceSummary:
    summary = RetailerPersistenceSummary()
    for order in orders:
        summary.orders_seen += 1
        summary.items_seen += len(order.items)
        order_number = _validate_retailer_order_number(
            order.retailer_order_number, numeric_only=(account.retailer == "midtown")
        )
        snapshot = session.exec(
            select(RetailerOrderSnapshot).where(
                RetailerOrderSnapshot.owner_user_id == account.owner_user_id,
                RetailerOrderSnapshot.retailer == account.retailer,
                RetailerOrderSnapshot.retailer_order_number == order_number,
            )
        ).first()
        created = snapshot is None
        if snapshot is None:
            snapshot = RetailerOrderSnapshot(
                owner_user_id=account.owner_user_id,
                collection_id=require_active_collection_id_for_user(session, int(account.owner_user_id)),
                retailer_account_id=account.id,
                retailer=account.retailer,
                retailer_order_number=order_number,
                created_at=utc_now(),
                updated_at=utc_now(),
                raw_snapshot_json={},
            )
        snapshot.retailer_account_id = account.id
        snapshot.order_date = order.order_date
        snapshot.order_status = order.order_status
        snapshot.order_total = order.order_total
        snapshot.source_url = order.detail_url
        snapshot.raw_snapshot_json = order.to_dict()
        snapshot.updated_at = utc_now()
        session.add(snapshot)
        session.flush()
        if created:
            summary.orders_imported += 1

        existing_items = session.exec(
            select(RetailerOrderItemSnapshot).where(
                RetailerOrderItemSnapshot.retailer_order_snapshot_id == snapshot.id
            )
        ).all()
        seen_ids: set[int] = set()
        for parsed_item in order.items:
            existing_item = _match_existing_item(existing_items, parsed_item)
            if existing_item is None:
                existing_item = RetailerOrderItemSnapshot(
                    owner_user_id=account.owner_user_id,
                    retailer_order_snapshot_id=snapshot.id,
                    retailer=account.retailer,
                    retailer_order_number=order_number,
                    title=parsed_item.title,
                    quantity=parsed_item.quantity,
                    raw_item_json={},
                    created_at=utc_now(),
                    updated_at=utc_now(),
                )
                summary.items_imported += 1
                existing_items.append(existing_item)
            else:
                summary.items_updated += 1
                if existing_item.id is not None:
                    seen_ids.add(int(existing_item.id))
            _apply_item_snapshot(existing_item, item=parsed_item, order_snapshot=snapshot)
            session.add(existing_item)
            session.flush()
            if existing_item.id is not None:
                seen_ids.add(int(existing_item.id))

        stale_items = [
            item for item in existing_items if item.id is not None and int(item.id) not in seen_ids
        ]
        if stale_items:
            session.exec(
                delete(RetailerOrderItemSnapshot).where(
                    RetailerOrderItemSnapshot.id.in_([int(item.id) for item in stale_items])
                )
            )

    sync_run.orders_seen = summary.orders_seen
    sync_run.orders_imported = summary.orders_imported
    sync_run.items_seen = summary.items_seen
    sync_run.items_imported = summary.items_imported
    sync_run.items_updated = summary.items_updated
    sync_run.summary_json = {
        "orders_seen": summary.orders_seen,
        "orders_imported": summary.orders_imported,
        "items_seen": summary.items_seen,
        "items_imported": summary.items_imported,
        "items_updated": summary.items_updated,
    }
    session.add(sync_run)
    session.flush()
    return summary
