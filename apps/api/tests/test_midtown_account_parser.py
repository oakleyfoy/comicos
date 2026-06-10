from __future__ import annotations

from decimal import Decimal

from app.services.retailer_sync.midtown_parser import (
    parse_midtown_order_detail,
    parse_midtown_order_history,
)


def test_parse_midtown_order_history_extracts_rows() -> None:
    html = """
    <table>
      <tr>
        <td><a href="/account/orders/view/4272232">Order #4272232</a></td>
        <td>Date: 06/08/2026</td>
        <td>Status: Shipped</td>
        <td>Total: $14.98</td>
      </tr>
    </table>
    """
    rows = parse_midtown_order_history(html)
    assert len(rows) == 1
    assert rows[0].retailer_order_number == "4272232"
    assert rows[0].order_status == "Shipped"
    assert rows[0].order_total == Decimal("14.98")
    assert rows[0].detail_url == "https://www.midtowncomics.com/account/orders/view/4272232"


def test_parse_midtown_order_detail_extracts_items() -> None:
    html = """
    <div>
      <style>
        .card { border-radius: 12px; }
      </style>
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
          <td>Shipped: 2</td>
          <td>SKU: MT-1234</td>
        </tr>
      </table>
    </div>
    """
    detail = parse_midtown_order_detail(
        html,
        fallback_order_number="4272232",
        detail_url="https://www.midtowncomics.com/account/orders/view/4272232",
    )
    assert detail.retailer_order_number == "4272232"
    assert detail.order_total == Decimal("14.98")
    assert len(detail.items) == 1
    item = detail.items[0]
    assert item.title == "Immortal Thor #1 Cover A"
    assert item.issue_number == "1"
    assert item.cover_name == "Cover A"
    assert item.publisher == "Marvel"
    assert item.quantity == 2
    assert item.unit_price == Decimal("4.99")
    assert item.total_price == Decimal("9.98")
    assert item.shipped_qty == 2
    assert item.product_url == "https://www.midtowncomics.com/product/1234/immortal-thor-1-cover-a"


def test_parse_midtown_order_detail_uses_header_number_not_item_status_text() -> None:
    html = """
    <html>
      <head>
        <title>Order #4272232 - Midtown Comics</title>
      </head>
      <body>
        <header>
          <h1>Order #4272232</h1>
          <div class="order-status-summary">
            Pending 0 Shipped 0 Back-Ordered 0 Not Available 0 Returned
          </div>
        </header>
        <section>
          <table>
            <tr>
              <td><img src="/images/absolute-batman.jpg" /></td>
              <td><a href="/product/9999/absolute-batman-1-cover-a">Absolute Batman #1 Cover A</a></td>
              <td>Publisher: DC</td>
              <td>Qty: 1</td>
              <td>Price: $4.99</td>
              <td>Line Total: $4.99</td>
              <td>Status: Pending</td>
              <td>Shipped: 0</td>
              <td>Backordered: 0</td>
              <td>Unavailable: 0</td>
              <td>Returned: 0</td>
            </tr>
          </table>
        </section>
      </body>
    </html>
    """
    detail = parse_midtown_order_detail(
        html,
        detail_url="https://www.midtowncomics.com/account/orders/view/4272232",
    )
    assert detail.retailer_order_number == "4272232"
    assert detail.order_status == "Pending"
    assert "Pending" not in detail.retailer_order_number
    assert detail.items[0].title == "Absolute Batman #1 Cover A"


def test_parse_midtown_order_detail_ignores_border_radius_noise() -> None:
    html = """
    <div>
      <style>
        .card { border-radius: 12px; }
      </style>
      <h1>Order #4272232</h1>
      <p>Date: 06/09/2026</p>
      <p>Status: Pending</p>
      <p>Total: $5.99</p>
    </div>
    """
    detail = parse_midtown_order_detail(
        html,
        fallback_order_number=None,
        detail_url="https://www.midtowncomics.com/account/orders/view/4272232",
    )
    assert detail.retailer_order_number == "4272232"
