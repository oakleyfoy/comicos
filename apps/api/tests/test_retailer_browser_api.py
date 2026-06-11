from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from test_inventory import auth_headers, register_and_login

from app.services.retailer_browser import MidtownBrowserOrders as MidtownBrowserOrdersModel
from app.services.retailer_browser import MidtownBrowserStatus
from app.services.retailer_browser import _launch_midtown_browser
from app.services.retailer_browser import (
    RetailerBrowserConfigurationError,
    RetailerBrowserEnvironmentError,
    RetailerBrowserStateError,
)


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
    assert response.status_code == 400
    assert response.json()["error"]["message"] == "Retailer browser session is not configured."


def test_midtown_browser_session_start_surfaces_security_verification(client, monkeypatch) -> None:
    token = register_and_login(client, "midtown-browser-security@example.com")
    status_model = MidtownBrowserStatus(
        retailer="midtown",
        account_id=1,
        status="security_verification_required",
        message="Midtown requires security verification.",
        current_url="https://www.midtowncomics.com/verify",
        orders_url="https://www.midtowncomics.com/account/orders",
        authenticated=False,
        order_count=0,
        last_updated_at=datetime.now(timezone.utc),
    )
    monkeypatch.setattr("app.api.retailer_browser.start_midtown_browser_session", lambda session, owner_user_id: status_model)

    response = client.post("/api/v1/retailer-browser/midtown/session/start", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    assert response.json()["session"]["status"] == "security_verification_required"
    assert response.json()["session"]["message"] == "Midtown requires security verification."


@pytest.mark.parametrize(
    ("raised_error", "expected_status", "expected_detail"),
    [
        (
            RetailerBrowserConfigurationError("Retailer browser session is not configured."),
            400,
            "Retailer browser session is not configured.",
        ),
        (
            RetailerBrowserEnvironmentError("Playwright Chromium failed to launch."),
            500,
            "Playwright Chromium failed to launch.",
        ),
        (
            RetailerBrowserStateError("Failed loading saved browser state."),
            500,
            "Failed loading saved browser state.",
        ),
    ],
)
def test_midtown_browser_session_start_maps_browser_errors(
    client,
    monkeypatch,
    raised_error,
    expected_status,
    expected_detail,
) -> None:
    token = register_and_login(client, "midtown-browser-error-map@example.com")

    def raise_error(*args, **kwargs):
        raise raised_error

    monkeypatch.setattr("app.api.retailer_browser.start_midtown_browser_session", raise_error)

    response = client.post("/api/v1/retailer-browser/midtown/session/start", headers=auth_headers(token))
    assert response.status_code == expected_status, response.text
    assert response.json()["error"]["message"] == expected_detail


def test_launch_midtown_browser_applies_headless_default_once(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeBrowserType:
        name = "chromium"
        executable_path = "C:/fake/chrome.exe"

        def launch(self, **kwargs):
            captured.update(kwargs)
            return object()

    class FakePlaywright:
        chromium = FakeBrowserType()

    monkeypatch.setattr("app.services.retailer_browser._playwright_version", lambda: "1.50.0")

    browser = _launch_midtown_browser(
        playwright=FakePlaywright(),
        account_id=7,
        launch_args={"headless": True, "slow_mo": 25},
    )

    assert browser is not None
    assert captured["headless"] is True
    assert captured["slow_mo"] == 25
    assert list(captured.keys()).count("headless") == 1


def test_midtown_session_start_does_not_fail_when_networkidle_times_out(client, session, monkeypatch) -> None:
    token = register_and_login(client, "midtown-browser-networkidle@example.com")
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

    class FakePage:
        url = "https://www.midtowncomics.com/account/orders"

        def __init__(self) -> None:
            self.load_states: list[str] = []

        def goto(self, url, wait_until="domcontentloaded"):
            self.url = url

        def wait_for_load_state(self, state, timeout=None):
            self.load_states.append(state)
            if state == "networkidle":
                raise AssertionError("networkidle should not be required")

        def content(self):
            return "<html><body>orders</body></html>"

    class FakeContext:
        def __init__(self) -> None:
            self.page = FakePage()

        def new_page(self):
            return self.page

        def close(self):
            pass

    class FakeBrowser:
        def __init__(self) -> None:
            self.context = FakeContext()

        def new_context(self, **kwargs):
            self.context_kwargs = kwargs
            return self.context

        def close(self):
            pass

    class FakeChromium:
        executable_path = "C:/fake/chrome.exe"
        name = "chromium"

        def launch(self, **kwargs):
            self.launch_kwargs = kwargs
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    class FakeSyncPlaywright:
        def __enter__(self):
            return FakePlaywright()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("playwright.sync_api.sync_playwright", lambda: FakeSyncPlaywright())
    monkeypatch.setattr("app.services.retailer_browser._requires_midtown_login", lambda page: False)
    monkeypatch.setattr("app.services.retailer_browser._has_midtown_challenge", lambda page: False)
    monkeypatch.setattr(
        "app.services.retailer_browser.parse_midtown_order_history",
        lambda html: [
            type(
                "FakeOrder",
                (),
                {
                    "retailer_order_number": "4272232",
                    "order_date": None,
                    "order_status": "Ready",
                    "order_total": None,
                    "raw_fragment": html,
                    "detail_url": "https://www.midtowncomics.com/account/orders/view/4272232",
                },
            )()
        ],
    )
    monkeypatch.setattr("app.services.retailer_browser._write_browser_state", lambda *args, **kwargs: None)

    response = client.post("/api/v1/retailer-browser/midtown/session/start", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    assert response.json()["session"]["status"] == "ready"
