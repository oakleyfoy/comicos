"""Phase 4: order financial provenance snapshot onto inventory_copy."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlmodel import Session

from app.models import ComicIssue, ComicTitle, InventoryCopy, Order, OrderItem, Publisher, Variant
from app.services.catalog_backfill_service import (
    backfill_order_provenance,
    snapshot_order_provenance_for_copy,
)


def _order_copy(session: Session) -> InventoryCopy:
    pub = Publisher(name="Marvel")
    session.add(pub)
    session.flush()
    title = ComicTitle(publisher_id=pub.id, name="Daredevil")
    session.add(title)
    session.flush()
    issue = ComicIssue(comic_title_id=title.id, issue_number="1")
    session.add(issue)
    session.flush()
    variant = Variant(comic_issue_id=issue.id, cover_name="A")
    session.add(variant)
    session.flush()
    order = Order(
        user_id=1,
        retailer="Midtown Comics",
        order_date=date(2025, 1, 15),
        source_type="online",
        total_amount=Decimal("10.00"),
    )
    session.add(order)
    session.flush()
    order_item = OrderItem(
        order_id=order.id,
        variant_id=variant.id,
        quantity=1,
        raw_item_price=Decimal("3.99"),
        allocated_shipping=Decimal("1.50"),
        allocated_tax=Decimal("0.40"),
        all_in_unit_cost=Decimal("5.89"),
    )
    session.add(order_item)
    session.flush()
    copy = InventoryCopy(
        user_id=1,
        order_item_id=order_item.id,
        variant_id=variant.id,
        copy_number=1,
        acquisition_cost=Decimal("5.89"),
    )
    session.add(copy)
    session.commit()
    session.refresh(copy)
    return copy


def test_snapshot_copies_order_financials(session: Session) -> None:
    copy = _order_copy(session)
    assert snapshot_order_provenance_for_copy(session, copy) is True
    session.commit()
    session.refresh(copy)
    assert copy.order_retailer == "Midtown Comics"
    assert copy.order_date == date(2025, 1, 15)
    assert copy.order_source_type == "online"
    assert copy.order_raw_item_price == Decimal("3.99")
    assert copy.order_shipping_paid == Decimal("1.50")
    assert copy.order_tax_paid == Decimal("0.40")

    # Idempotent: re-running does not overwrite / report a change.
    assert snapshot_order_provenance_for_copy(session, copy) is False


def test_backfill_provenance_report(session: Session) -> None:
    _order_copy(session)
    # A copy with no order graph is skipped.
    session.add(InventoryCopy(user_id=1, copy_number=1, acquisition_cost=Decimal("0")))
    session.commit()

    dry = backfill_order_provenance(session, dry_run=True, user_id=1)
    assert dry.scanned == 2
    assert dry.snapshotted == 1
    assert dry.skipped_no_order == 1

    applied = backfill_order_provenance(session, dry_run=False, user_id=1)
    assert applied.snapshotted == 1

    again = backfill_order_provenance(session, dry_run=False, user_id=1)
    assert again.snapshotted == 0
    assert again.already_snapshotted == 1
