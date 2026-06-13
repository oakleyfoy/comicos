from __future__ import annotations

from pathlib import Path
from decimal import Decimal

from app.services.retailer_sync.midtown_parser import (
    parse_midtown_order_detail,
    parse_midtown_order_history,
    strip_title_parentheticals,
)


def test_strip_title_parentheticals_removes_all_parenthetical_segments() -> None:
    dirty = "Absolute Green Arrow #1 Cover A Regular (DC All In)(Limit 1 Per Customer)"
    assert strip_title_parentheticals(dirty) == "Absolute Green Arrow #1 Cover A Regular"
    assert strip_title_parentheticals("Babylon Cove #1 (Cover A) Foo") == "Babylon Cove #1 Foo"
    assert strip_title_parentheticals("Plain Title #2 Cover B") == "Plain Title #2 Cover B"
    assert strip_title_parentheticals("") == ""
    assert strip_title_parentheticals(None) == ""


def test_parse_midtown_order_detail_strips_parentheticals_from_title() -> None:
    html = """
    <div>
      <h1>Order #4272299</h1>
      <p>Date: 06/08/2026</p>
      <p>Status: Shipped</p>
      <table>
        <tr>
          <td><img src="/images/PRODUCT/FUL/2539636_ful.jpg" /></td>
          <td><a href="/product/2539636/absolute-green-arrow-1">Absolute Green Arrow #1 Cover A Regular (DC All In)(Limit 1 Per Customer)</a></td>
          <td>Publisher: DC</td>
          <td>Qty: 1</td>
          <td>Price: $5.35</td>
          <td>Status: Shipped</td>
          <td>SKU: MT-2539636</td>
        </tr>
      </table>
    </div>
    """
    detail = parse_midtown_order_detail(html, fallback_order_number="4272299")
    assert len(detail.items) == 1
    item = detail.items[0]
    assert "(" not in item.title and ")" not in item.title
    assert item.title == "Absolute Green Arrow #1 Cover A Regular"
    assert item.issue_number == "1"
    assert item.cover_name == "Cover A"


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


def test_parse_midtown_order_detail_fixture_extracts_all_item_rows() -> None:
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "midtown" / "order_4272232_detail.html"
    html = fixture_path.read_text(encoding="utf-8")
    detail = parse_midtown_order_detail(
        html,
        detail_url="https://www.midtowncomics.com/account/orders/view/4272232",
    )
    assert detail.retailer_order_number == "4272232"
    assert detail.order_status == "Shipped"
    assert len(detail.items) == 21
    assert detail.items[0].title == "Absolute Batman #1 Cover A"
    assert detail.items[-1].title == "Absolute Batman #21 Cover C"
    assert detail.items[0].product_url == "https://www.midtowncomics.com/product/4272232-001/absolute-batman-1-cover-a"
    assert detail.items[-1].product_url == "https://www.midtowncomics.com/product/4272232-021/absolute-batman-21-cover-c"
    assert detail.parse_diagnostics["item_blocks_found"] >= 21
    assert detail.parse_diagnostics["items_parsed"] == 21
    assert detail.parse_diagnostics["items_skipped"] == 0
    assert detail.parse_diagnostics["skipped_reasons"] == {}
    assert detail.items[0].parse_diagnostics["fields_missing"] == []


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


