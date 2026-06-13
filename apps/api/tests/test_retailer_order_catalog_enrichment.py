"""Retailer order confirm catalog enrichment."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlmodel import Session, select

from app.models import InventoryCopy, OrderItem, RetailerAccount, RetailerOrderItemSnapshot, RetailerOrderSnapshot
from app.models.external_catalog import ExternalCatalogIssue, ExternalCatalogVariant
from app.services.retailer_order_catalog_enrichment import (
    _is_broken_local_retailer_image,
    enrich_retailer_draft_item_dict,
)
from test_inventory import auth_headers, register_and_login

EXPECTED_LINE_COUNT = 27
EXPECTED_TOTAL_QUANTITY = 41


def test_broken_local_image_detection() -> None:
    assert _is_broken_local_retailer_image("/images/immortal.jpg") is True
    assert _is_broken_local_retailer_image("https://cdn.example.com/cover.jpg") is False


def test_enrich_retailer_draft_item_prefers_catalog_cover_over_local_path(session: Session) -> None:
    issue = ExternalCatalogIssue(
        source_name="locg",
        title="Barbara Gordon Breakout #2",
        publisher="DC",
        series_name="Barbara Gordon Breakout",
        issue_number="2",
        release_date=date(2026, 7, 1),
        cover_image_url="https://catalog.example.com/barbara.jpg",
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)
    session.add(
        ExternalCatalogVariant(
            external_issue_id=int(issue.id),
            cover_label="Cover A",
            image_url="https://catalog.example.com/barbara-cover-a.jpg",
        )
    )
    session.commit()

    item = {
        "publisher": "DC",
        "title": "Barbara Gordon Breakout #2",
        "issue_number": "2",
        "cover_name": "Cover A",
        "variant_type": "Regular",
        "quantity": 1,
        "raw_item_price": "4.99",
        "retailer_cover_url": "/images/order-local/barbara.jpg",
    }
    enriched = enrich_retailer_draft_item_dict(session, owner_user_id=1, item=item)
    assert enriched.get("catalog_match_matched") is True
    assert enriched["cover_image_url"].startswith("https://")
    assert enriched["source_image_url"] == "/images/order-local/barbara.jpg"
    assert enriched["enrichment_status"] == "matched"
    assert enriched.get("parsed_release_date") == "2026-07-01" or enriched.get("release_date")


def test_enrich_unmatched_item_still_returns_needs_review(session: Session) -> None:
    item = {
        "publisher": "Obscure",
        "title": "Unknown Comic ZZZ-999",
        "issue_number": "1",
        "quantity": 1,
        "raw_item_price": "3.99",
        "retailer_cover_url": "/images/missing.jpg",
    }
    enriched = enrich_retailer_draft_item_dict(session, owner_user_id=1, item=item)
    assert enriched["enrichment_status"] == "needs_review"
    assert enriched["source_image_url"] == "/images/missing.jpg"


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
                image_url=f"/images/local/cover-{index}.jpg",
                thumbnail_url=f"/images/local/cover-{index}-thumb.jpg",
                title=title,
                publisher=publisher,
                issue_number=str(2 if index == 1 else 4 if index == 2 else index),
                cover_name="Cover A",
                variant_type="Regular",
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


def test_confirm_midtown_order_4272232_with_catalog_enrichment(client, session) -> None:
    issue = ExternalCatalogIssue(
        source_name="locg",
        title="Barbara Gordon Breakout #2",
        publisher="DC",
        series_name="Barbara Gordon Breakout",
        issue_number="2",
        release_date=date(2026, 7, 15),
        cover_image_url="https://catalog.example.com/barbara-main.jpg",
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)
    session.add(
        ExternalCatalogVariant(
            external_issue_id=int(issue.id),
            cover_label="Cover A",
            image_url="https://catalog.example.com/barbara-a.jpg",
        )
    )
    session.commit()

    token = register_and_login(client, "midtown-enrich-4272232@example.com")
    account = _create_account(client, session, token, "midtown-enrich@example.com")
    _seed_midtown_order_4272232(session, account=account, order_id=9104272232)

    confirmed = client.post("/api/v1/retailer-orders/9104272232/confirm", headers=auth_headers(token))
    assert confirmed.status_code == 200, confirmed.text
    body = confirmed.json()
    assert body["inventory_copies_created"] == EXPECTED_TOTAL_QUANTITY

    order_items = session.exec(select(OrderItem).where(OrderItem.order_id == body["linked_order_id"])).all()
    assert len(order_items) == EXPECTED_LINE_COUNT
    assert sum(int(row.quantity) for row in order_items) == EXPECTED_TOTAL_QUANTITY

    barbara_line = order_items[0]
    assert barbara_line.enrichment_status == "matched"
    assert barbara_line.catalog_match_id == int(issue.id)

    copies = session.exec(
        select(InventoryCopy)
        .join(OrderItem, InventoryCopy.order_item_id == OrderItem.id)
        .where(OrderItem.order_id == body["linked_order_id"])
    ).all()
    assert len(copies) == EXPECTED_TOTAL_QUANTITY
    barbara_copies = session.exec(
        select(InventoryCopy).where(InventoryCopy.order_item_id == barbara_line.id)
    ).all()
    assert len(barbara_copies) == 2
    # Matched item: the resolved catalog (Cover A) cover wins over the broken local
    # retailer image for display.
    assert barbara_copies[0].source_image_url == "https://catalog.example.com/barbara-a.jpg"
    assert barbara_copies[0].release_date == date(2026, 7, 15)

    detail = client.get("/api/v1/retailer-orders/9104272232", headers=auth_headers(token))
    assert detail.status_code == 200
    first_item = detail.json()["items"][0]
    assert first_item["enrichment_status"] == "matched"


def test_confirm_sparse_line_still_imports_with_needs_review(client, session) -> None:
    token = register_and_login(client, "midtown-enrich-sparse@example.com")
    account = _create_account(client, session, token, "midtown-enrich-sparse@example.com")
    order = RetailerOrderSnapshot(
        owner_user_id=account.owner_user_id,
        retailer_account_id=int(account.id),
        retailer="midtown",
        retailer_order_number="8882002",
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
            retailer_order_number="8882002",
            title="Mystery Comic #1",
            publisher=None,
            issue_number=None,
            quantity=1,
            unit_price=Decimal("9.98"),
            product_url=None,
            image_url="/images/mystery.jpg",
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
    order_item = session.exec(
        select(OrderItem).where(OrderItem.order_id == confirmed.json()["linked_order_id"])
    ).one()
    assert order_item.enrichment_status == "needs_review"
