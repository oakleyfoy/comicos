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
        <td><a href="/account/orders/view/ABC123">Order #ABC123</a></td>
        <td>Date: 06/08/2026</td>
        <td>Status: Shipped</td>
        <td>Total: $14.98</td>
      </tr>
    </table>
    """
    rows = parse_midtown_order_history(html)
    assert len(rows) == 1
    assert rows[0].retailer_order_number == "ABC123"
    assert rows[0].order_status == "Shipped"
    assert rows[0].order_total == Decimal("14.98")
    assert rows[0].detail_url == "https://www.midtowncomics.com/account/orders/view/ABC123"


def test_parse_midtown_order_detail_extracts_items() -> None:
    html = """
    <div>
      <h1>Order #ABC123</h1>
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
        fallback_order_number="ABC123",
        detail_url="https://www.midtowncomics.com/account/orders/view/ABC123",
    )
    assert detail.retailer_order_number == "ABC123"
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
