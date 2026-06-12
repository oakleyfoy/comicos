from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlmodel import select
from test_inventory import auth_headers, register_and_login

from app.models import RetailerAccount, RetailerOrderItemSnapshot, RetailerOrderSnapshot, RetailerSyncRun


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


def _seed_order(
    session,
    *,
    account: RetailerAccount,
    order_id: int,
    order_number: str,
    review_status: str = "captured",
    item_count: int = 2,
    cover_image_count: int | None = None,
    product_url_count: int | None = None,
    price_count: int | None = None,
    release_date_count: int | None = None,
) -> RetailerOrderSnapshot:
    cover_image_count = item_count if cover_image_count is None else cover_image_count
    product_url_count = item_count if product_url_count is None else product_url_count
    price_count = item_count if price_count is None else price_count
    release_date_count = 0 if release_date_count is None else release_date_count
    order = RetailerOrderSnapshot(
        id=order_id,
        owner_user_id=account.owner_user_id,
        retailer_account_id=int(account.id),
        retailer=account.retailer,
        retailer_order_number=order_number,
        order_date=date(2026, 6, 8),
        order_status="Shipped",
        order_total=Decimal("104.79"),
        source_url=f"https://www.midtowncomics.com/account/orders/view/{order_number}",
        raw_snapshot_json={
            "comicos_review_status": review_status,
            "parse_diagnostics": {
                "item_blocks_found": item_count,
                "items_parsed": item_count,
                "items_skipped": 0,
            },
        },
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(order)
    session.flush()
    for index in range(item_count):
        session.add(
            RetailerOrderItemSnapshot(
                owner_user_id=account.owner_user_id,
                retailer_order_snapshot_id=int(order.id),
                retailer=account.retailer,
                retailer_order_number=order_number,
                retailer_item_id=f"SKU-{index + 1}",
                product_url=(
                    f"https://www.midtowncomics.com/product/{index + 1}" if index < product_url_count else None
                ),
                image_url=(f"https://example.com/{index + 1}.jpg" if index < cover_image_count else None),
                thumbnail_url=(f"https://example.com/{index + 1}-thumb.jpg" if index < cover_image_count else None),
                title=f"Immortal Thor #{index + 1} Cover A",
                publisher="Marvel",
                issue_number=f"#{index + 1}",
                cover_name="Cover A",
                variant_type="Regular",
                cover_artist="Artist One",
                quantity=1,
                unit_price=Decimal("4.99") if index < price_count else None,
                total_price=Decimal("4.99") if index < price_count else None,
                item_status="Pending",
                release_date=date(2026, 6, 1 + index) if index < release_date_count else None,
                raw_item_json={"index": index + 1},
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )
    session.commit()
    session.refresh(order)
    return order


def _seed_sync_run(session, *, account: RetailerAccount, order_number: str) -> None:
    session.add(
        RetailerSyncRun(
            owner_user_id=account.owner_user_id,
            retailer_account_id=int(account.id),
            retailer=account.retailer,
            status="succeeded",
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
            orders_seen=1,
            orders_imported=1,
            items_seen=2,
            items_imported=2,
            items_updated=0,
            errors_count=0,
            summary_json={
                "capture_quality_report": [
                    {
                        "retailer_order_number": order_number,
                        "detail_url": f"https://www.midtowncomics.com/account/orders/view/{order_number}",
                        "current_url": f"https://www.midtowncomics.com/account/orders/view/{order_number}",
                        "ready_state": "complete",
                        "items_detected_client_side": 2,
                        "html_length": 4096,
                        "text_length": 2048,
                        "body_inner_html_length": 3072,
                        "body_inner_text_length": 1536,
                        "image_count": 2,
                        "product_link_count": 2,
                        "visible_order_item_block_count": 2,
                        "each_match_count": 2,
                        "qty_match_count": 2,
                        "status_match_count": 2,
                        "scroll_height": 1200,
                        "scroll_position": 0,
                        "parser_item_blocks_found": 2,
                        "parser_items_parsed": 2,
                        "parser_items_skipped": 0,
                    }
                ],
                "parser_quality_report": [
                    {
                        "retailer_order_number": order_number,
                        "order_fields_extracted_count": 5,
                        "order_fields_total": 5,
                        "order_fields_missing": [],
                        "item_blocks_found": 2,
                        "items_parsed": 2,
                        "items_skipped": 0,
                        "skipped_reasons": {},
                        "item_fields_extracted_count": 12,
                        "item_fields_total": 12,
                        "item_fields_missing": [],
                    }
                ],
            },
        )
    )
    session.commit()


def test_retailer_orders_list_detail_and_confirm_flow(client, session) -> None:
    owner_token = register_and_login(client, "retailer-orders-owner@example.com")
    outsider_token = register_and_login(client, "retailer-orders-outsider@example.com")

    owner_account = _create_account(client, session, owner_token, "owner@example.com")
    outsider_account = _create_account(client, session, outsider_token, "outsider@example.com")

    _seed_order(session, account=owner_account, order_id=101, order_number="4272232", item_count=2)
    _seed_order(
        session,
        account=owner_account,
        order_id=102,
        order_number="5550001",
        review_status="confirmed",
        item_count=1,
        cover_image_count=0,
        product_url_count=0,
        price_count=1,
    )
    _seed_order(session, account=outsider_account, order_id=201, order_number="9999999", item_count=1)
    _seed_sync_run(session, account=owner_account, order_number="4272232")
    _seed_sync_run(session, account=owner_account, order_number="5550001")

    listed = client.get("/api/v1/retailer-orders", headers=auth_headers(owner_token))
    assert listed.status_code == 200, listed.text
    assert [item["retailer_order_number"] for item in listed.json()["items"]] == ["5550001", "4272232"]
    assert listed.json()["items"][0]["review_status"] == "confirmed"
    assert listed.json()["items"][1]["item_count"] == 2
    assert listed.json()["items"][1]["cover_image_count"] == 2
    assert listed.json()["items"][1]["product_url_count"] == 2

    filtered = client.get("/api/v1/retailer-orders?status=confirmed", headers=auth_headers(owner_token))
    assert filtered.status_code == 200, filtered.text
    assert [item["retailer_order_number"] for item in filtered.json()["items"]] == ["5550001"]

    detail = client.get("/api/v1/retailer-orders/101", headers=auth_headers(owner_token))
    assert detail.status_code == 200, detail.text
    assert detail.json()["item_count"] == 2
    assert detail.json()["capture_quality_summary_json"]["items_detected_client_side"] == 2
    assert detail.json()["parser_quality_summary_json"]["items_parsed"] == 2
    assert len(detail.json()["items"]) == 2

    forbidden = client.get("/api/v1/retailer-orders/201", headers=auth_headers(owner_token))
    assert forbidden.status_code == 404, forbidden.text

    confirmed = client.post("/api/v1/retailer-orders/101/confirm", headers=auth_headers(owner_token))
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["review_status"] == "confirmed"

    confirmed_again = client.post("/api/v1/retailer-orders/101/confirm", headers=auth_headers(owner_token))
    assert confirmed_again.status_code == 200, confirmed_again.text
    assert confirmed_again.json()["review_status"] == "confirmed"


def test_retailer_orders_detail_returns_all_items(client, session) -> None:
    token = register_and_login(client, "retailer-orders-detail@example.com")
    account = _create_account(client, session, token, "detail@example.com")
    _seed_order(session, account=account, order_id=301, order_number="4272232", item_count=21)
    _seed_sync_run(session, account=account, order_number="4272232")

    detail = client.get("/api/v1/retailer-orders/301", headers=auth_headers(token))
    assert detail.status_code == 200, detail.text
    assert len(detail.json()["items"]) == 21
    assert detail.json()["items"][0]["title"] == "Immortal Thor #1 Cover A"
    assert detail.json()["items"][-1]["title"] == "Immortal Thor #21 Cover A"


_SAVED_MIDTOWN_ORDER_HTML = """
<html>
  <head><title>Order #4272232 - Midtown Comics</title></head>
  <body>
    <h1>Order #4272232</h1>
    <p>Date: 06/08/2026</p>
    <p>Status: Shipped</p>
    <p>Total: $14.98</p>
    <table>
      <tr>
        <td><img src="/images/immortal.jpg" /></td>
        <td><a href="/product/1234/immortal-thor-1-cover-a">Immortal Thor #1 Cover A</a></td>
        <td>Publisher: Marvel</td>
        <td>Qty: 2</td>
        <td>Price: $4.99</td>
        <td>Line Total: $9.98</td>
        <td>Status: Shipped</td>
        <td>SKU: MT-1234</td>
      </tr>
    </table>
  </body>
</html>
"""


def test_import_midtown_order_html_creates_order(client, session) -> None:
    token = register_and_login(client, "midtown-html-upload@example.com")

    response = client.post(
        "/api/v1/retailer-orders/import/midtown-html",
        headers=auth_headers(token),
        files={"file": ("order.html", _SAVED_MIDTOWN_ORDER_HTML.encode("utf-8"), "text/html")},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["retailer_order_number"] == "4272232"
    assert payload["item_count"] == 1
    order_id = payload["order_id"]

    detail = client.get(f"/api/v1/retailer-orders/{order_id}", headers=auth_headers(token))
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["retailer_order_number"] == "4272232"
    assert body["order_total"] == "14.98"
    assert len(body["items"]) == 1
    assert body["items"][0]["title"] == "Immortal Thor #1 Cover A"
    assert body["items"][0]["image_url"] == "https://www.midtowncomics.com/images/immortal.jpg"


def test_import_midtown_order_html_rejects_unparseable_file(client, session) -> None:
    token = register_and_login(client, "midtown-html-bad@example.com")

    response = client.post(
        "/api/v1/retailer-orders/import/midtown-html",
        headers=auth_headers(token),
        files={"file": ("notes.txt", b"<html><body>no order here</body></html>", "text/plain")},
    )
    assert response.status_code == 422, response.text
    assert "order number" in response.text.lower()


def test_import_midtown_order_html_rejects_empty_file(client, session) -> None:
    token = register_and_login(client, "midtown-html-empty@example.com")

    response = client.post(
        "/api/v1/retailer-orders/import/midtown-html",
        headers=auth_headers(token),
        files={"file": ("order.html", b"", "text/html")},
    )
    assert response.status_code == 400, response.text


_NO_ITEMS_MIDTOWN_HTML = """
<html>
  <head><title>Order #4257558 - Midtown Comics</title></head>
  <body>
    <div id="right-contents">
      <div class="info-container">
        <h1>Order #4257558</h1>
        <p>Status: Shipped</p>
        <p>Order Total: $72.86</p>
      </div>
    </div>
  </body>
</html>
"""


def test_import_midtown_order_html_no_items_returns_diagnostics(client, session, tmp_path, monkeypatch) -> None:
    from app.services.retailer_sync import midtown_html_import as import_module

    monkeypatch.setattr(import_module, "MIDTOWN_HTML_FAILURE_ROOT", tmp_path)

    token = register_and_login(client, "midtown-html-no-items@example.com")
    response = client.post(
        "/api/v1/retailer-orders/import/midtown-html",
        headers=auth_headers(token),
        files={
            "file": ("order.html", _NO_ITEMS_MIDTOWN_HTML.encode("utf-8"), "text/html"),
        },
    )
    assert response.status_code == 422, response.text
    payload = response.json()
    assert "error" in payload
    detail = payload["error"]["details"]
    assert detail is not None
    assert "No order items" in payload["error"]["message"]
    diagnostics = detail["diagnostics"]
    assert diagnostics["title"] == "Order #4257558 - Midtown Comics"
    assert diagnostics["order_item_count"] == 0
    assert diagnostics["has_right_contents"] is True
    assert diagnostics["has_info_container"] is True
    assert diagnostics["parsed"]["retailer_order_number"] == "4257558"
    assert diagnostics["parsed"]["items_parsed"] == 0
    assert diagnostics["saved_html_path"]
    assert Path(diagnostics["saved_html_path"]).is_file()


def test_debug_midtown_order_html_import(client, session) -> None:
    token = register_and_login(client, "midtown-html-debug@example.com")
    html = """
    <html><head><title>Order #9999</title></head>
    <body><div id="right-contents"><div class="info-container">
    <div class="order-item"><a href="/product/x">Comic</a></div>
    </div></div></body></html>
    """
    response = client.post(
        "/api/v1/retailer-orders/import/midtown-html/debug",
        headers=auth_headers(token),
        files={"file": ("order.html", html.encode("utf-8"), "text/html")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["title"] == "Order #9999"
    assert body["order_item_count"] == 1
    assert body["has_right_contents"] is True
    assert body["has_info_container"] is True
    assert "Comic" in body["visible_text_excerpt"]

