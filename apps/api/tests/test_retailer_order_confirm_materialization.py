"""Confirm Midtown retailer orders materialize inventory with correct quantities."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlmodel import select

from app.models import (
    DraftImport,
    InventoryCopy,
    Order,
    OrderItem,
    PortfolioItem,
    RetailerAccount,
    RetailerOrderItemSnapshot,
    RetailerOrderSnapshot,
    User,
)
from app.schemas.ai import AiDraftOrderItem, ParseOrderResponse
from test_inventory import auth_headers, register_and_login

EXPECTED_LINE_COUNT = 27
EXPECTED_TOTAL_QUANTITY = 41


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
    for index in range(3, 16):
        line_specs.append((f"Series Title #{index}", 2, Decimal("3.99"), "Image"))
    for index in range(16, 28):
        line_specs.append((f"Series Title #{index}", 1, Decimal("3.99"), "Image"))
    assert len(line_specs) == EXPECTED_LINE_COUNT
    assert sum(qty for _, qty, _, _ in line_specs) == EXPECTED_TOTAL_QUANTITY

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
                issue_number=str(2 if index == 1 else 4 if index == 2 else index),
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


def test_confirm_midtown_order_4272232_materializes_inventory(client, session) -> None:
    token = register_and_login(client, "midtown-confirm-4272232@example.com")
    account = _create_account(client, session, token, "midtown-4272232@example.com")
    _seed_midtown_order_4272232(session, account=account, order_id=9004272232)

    confirmed = client.post("/api/v1/retailer-orders/9004272232/confirm", headers=auth_headers(token))
    assert confirmed.status_code == 200, confirmed.text
    body = confirmed.json()
    assert body["review_status"] == "confirmed"
    assert body["linked_order_id"] is not None
    assert body["inventory_copies_created"] == EXPECTED_TOTAL_QUANTITY
    assert body["total_ordered_quantity"] == EXPECTED_TOTAL_QUANTITY
    assert body["portfolio_items_added"] == EXPECTED_TOTAL_QUANTITY
    assert len(body.get("materialization_line_debug") or []) == EXPECTED_LINE_COUNT
    for row in body["materialization_line_debug"]:
        assert row["parsed_qty"] == row["order_item_qty"] == row["copies_created"]

    order_items = session.exec(select(OrderItem).where(OrderItem.order_id == body["linked_order_id"])).all()
    assert len(order_items) == EXPECTED_LINE_COUNT
    assert sum(int(row.quantity) for row in order_items) == EXPECTED_TOTAL_QUANTITY

    copies = session.exec(
        select(InventoryCopy)
        .join(OrderItem, InventoryCopy.order_item_id == OrderItem.id)
        .where(OrderItem.order_id == body["linked_order_id"])
    ).all()
    assert len(copies) == EXPECTED_TOTAL_QUANTITY

    debug_by_title = {row["title"]: row for row in body["materialization_line_debug"]}
    assert debug_by_title["Barbara Gordon Breakout #2"]["copies_created"] == 2
    assert debug_by_title["Batman Gargoyle Of Gotham #4"]["copies_created"] == 1

    copy_ids = {int(c.id) for c in copies}
    portfolio_items = session.exec(
        select(PortfolioItem).where(
            PortfolioItem.removed_at.is_(None),
            PortfolioItem.inventory_item_id.in_(copy_ids),
        )
    ).all()
    assert len(portfolio_items) == EXPECTED_TOTAL_QUANTITY

    confirmed_again = client.post("/api/v1/retailer-orders/9004272232/confirm", headers=auth_headers(token))
    assert confirmed_again.status_code == 200, confirmed_again.text
    assert confirmed_again.json()["portfolio_items_added"] == 0
    copies_after = session.exec(
        select(InventoryCopy)
        .join(OrderItem, InventoryCopy.order_item_id == OrderItem.id)
        .where(OrderItem.order_id == body["linked_order_id"])
    ).all()
    assert len(copies_after) == EXPECTED_TOTAL_QUANTITY


def test_confirm_midtown_order_ignores_unrelated_draft_lines(client, session) -> None:
    token = register_and_login(client, "midtown-confirm-mixed-draft@example.com")
    user = session.exec(select(User).where(User.email == "midtown-confirm-mixed-draft@example.com")).one()
    account = _create_account(client, session, token, "midtown-mixed@example.com")
    _seed_midtown_order_4272232(session, account=account, order_id=9004272233)

    polluted = DraftImport(
        user_id=int(user.id),
        raw_text="mixed draft",
        parsed_payload_json=ParseOrderResponse(
            retailer="Midtown Comics",
            order_date=date(2026, 6, 1),
            source_type="retailer_account",
            items=[
                AiDraftOrderItem(
                    title="Other Order Book",
                    publisher="Marvel",
                    issue_number="1",
                    quantity=22,
                    raw_item_price=Decimal("1.00"),
                    retailer_order_number="9999999",
                ),
                AiDraftOrderItem(
                    title="Barbara Gordon Breakout #2",
                    publisher="DC",
                    issue_number="2",
                    quantity=2,
                    raw_item_price=Decimal("4.99"),
                    retailer_order_number="4272232",
                ),
            ],
        ).model_dump(mode="json"),
        confidence_score=Decimal("1.0"),
        status="draft",
    )
    session.add(polluted)
    session.commit()

    confirmed = client.post("/api/v1/retailer-orders/9004272233/confirm", headers=auth_headers(token))
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["inventory_copies_created"] == EXPECTED_TOTAL_QUANTITY
    assert confirmed.json()["total_ordered_quantity"] == EXPECTED_TOTAL_QUANTITY


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


def test_confirm_with_slow_enrichment_stays_fast_and_is_idempotent(client, session, monkeypatch) -> None:
    """Slow catalog enrichment must never block inventory creation or hang the request."""
    import time as _time

    from app.services import retailer_order_catalog_enrichment as enrichment_module

    token = register_and_login(client, "midtown-confirm-slow@example.com")
    account = _create_account(client, session, token, "midtown-slow@example.com")
    _seed_midtown_order_4272232(session, account=account, order_id=9004272240)

    # Cap the per-order enrichment budget and make each line enrichment slow so the
    # budget is exceeded almost immediately. Remaining lines should be skipped.
    monkeypatch.setattr(enrichment_module, "DEFAULT_ENRICH_TIME_BUDGET_SECONDS", 0.5)

    original_enrich = enrichment_module.enrich_retailer_draft_item_dict

    def _slow_enrich(session, *, owner_user_id, item):
        _time.sleep(0.6)
        return original_enrich(session, owner_user_id=owner_user_id, item=item)

    monkeypatch.setattr(enrichment_module, "enrich_retailer_draft_item_dict", _slow_enrich)

    started = _time.perf_counter()
    confirmed = client.post("/api/v1/retailer-orders/9004272240/confirm", headers=auth_headers(token))
    elapsed = _time.perf_counter() - started

    assert confirmed.status_code == 200, confirmed.text
    assert elapsed < 15.0, f"confirm took {elapsed:.2f}s (enrichment must be time-boxed)"

    body = confirmed.json()
    assert body["review_status"] == "confirmed"
    assert body["linked_order_id"] is not None
    assert body["inventory_copies_created"] == EXPECTED_TOTAL_QUANTITY
    assert body["portfolio_items_added"] == EXPECTED_TOTAL_QUANTITY
    summary = body.get("enrichment_summary")
    assert summary is not None
    assert summary["budget_exceeded"] is True
    assert summary["skipped_items"] >= 1
    assert summary["enriched_items"] + summary["skipped_items"] == EXPECTED_LINE_COUNT

    # Second confirm is idempotent: no new copies, no duplicate portfolio items.
    confirmed_again = client.post("/api/v1/retailer-orders/9004272240/confirm", headers=auth_headers(token))
    assert confirmed_again.status_code == 200, confirmed_again.text
    assert confirmed_again.json()["portfolio_items_added"] == 0

    copies_after = session.exec(
        select(InventoryCopy)
        .join(OrderItem, InventoryCopy.order_item_id == OrderItem.id)
        .where(OrderItem.order_id == body["linked_order_id"])
    ).all()
    assert len(copies_after) == EXPECTED_TOTAL_QUANTITY
