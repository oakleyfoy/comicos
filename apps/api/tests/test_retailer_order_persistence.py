from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlmodel import select

from app.models import (
    RetailerAccount,
    RetailerOrderItemSnapshot,
    RetailerOrderSnapshot,
    RetailerSyncRun,
    User,
)
from app.services.retailer_sync.midtown_parser import (
    MidtownOrderDetail,
    MidtownOrderItem,
    MidtownOrderNumberError,
    parse_midtown_order_detail,
)
from app.services.retailer_sync.retailer_order_persistence import upsert_retailer_order_snapshots


def test_upsert_retailer_order_snapshots_creates_and_updates_rows(session) -> None:
    user = User(email="retailer-persist@example.com", password_hash="hash")
    session.add(user)
    session.commit()
    session.refresh(user)

    account = RetailerAccount(
        owner_user_id=int(user.id),
        retailer="midtown",
        display_name="Midtown Comics",
        username="collector@example.com",
        encrypted_password="encrypted",
        credential_version=1,
        status="connected",
        sync_enabled=True,
    )
    session.add(account)
    session.commit()
    session.refresh(account)

    sync_run = RetailerSyncRun(
        owner_user_id=int(user.id),
        retailer_account_id=int(account.id),
        retailer="midtown",
        status="running",
        summary_json={},
    )
    session.add(sync_run)
    session.commit()
    session.refresh(sync_run)

    orders = [
        MidtownOrderDetail(
            retailer_order_number="4272232",
            order_date=date(2026, 6, 8),
            order_status="Shipped",
            order_total=Decimal("9.98"),
            detail_url="https://www.midtowncomics.com/account/orders/view/4272232",
            items=[
                MidtownOrderItem(
                    retailer_item_id="SKU-1",
                    product_url="https://www.midtowncomics.com/product/1234/immortal-thor-1-cover-a",
                    image_url="https://img.example/immortal.jpg",
                    thumbnail_url="https://img.example/immortal-thumb.jpg",
                    title="Immortal Thor #1 Cover A",
                    publisher="Marvel",
                    issue_number="1",
                    cover_name="Cover A",
                    quantity=2,
                    unit_price=Decimal("4.99"),
                    total_price=Decimal("9.98"),
                    item_status="Shipped",
                    shipped_qty=2,
                )
            ],
        )
    ]
    summary = upsert_retailer_order_snapshots(
        session, account=account, sync_run=sync_run, orders=orders
    )
    session.commit()

    assert summary.orders_seen == 1
    assert summary.orders_imported == 1
    assert summary.items_imported == 1

    snapshot = session.exec(select(RetailerOrderSnapshot)).one()
    assert snapshot.retailer_order_number == "4272232"
    item = session.exec(select(RetailerOrderItemSnapshot)).one()
    assert item.quantity == 2
    assert item.image_url == "https://img.example/immortal.jpg"

    orders[0].items[0].quantity = 3
    orders[0].items[0].total_price = Decimal("14.97")
    second = upsert_retailer_order_snapshots(
        session, account=account, sync_run=sync_run, orders=orders
    )
    session.commit()

    assert second.items_updated >= 1
    item = session.exec(select(RetailerOrderItemSnapshot)).one()
    assert item.quantity == 3
    assert item.total_price == Decimal("14.97")


def test_upsert_retailer_order_snapshots_rejects_overlong_order_number_before_insert(session) -> None:
    user = User(email="retailer-persist-long@example.com", password_hash="hash")
    session.add(user)
    session.commit()
    session.refresh(user)

    account = RetailerAccount(
        owner_user_id=int(user.id),
        retailer="midtown",
        display_name="Midtown Comics",
        username="collector@example.com",
        encrypted_password="encrypted",
        credential_version=1,
        status="connected",
        sync_enabled=True,
    )
    session.add(account)
    session.commit()
    session.refresh(account)

    sync_run = RetailerSyncRun(
        owner_user_id=int(user.id),
        retailer_account_id=int(account.id),
        retailer="midtown",
        status="running",
        summary_json={},
    )
    session.add(sync_run)
    session.commit()
    session.refresh(sync_run)

    orders = [
        MidtownOrderDetail(
            retailer_order_number="9" * 129,
            order_date=date(2026, 6, 8),
            order_status="Shipped",
            order_total=Decimal("9.98"),
            detail_url="https://www.midtowncomics.com/account/orders/view/9999999",
            items=[],
        )
    ]

    with pytest.raises(MidtownOrderNumberError) as exc_info:
        upsert_retailer_order_snapshots(
            session, account=account, sync_run=sync_run, orders=orders
        )

    assert "parser_no_order_number" in str(exc_info.value)
    assert session.exec(select(RetailerOrderSnapshot)).all() == []


def test_upsert_retailer_order_snapshots_handles_midtown_failing_payload(session) -> None:
    user = User(email="retailer-persist-midtown@example.com", password_hash="hash")
    session.add(user)
    session.commit()
    session.refresh(user)

    account = RetailerAccount(
        owner_user_id=int(user.id),
        retailer="midtown",
        display_name="Midtown Comics",
        username="collector@example.com",
        encrypted_password="encrypted",
        credential_version=1,
        status="connected",
        sync_enabled=True,
    )
    session.add(account)
    session.commit()
    session.refresh(account)

    sync_run = RetailerSyncRun(
        owner_user_id=int(user.id),
        retailer_account_id=int(account.id),
        retailer="midtown",
        status="running",
        summary_json={},
    )
    session.add(sync_run)
    session.commit()
    session.refresh(sync_run)

    fixture_path = (
        Path(__file__).resolve().parent / "fixtures" / "midtown" / "order_4272232_detail.html"
    )
    html = fixture_path.read_text(encoding="utf-8")
    order = parse_midtown_order_detail(
        html,
        detail_url="https://www.midtowncomics.com/account/orders/view/4272232",
    )
    summary = upsert_retailer_order_snapshots(session, account=account, sync_run=sync_run, orders=[order])
    session.commit()

    assert summary.orders_seen == 1
    assert summary.orders_imported == 1
    snapshot = session.exec(select(RetailerOrderSnapshot)).one()
    assert snapshot.retailer_order_number == "4272232"
    assert snapshot.order_status == "Shipped"
    assert len(snapshot.raw_snapshot_json["items"]) == 21
    assert snapshot.raw_snapshot_json["items"][0]["title"] == "Absolute Batman #1 Cover A"
    assert snapshot.raw_snapshot_json["items"][-1]["title"] == "Absolute Batman #21 Cover C"
    assert snapshot.raw_snapshot_json["parse_diagnostics"]["items_parsed"] == 21
