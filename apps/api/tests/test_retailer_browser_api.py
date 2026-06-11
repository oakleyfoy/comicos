from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from test_inventory import auth_headers, register_and_login

from app.services.retailer_browser import MidtownBrowserOrders as MidtownBrowserOrdersModel
from app.services.retailer_browser import MidtownBrowserStatus


def test_midtown_browser_session_routes_surface_orders_and_capture(client, session, monkeypatch) -> None:
    token = register_and_login(client, "midtown-browser-route@example.com")
    client.post(
        "/api/v1/retailer-accounts",
        headers=auth_headers(token),
        json={
            "retailer": "midtown",
            "username": "collector@example.com",
            "password": "supersafe",
            "display_name": "Midtown Comics",
            "sync_enabled": True,
        },
    )

    status_model = MidtownBrowserStatus(
        retailer="midtown",
        account_id=1,
        status="ready",
        message="Ready",
        current_url="https://www.midtowncomics.com/account-settings",
        orders_url="https://www.midtowncomics.com/account-settings",
        authenticated=True,
        order_count=1,
        last_updated_at=datetime.now(timezone.utc),
    )
    orders_model = MidtownBrowserOrdersModel(
        status=status_model,
        orders=[
            {
                "retailer_order_number": "4272232",
                "order_date": date(2026, 6, 8),
                "order_status": "Shipped",
                "order_total": Decimal("9.98"),
                "item_count": 1,
                "detail_url": "https://www.midtowncomics.com/account/orders/view/4272232",
            }
        ],
    )

    monkeypatch.setattr(
        "app.api.retailer_browser.start_midtown_browser_session",
        lambda session, owner_user_id: status_model,
    )
    monkeypatch.setattr(
        "app.api.retailer_browser.get_midtown_browser_session_status",
        lambda session, owner_user_id: status_model,
    )
    monkeypatch.setattr(
        "app.api.retailer_browser.list_midtown_browser_orders",
        lambda session, owner_user_id: orders_model,
    )
    monkeypatch.setattr(
        "app.api.retailer_browser.capture_midtown_browser_order",
        lambda session, owner_user_id, retailer_order_number: (status_model, object(), 17),
    )

    started = client.post("/api/v1/retailer-browser/midtown/session/start", headers=auth_headers(token))
    assert started.status_code == 200, started.text
    assert started.json()["session"]["status"] == "ready"

    session_status = client.get(
        "/api/v1/retailer-browser/midtown/session/status",
        headers=auth_headers(token),
    )
    assert session_status.status_code == 200, session_status.text
    assert session_status.json()["session"]["authenticated"] is True

    orders = client.get("/api/v1/retailer-browser/midtown/orders", headers=auth_headers(token))
    assert orders.status_code == 200, orders.text
    assert orders.json()["orders"][0]["retailer_order_number"] == "4272232"

    capture = client.post(
        "/api/v1/retailer-browser/midtown/orders/4272232/capture",
        headers=auth_headers(token),
    )
    assert capture.status_code == 200, capture.text
    assert capture.json()["order_id"] == 17
    assert capture.json()["retailer_order_number"] == "4272232"


def test_midtown_browser_session_requires_connected_account(client) -> None:
    token = register_and_login(client, "midtown-browser-missing@example.com")
    response = client.get(
        "/api/v1/retailer-browser/midtown/session/status",
        headers=auth_headers(token),
    )
    assert response.status_code == 404