def test_parse_midtown_saved_order_4257558_ignores_header_pull_list() -> None:
    fixture_path = (
        Path(__file__).resolve().parent / "fixtures" / "midtown" / "order_4257558_saved.html"
    )
    html = fixture_path.read_text(encoding="utf-8")
    detail = parse_midtown_order_detail(
        html,
        detail_url="https://www.midtowncomics.com/account/orders/view/4257558",
    )
    assert detail.retailer_order_number == "4257558"
    assert detail.order_status == "Shipped"
    assert detail.order_total == Decimal("105.13")
    assert len(detail.items) == 13
    assert detail.parse_diagnostics["parse_scope"] == "info_container"
    assert detail.parse_diagnostics["parse_source"] == "info_container_order_item"
    assert detail.parse_diagnostics["items_parsed"] == 13
    first = detail.items[0]
    # Parenthetical imprint/promo notes are stripped from the stored title.
    assert first.title == "Absolute Green Arrow #1 Cover A Regular Rafael Albuquerque Cover"
    assert "(" not in first.title and ")" not in first.title
    assert first.publisher == "DC"
    assert first.unit_price == Decimal("4.49")
    assert first.total_price == Decimal("4.49")
    assert first.quantity == 1
    assert first.item_status == "Shipped"
    assert first.image_url and "2539629_ful.jpg" in first.image_url
    assert first.remote_midtown_image_url == (
        "https://www.midtowncomics.com/images/PRODUCT/FUL/2539629_ful.jpg"
    )
    assert first.release_date is None
    assert first.product_url is None
    assert "release_date" in first.parse_diagnostics.get("enrichment_fields_missing", [])
    assert detail.items[1].publisher == "DC"
    assert detail.items[8].title.startswith("Babylon Cove")
    assert detail.items[8].publisher == "Independents"
    assert detail.items[9].title.startswith("Geiger")
    assert detail.items[9].publisher == "Image"
    assert detail.items[10].title.startswith("Seven Wives")
    assert detail.items[10].publisher == "IDW Publishing"
    titles = [item.title for item in detail.items]
    assert "Redcoat Cover B (regular)" not in titles
    assert detail.parse_diagnostics.get("first_order_item", {}).get("resolved_fields")


def test_parse_midtown_order_item_title_from_store_link_and_heading() -> None:
    html = """
    <div id="right-contents">
      <div class="info-container">
        <h1>Order #4257558</h1>
        <p>Status: Shipped</p>
        <p>Order Total: $105.13</p>
        <div class="order-item">
          <h4>Absolute Green Arrow #1 Cover A Regular Rafael Albuquerque Cover</h4>
          <a href="/Store/Comics/absolute-green-arrow-1" title="Absolute Green Arrow #1 Cover A Regular Rafael Albuquerque Cover">
            <img src="/images/cover.jpg" alt="" />
          </a>
          <div>Publisher: DC Comics</div>
          <div>Each: $4.99</div>
          <div>Total: $4.99</div>
          <div>QTY: 1</div>
          <div>Status: Shipped</div>
        </div>
      </div>
    </div>
    """
    detail = parse_midtown_order_detail(
        html,
        detail_url="https://www.midtowncomics.com/account/orders/view/4257558",
    )
    assert len(detail.items) == 1
    assert detail.items[0].title == "Absolute Green Arrow #1 Cover A Regular Rafael Albuquerque Cover"
    assert detail.items[0].product_url == "https://www.midtowncomics.com/Store/Comics/absolute-green-arrow-1"


def test_parse_midtown_order_item_title_from_visible_text_only() -> None:
    html = """
    <div id="right-contents">
      <div class="info-container">
        <h1>Order #4257558</h1>
        <div class="order-item">
          Absolute Green Arrow #1 Cover A Regular Rafael Albuquerque Cover
          Publisher: DC Comics
          Each: $4.99
          Total: $4.99
          QTY: 1
          Status: Shipped
        </div>
      </div>
    </div>
    """
    detail = parse_midtown_order_detail(html)
    assert len(detail.items) == 1
    assert "Absolute Green Arrow #1" in detail.items[0].title


def test_parse_midtown_order_detail_visible_text_fallback_in_info_container() -> None:
    html = """
    <div id="right-contents">
      <div class="info-container">
        <h1>Order #4257558</h1>
        <p>Status: Shipped</p>
        <p>Order Total: $9.98</p>
        <div class="order-summary-text">
          Immortal Thor #1 Cover A
          Publisher: Marvel
          Each: $4.99
          Total: $4.99
          QTY: 1
          Condition: New
          Status: Shipped

          Immortal Thor #2 Cover B
          Publisher: Marvel
          Each: $4.99
          Total: $4.99
          QTY: 1
          Condition: New
          Status: Shipped
        </div>
      </div>
    </div>
    """
    detail = parse_midtown_order_detail(
        html,
        detail_url="https://www.midtowncomics.com/account/orders/view/4257558",
    )
    assert detail.retailer_order_number == "4257558"
    assert detail.order_total == Decimal("9.98")
    assert len(detail.items) == 2
    assert detail.parse_diagnostics["parse_source"] == "visible_text_fallback"
    assert detail.items[0].title == "Immortal Thor #1 Cover A"
    assert detail.items[1].title == "Immortal Thor #2 Cover B"
