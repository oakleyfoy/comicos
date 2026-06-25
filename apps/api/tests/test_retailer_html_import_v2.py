"""Retailer HTML Import v2: parser registry, generic parser, shared pipeline."""

from __future__ import annotations

import json
from datetime import date
from unittest.mock import patch

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

_DCBS_ORDER_TABLE_HTML = """
<html>
  <head><title>Order #970668 Detail - Discount Comic Book Service</title></head>
  <body>
    <a href="https://www.dcbservice.com/products/dc-comics/1">DC Comics</a>
    <a href="https://www.dcbservice.com/products/marvel-comics/4">Marvel Comics</a>
    <h2>Order ID: 970668</h2>
    <table>
      <tr>
        <th>Product</th><th>Qty</th><th>Price</th><th>Total</th><th>Status</th>
      </tr>
      <tr>
        <td class="compactoff"><img alt="X-Men #34 Inhyuk Lee Marvel Snap Swimsuit Variant" class="cartimg" src="/files/MAY265025.jpg"></td>
        <td>X-Men #34 Inhyuk Lee Marvel Snap Swimsuit Variant<div class="productcode">MAY265025</div></td>
        <td class="centered">1</td>
        <td class="currency">$3.19</td>
        <td class="currency">$3.19</td>
        <td class="centered"><img alt="Processing" class="statusimg" src="/processing.png"></td>
      </tr>
      <tr>
        <td class="compactoff"><img alt="Spectacular Spider-Man Brand New Day #3" class="cartimg" src="/files/MAY264642.jpg"></td>
        <td>Spectacular Spider-Man Brand New Day #3<div class="productcode">MAY264642</div></td>
        <td class="centered">2</td>
        <td class="currency">$3.19</td>
        <td class="currency">$6.38</td>
        <td class="centered"><img alt="Processing" class="statusimg" src="/processing.png"></td>
      </tr>
    </table>
    <p>Order Total: $9.57</p>
  </body>
</html>
"""

_THIRD_EYE_SHOPIFY_HTML = """
<html>
  <head><title>Order #973967</title></head>
  <body>
    <h1>Order 973967</h1>
    <table class="order-list">
      <tbody>
        <tr>
          <td class="order-list__item-description">
            <a href="https://www.thirdeyecomics.com/products/gehenna-in-tokyo-1-cvr-a-shimizu">
              Gehenna In Tokyo #1 (CVR A Shimizu)
            </a>
          </td>
          <td class="order-list__item-quantity">1</td>
          <td class="order-list__item-price">$3.59 USD /ea</td>
        </tr>
        <tr>
          <td class="order-list__item-description">
            <a href="https://www.thirdeyecomics.com/products/spider-man-1">Amazing Spider-Man #1</a>
          </td>
          <td>2</td>
          <td>$4.99 USD /ea</td>
        </tr>
      </tbody>
    </table>
    <p>Order Total: $13.97</p>
  </body>
</html>
"""


_THIRD_EYE_CUSTOMER_ACCOUNT_HTML = """
<html>
  <head><title>Order #973967 - Third Eye Comics</title></head>
  <body>
    <h1>Order 973967</h1>
    <div class="order-items">
      <div class="line">
        <a href="https://shop.thirdeyecomics.com/products/marvel-swimsuit-special-brand-new-beach-day-1-inhyuk-lee-marvel-snap-swimsuit-variant?variant=1&amp;sso=silent">Quantity 1</a>
        Quantity 1 MARVEL SWIMSUIT SPECIAL: BRAND NEW BEACH DAY #1 INHYUK LEE MARVEL SNAP SWIMSUIT VARIANT $5.99
      </div>
      <div class="line">
        <a href="https://shop.thirdeyecomics.com/products/apr26cat-prh-75960621474700111-marvel-swimsuit-special-brand-new-beach-day-1-wraparound-cover?variant=2">Quantity 2</a>
        Quantity 2 MARVEL SWIMSUIT SPECIAL: BRAND NEW BEACH DAY #1 WRAPAROUND COVER $5.99/ea $11.98
      </div>
    </div>
  </body>
</html>
"""


def test_third_eye_parser_uses_product_links_not_price_junk() -> None:
    parser = get_retailer_html_parser("third_eye")
    detail = parser.parse(_THIRD_EYE_SHOPIFY_HTML)
    assert detail.retailer_order_number == "973967"
    titles = {item.title for item in detail.items}
    assert "Gehenna In Tokyo #1" in titles
    assert "Amazing Spider-Man #1" in titles
    assert "/ea" not in titles
    assert "USD" not in titles
    gehenna = next(i for i in detail.items if "Gehenna" in i.title)
    assert gehenna.unit_price is not None
    assert str(gehenna.unit_price) == "3.59"
    assert "thirdeyecomics.com/products/" in (gehenna.product_url or "")


