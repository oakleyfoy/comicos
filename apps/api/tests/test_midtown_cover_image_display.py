"""Midtown saved-HTML cover images render through review, confirm, and detail.

Midtown saved order pages reference local image filenames (e.g. ``2539636_ful.jpg``).
All Midtown product images follow
``https://www.midtowncomics.com/images/PRODUCT/FUL/{id}_ful.jpg``. The parser derives
that remote URL so the retailer cover displays even without catalog enrichment.
"""

from __future__ import annotations

from sqlmodel import select

from app.models import InventoryCopy, OrderItem
from app.services.retailer_sync.midtown_parser import parse_midtown_order_detail
from test_inventory import auth_headers, register_and_login

_REMOTE_URL = "https://www.midtowncomics.com/images/PRODUCT/FUL/2539636_ful.jpg"

_MIDTOWN_HTML = """
<html>
  <head><title>Order #4257559 - Midtown Comics</title></head>
  <body>
    <h1>Order #4257559</h1>
    <p>Date: 06/11/2026</p>
    <p>Status: Shipped</p>
    <p>Total: $5.99</p>
    <table>
      <tr>
        <td><img src="./Midtown Comics - Order-4257559_files/2539636_ful.jpg"
                 title="Absolute Wonder Woman #1 Cover A" alt="Absolute Wonder Woman #1" /></td>
        <td><a href="/product/9876/absolute-wonder-woman-1-cover-a">Absolute Wonder Woman #1 Cover A</a></td>
        <td>Publisher: DC</td>
        <td>Qty: 1</td>
        <td>Price: $5.99</td>
        <td>Line Total: $5.99</td>
        <td>Status: Shipped</td>
        <td>SKU: MT-9876</td>
      </tr>
    </table>
  </body>
</html>
"""


def test_parser_derives_remote_midtown_image_url() -> None:
    detail = parse_midtown_order_detail(_MIDTOWN_HTML)
    assert detail.retailer_order_number == "4257559"
    assert len(detail.items) == 1
    item = detail.items[0]
    # Local saved path retained; remote CDN URL derived from the *_ful.jpg filename.
    assert item.image_url == "./Midtown Comics - Order-4257559_files/2539636_ful.jpg"
    assert item.remote_midtown_image_url == _REMOTE_URL
    assert item.image_title == "Absolute Wonder Woman #1 Cover A"
    raw = item.to_dict()
    assert raw["remote_midtown_image_url"] == _REMOTE_URL
    assert raw["image_url"] == "./Midtown Comics - Order-4257559_files/2539636_ful.jpg"
    assert raw["image_title"] == "Absolute Wonder Woman #1 Cover A"


def test_midtown_cover_flows_review_confirm_and_detail(client, session) -> None:
    token = register_and_login(client, "midtown-cover-display@example.com")

    response = client.post(
        "/api/v1/retailer-orders/import/midtown-html",
        headers=auth_headers(token),
        files={"file": ("order.html", _MIDTOWN_HTML.encode("utf-8"), "text/html")},
    )
    assert response.status_code == 201, response.text
    order_id = response.json()["order_id"]

    # 1. Review screen exposes the Midtown remote cover (no catalog enrichment needed).
    detail = client.get(f"/api/v1/retailer-orders/{order_id}", headers=auth_headers(token))
    assert detail.status_code == 200, detail.text
    review_item = detail.json()["items"][0]
    assert review_item["remote_midtown_image_url"] == _REMOTE_URL
    assert review_item["cover_image_url"] == _REMOTE_URL
    assert review_item["image_title"] == "Absolute Wonder Woman #1 Cover A"

    # 2. Confirm materializes inventory with the remote cover as source_image_url.
    confirmed = client.post(
        f"/api/v1/retailer-orders/{order_id}/confirm", headers=auth_headers(token)
    )
    assert confirmed.status_code == 200, confirmed.text
    linked_order_id = confirmed.json()["linked_order_id"]
    session.expire_all()

    order_item = session.exec(
        select(OrderItem).where(OrderItem.order_id == linked_order_id)
    ).one()
    copy = session.exec(
        select(InventoryCopy).where(InventoryCopy.order_item_id == order_item.id)
    ).one()
    # Retailer cover should display even when the catalog match is needs_review.
    assert copy.source_image_url == _REMOTE_URL
    assert copy.primary_cover_image_id is None

    # 3. Inventory detail API returns the Midtown remote URL as the cover image.
    inv_detail = client.get(
        f"/inventory/{copy.id}", headers=auth_headers(token)
    )
    assert inv_detail.status_code == 200, inv_detail.text
    assert inv_detail.json()["cover_image_url"] == _REMOTE_URL
