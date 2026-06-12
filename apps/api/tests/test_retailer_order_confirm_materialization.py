"""Confirm Midtown retailer orders materialize inventory with correct quantities."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlmodel import select

from app.models import (
    InventoryCopy,
    Order,
    OrderItem,
    PortfolioItem,
    RetailerAccount,
    RetailerOrderItemSnapshot,
    RetailerOrderSnapshot,
    User,
)
from test_inventory import auth_headers, register_and_login


def _create_account(client, session, token: str, email: str) -> RetailerAccount:
    created = client.post(
        "/api/v1/retailer-accounts",
        headers=auth_headers(token),
        json={
            "retailer": "midtown",
            "username": email,
            "password": "supersafe",
            "display_name": "Midtown Comics",
            "sync_enabled": True,
        },
    )
    assert created.status_code == 201, created.text
    account_id = created.json()["id"]
    return session.exec(select(RetailerAccount).where(RetailerAccount.id == account_id)).one()


def _seed_midtown_order_4272232(session, *, account: RetailerAccount, order_id: int = 4272232) -> RetailerOrderSnapshot:
    line_specs: list[tuple[str, int, Decimal | None, str | None]] = [
        ("Barbara Gordon Breakout #2", 2, Decimal("4.99"), "DC"),
        ("Batman Gargoyle Of Gotham #4", 1, Decimal("5.99"), "DC"),
    ]
    for index in range(3, 28):
        line_specs.append((f"Series Title #{index}", 1, Decimal("3.99"), "Image"))

    order = RetailerOrderSnapshot(
        id=order_id,
        owner_user_id=account.owner_user_id,
        retailer_account_id=int(account.id),
        retailer=account.retailer,
        retailer_order_number="4272232",
        order_date=date(2026, 6, 8),
        order_status="Shipped",
        order_total=Decimal("225.96"),
        source_url="https://www.midtowncomics.com/account/orders/view/4272232",
        raw_snapshot_json={"comicos_review_status": "captured"},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(order)
    session.flush()

    for index, (title, quantity, unit_price, publisher) in enumerate(line_specs, start=1):
        session.add(
            RetailerOrderItemSnapshot(
                owner_user_id=account.owner_user_id,
                retailer_order_snapshot_id=int(order.id),
                retailer=account.retailer,
                retailer_order_number="4272232",
                retailer_item_id=f"4272232-{index:03d}",
                product_url=None,
                image_url=f"https://example.com/cover-{index}.jpg",
                thumbnail_url=f"https://example.com/cover-{index}-thumb.jpg",
                title=title,
                publisher=publisher,
                issue_number=str(index if index > 2 else (2 if index == 1 else 4)),
                cover_name="Cover A",
                variant_type="Regular",
                cover_artist=None,
                quantity=quantity,
                unit_price=unit_price,
                total_price=unit_price * quantity if unit_price is not None else None,
                item_status="Shipped",
                release_date=None,
                raw_item_json={"line": index},
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )
    session.commit()
    session.refresh(order)
    return order


def _expected_total_quantity() -> int:
    return 2 + 1 + 25


def test_confirm_midtown_order_4272232_materializes_inventory(client, session) -> None:
    token = register_and_login(client, "midtown-confirm-4272232@example.com")
    account = _create_account(client, session, token, "midtown-4272232@example.com")
    _seed_midtown_order_4272232(session, account=account, order_id=9004272232)

    before = client.get("/inventory", headers=auth_headers(token))
    assert before.status_code == 200, before.text
    assert before.json()["total"] == 0

    confirmed = client.post("/api/v1/retailer-orders/9004272232/confirm", headers=auth_headers(token))
    assert confirmed.status_code == 200, confirmed.text
    body = confirmed.json()
    assert body["review_status"] == "confirmed"
    assert body["linked_order_id"] is not None
    assert body["inventory_copies_created"] == _expected_total_quantity()
    assert body["total_ordered_quantity"] == _expected_total_quantity()
    assert body["portfolio_items_added"] == _expected_total_quantity()

    order = session.exec(select(Order).where(Order.id == body["linked_order_id"])).one()
    assert order.user_id == account.owner_user_id
    assert order.retailer == "Midtown Comics"

    copies = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == account.owner_user_id)).all()
    assert len(copies) == _expected_total_quantity()

    order_items = session.exec(select(OrderItem).where(OrderItem.order_id == body["linked_order_id"])).all()
    assert len(order_items) == 27
    assert sum(int(row.quantity) for row in order_items) == _expected_total_quantity()

    barbara_rows = [row for row in order_items if row.quantity == 2]
    assert len(barbara_rows) == 1
    gargoyle_rows = [row for row in order_items if row.quantity == 1]
    assert len(gargoyle_rows) == 26

    barbara_copies = session.exec(
        select(InventoryCopy)
        .join(OrderItem, InventoryCopy.order_item_id == OrderItem.id)
        .where(OrderItem.quantity == 2, OrderItem.order_id == body["linked_order_id"])
    ).all()
    assert len(barbara_copies) == 2

    portfolio_items = session.exec(
        select(PortfolioItem).where(PortfolioItem.removed_at.is_(None))
    ).all()
    assert len(portfolio_items) == _expected_total_quantity()

    after = client.get("/inventory", headers=auth_headers(token))
    assert after.status_code == 200, after.text
    assert after.json()["total"] == _expected_total_quantity()

    confirmed_again = client.post("/api/v1/retailer-orders/9004272232/confirm", headers=auth_headers(token))
    assert confirmed_again.status_code == 200, confirmed_again.text
    assert confirmed_again.json()["inventory_copies_created"] == _expected_total_quantity()

    copies_after = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == account.owner_user_id)).all()
    assert len(copies_after) == _expected_total_quantity()


def test_confirm_midtown_order_allows_missing_product_url_and_release_date(client, session) -> None:
    token = register_and_login(client, "midtown-confirm-sparse@example.com")
    account = _create_account(client, session, token, "midtown-sparse@example.com")

    order = RetailerOrderSnapshot(
        owner_user_id=account.owner_user_id,
        retailer_account_id=int(account.id),
        retailer="midtown",
        retailer_order_number="8881001",
        order_date=date(2026, 6, 9),
        order_status="Shipped",
        order_total=Decimal("9.98"),
        raw_snapshot_json={},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(order)
    session.flush()
    session.add(
        RetailerOrderItemSnapshot(
            owner_user_id=account.owner_user_id,
            retailer_order_snapshot_id=int(order.id),
            retailer="midtown",
            retailer_order_number="8881001",
            title="Mystery Comic #1",
            publisher=None,
            issue_number=None,
            quantity=1,
            unit_price=Decimal("9.98"),
            product_url=None,
            release_date=None,
            raw_item_json={},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )
    session.commit()
    session.refresh(order)

    confirmed = client.post(f"/api/v1/retailer-orders/{order.id}/confirm", headers=auth_headers(token))
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["inventory_copies_created"] == 1

    inventory = client.get("/inventory", headers=auth_headers(token))
    assert inventory.status_code == 200, inventory.text
    assert inventory.json()["total"] == 1
