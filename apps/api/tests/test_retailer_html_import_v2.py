"""Retailer HTML Import v2: parser registry, generic parser, shared pipeline."""

from __future__ import annotations

from sqlmodel import select

from app.models import InventoryCopy, OrderItem, RetailerOrderSnapshot
from app.services.retailer_sync.retailer_html_parsers import (
    GenericRetailerHtmlParser,
    get_retailer_html_parser,
    list_supported_retailers,
    retailer_html_parsers,
)
from test_inventory import auth_headers, register_and_login

_GENERIC_ORDER_HTML = """
<html>
  <head><title>Your Order Confirmation</title></head>
  <body>
    <h1>Order #ABC-1001</h1>
    <table>
      <tr><th>Item</th><th>Qty</th><th>Price</th></tr>
      <tr>
        <td><a href="https://shop.example.com/p/saga-1">Saga #1 (Image)</a></td>
        <td>2</td>
        <td>$3.99</td>
      </tr>
      <tr>
        <td>Batman #500 Cover A (DC Comics)</td>
        <td>1</td>
        <td>$5.99</td>
      </tr>
    </table>
    <p>Order Total: $13.97</p>
  </body>
</html>
"""

_NO_ITEMS_HTML = "<html><head><title>Order #X9</title></head><body><p>Nothing here.</p></body></html>"


def test_registry_contains_all_supported_retailers() -> None:
    assert set(retailer_html_parsers) == {"midtown", "dcbs", "third_eye", "mycomicshop", "unknown"}
    assert retailer_html_parsers["midtown"].status == "supported"
    assert retailer_html_parsers["dcbs"].status == "beta"
    assert isinstance(retailer_html_parsers["unknown"], GenericRetailerHtmlParser)


def test_list_supported_retailers_catalog() -> None:
    cards = {card["key"]: card for card in list_supported_retailers()}
    assert cards["midtown"]["supported"] is True
    assert cards["dcbs"]["supported"] is False
    assert cards["dcbs"]["status"] == "beta"
    assert cards["unknown"]["is_fallback"] is True
    assert all(card["accepts_upload"] for card in cards.values())


def test_generic_parser_extracts_normalized_items() -> None:
    parser = get_retailer_html_parser("unknown")
    detail = parser.parse(_GENERIC_ORDER_HTML)
    assert detail.retailer_order_number == "ABC-1001"
    titles = {item.title: item for item in detail.items}
    # Parenthetical notes are stripped from stored titles across all parsers.
    assert "Saga #1" in titles
    assert "Batman #500 Cover A" in titles
    saga = titles["Saga #1"]
    assert saga.quantity == 2
    assert str(saga.unit_price) == "3.99"
    assert saga.publisher == "Image"
    assert saga.product_url == "https://shop.example.com/p/saga-1"
    batman = titles["Batman #500 Cover A"]
    assert batman.issue_number == "500"
    assert batman.cover_name == "Cover A"


def test_import_retailers_catalog_endpoint(client) -> None:
    token = register_and_login(client, "html-v2-catalog@example.com")
    response = client.get("/api/v1/retailer-orders/import/retailers", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    items = {card["key"]: card for card in response.json()["items"]}
    assert items["midtown"]["status"] == "supported"
    assert items["third_eye"]["status"] == "beta"
    assert items["unknown"]["is_fallback"] is True


def test_import_generic_retailer_html_creates_order(client, session) -> None:
    token = register_and_login(client, "html-v2-generic@example.com")
    response = client.post(
        "/api/v1/retailer-orders/import/html",
        headers=auth_headers(token),
        data={"retailer": "unknown"},
        files={"file": ("order.html", _GENERIC_ORDER_HTML.encode("utf-8"), "text/html")},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["retailer"] == "unknown"
    assert payload["retailer_order_number"] == "ABC-1001"
    assert payload["item_count"] == 2

    detail = client.get(
        f"/api/v1/retailer-orders/{payload['order_id']}", headers=auth_headers(token)
    )
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["retailer"] == "unknown"
    assert len(body["items"]) == 2


def test_import_beta_retailer_html_emits_warning(client, session) -> None:
    token = register_and_login(client, "html-v2-dcbs@example.com")
    response = client.post(
        "/api/v1/retailer-orders/import/html",
        headers=auth_headers(token),
        data={"retailer": "dcbs"},
        files={"file": ("dcbs-order.html", _GENERIC_ORDER_HTML.encode("utf-8"), "text/html")},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["retailer"] == "dcbs"
    assert payload["parser_status"] == "beta"
    assert any("beta" in warning.lower() for warning in payload["warnings"])


def test_import_html_rejects_unknown_retailer(client) -> None:
    token = register_and_login(client, "html-v2-bad-retailer@example.com")
    response = client.post(
        "/api/v1/retailer-orders/import/html",
        headers=auth_headers(token),
        data={"retailer": "not-a-retailer"},
        files={"file": ("order.html", _GENERIC_ORDER_HTML.encode("utf-8"), "text/html")},
    )
    assert response.status_code == 422, response.text
    assert "unsupported retailer" in response.text.lower()


def test_import_html_no_items_returns_diagnostics(client) -> None:
    token = register_and_login(client, "html-v2-noitems@example.com")
    response = client.post(
        "/api/v1/retailer-orders/import/html",
        headers=auth_headers(token),
        data={"retailer": "unknown"},
        files={"file": ("order.html", _NO_ITEMS_HTML.encode("utf-8"), "text/html")},
    )
    assert response.status_code == 422, response.text
    assert "no order items" in response.text.lower()


def test_import_midtown_via_generic_endpoint_uses_midtown_flow(client, session) -> None:
    token = register_and_login(client, "html-v2-midtown@example.com")
    from test_retailer_orders_api import _SAVED_MIDTOWN_ORDER_HTML

    response = client.post(
        "/api/v1/retailer-orders/import/html",
        headers=auth_headers(token),
        data={"retailer": "midtown"},
        files={"file": ("order.html", _SAVED_MIDTOWN_ORDER_HTML.encode("utf-8"), "text/html")},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["retailer"] == "midtown"
    assert payload["retailer_order_number"] == "4272232"
    assert payload["parser_status"] == "supported"


def test_generic_retailer_order_confirms_and_materializes(client, session) -> None:
    """Confirm/materialization is shared: a generic upload creates inventory copies."""
    token = register_and_login(client, "html-v2-confirm@example.com")
    response = client.post(
        "/api/v1/retailer-orders/import/html",
        headers=auth_headers(token),
        data={"retailer": "unknown"},
        files={"file": ("order.html", _GENERIC_ORDER_HTML.encode("utf-8"), "text/html")},
    )
    assert response.status_code == 201, response.text
    order_id = response.json()["order_id"]

    confirmed = client.post(
        f"/api/v1/retailer-orders/{order_id}/confirm", headers=auth_headers(token)
    )
    assert confirmed.status_code == 200, confirmed.text
    body = confirmed.json()
    assert body["review_status"] == "confirmed"
    assert body["linked_order_id"] is not None
    # Two lines, quantities 2 + 1 = 3 inventory copies.
    assert body["inventory_copies_created"] == 3

    copies = session.exec(
        select(InventoryCopy)
        .join(OrderItem, InventoryCopy.order_item_id == OrderItem.id)
        .where(OrderItem.order_id == body["linked_order_id"])
    ).all()
    assert len(copies) == 3

    snapshot = session.get(RetailerOrderSnapshot, order_id)
    assert snapshot is not None
    assert snapshot.retailer == "unknown"