def test_third_eye_shopify_customer_account_quantity_links() -> None:
    parser = get_retailer_html_parser("third_eye")
    detail = parser.parse(_THIRD_EYE_CUSTOMER_ACCOUNT_HTML)
    assert detail.retailer_order_number == "973967"
    titles = {item.title for item in detail.items}
    assert any("INHYUK LEE" in t for t in titles)
    assert any("WRAPAROUND" in t for t in titles)
    wrap = next(i for i in detail.items if "WRAPAROUND" in i.title)
    assert wrap.quantity == 2
    assert str(wrap.unit_price) == "5.99"
    assert str(wrap.total_price) == "11.98"


def test_third_eye_fetches_shopify_product_json_for_cover_and_release() -> None:
    product_json = {
        "product": {
            "published_at": "2026-05-08T11:52:22-04:00",
            "images": [{"src": "https://cdn.shopify.com/s/files/cover.jpg"}],
        }
    }

    class _FakeResponse:
        def read(self) -> bytes:
            return json.dumps(product_json).encode()

        def __enter__(self) -> "_FakeResponse":
            return self

        def __exit__(self, *_args) -> None:
            return None

    with patch("urllib.request.urlopen", return_value=_FakeResponse()):
        detail = get_retailer_html_parser("third_eye").parse(_THIRD_EYE_CUSTOMER_ACCOUNT_HTML)

    inhyuk = next(i for i in detail.items if "INHYUK" in i.title.upper())
    assert inhyuk.image_url == "https://cdn.shopify.com/s/files/cover.jpg"
    assert inhyuk.release_date == date(2026, 5, 8)


def test_third_eye_confirm_materializes_on_acquisition_spine(client, session, monkeypatch) -> None:
    from app.services import retailer_order_materialization as materialization_module
    from app.services.retailer_sync import retailer_html_parsers as parsers_module

    monkeypatch.setattr(
        materialization_module,
        "legacy_customer_order_table_exists",
        lambda _session: False,
    )
    monkeypatch.setattr(
        parsers_module,
        "_get_shopify_product_meta",
        lambda _url: (None, None),
    )

    token = register_and_login(client, "third-eye-confirm@example.com")
    imported = client.post(
        "/api/v1/retailer-orders/import/html",
        headers=auth_headers(token),
        data={"retailer": "third_eye"},
        files={
            "file": (
                "order.html",
                _THIRD_EYE_CUSTOMER_ACCOUNT_HTML.encode("utf-8"),
                "text/html",
            )
        },
    )
    assert imported.status_code == 201, imported.text
    order_id = imported.json()["order_id"]

    confirmed = client.post(f"/api/v1/retailer-orders/{order_id}/confirm", headers=auth_headers(token))
    assert confirmed.status_code == 200, confirmed.text
    body = confirmed.json()
    assert body["review_status"] == "confirmed"
    assert body["linked_acquisition_id"] is not None
    assert body["inventory_copies_created"] == 3
    assert body["portfolio_items_added"] == 3


def test_dcbs_confirm_materializes_on_acquisition_spine(client, session) -> None:
    token = register_and_login(client, "dcbs-confirm@example.com")
    imported = client.post(
        "/api/v1/retailer-orders/import/html",
        headers=auth_headers(token),
        data={"retailer": "dcbs"},
        files={"file": ("dcbs-order.html", _DCBS_ORDER_TABLE_HTML.encode("utf-8"), "text/html")},
    )
    assert imported.status_code == 201, imported.text
    order_id = imported.json()["order_id"]

    confirmed = client.post(f"/api/v1/retailer-orders/{order_id}/confirm", headers=auth_headers(token))
    assert confirmed.status_code == 200, confirmed.text
    body = confirmed.json()
    assert body["review_status"] == "confirmed"
    assert body["linked_acquisition_id"] is not None
    assert body["inventory_copies_created"] == 3
    assert body["portfolio_items_added"] == 3


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


def test_dcbs_parser_reads_order_table_not_publisher_menu(client) -> None:
    token = register_and_login(client, "html-v2-dcbs-table@example.com")
    parser = get_retailer_html_parser("dcbs")
    detail = parser.parse(_DCBS_ORDER_TABLE_HTML)
    assert detail.retailer_order_number == "970668"
    assert len(detail.items) == 2
    assert detail.items[0].image_url == "https://media.dcbservice.com/small/MAY265025.jpg"
    assert detail.items[0].issue_number == "34"
    assert detail.items[0].publisher and "marvel" in detail.items[0].publisher.lower()
    assert detail.items[0].title.startswith("X-Men #34")
    assert detail.items[0].retailer_item_id == "MAY265025"
    assert detail.items[1].quantity == 2
    assert detail.parse_diagnostics["parse_source"] == "dcbs_order_table"

    response = client.post(
        "/api/v1/retailer-orders/import/html",
        headers=auth_headers(token),
        data={"retailer": "dcbs"},
        files={"file": ("dcbs-order.html", _DCBS_ORDER_TABLE_HTML.encode("utf-8"), "text/html")},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["retailer_order_number"] == "970668"
    assert payload["item_count"] == 2


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
