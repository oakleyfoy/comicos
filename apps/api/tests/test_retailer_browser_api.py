from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from test_inventory import auth_headers, register_and_login

from app.services.retailer_browser import MidtownBrowserOrders as MidtownBrowserOrdersModel
from app.services.retailer_browser import MidtownBrowserStatus
from app.services.retailer_browser import _launch_midtown_browser
from app.services.retailer_browser import (
    MidtownBrowserBusyError,
    MidtownNeedsAttentionError,
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

        def storage_state(self, path):
            return None

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
    monkeypatch.setattr("app.services.retailer_browser._MIDTOWN_PLAYWRIGHT", None)
    monkeypatch.setattr("app.services.retailer_browser._MIDTOWN_LIVE_SESSIONS", {})
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


def test_midtown_browser_session_frame_returns_image_and_metadata(client, monkeypatch) -> None:
    token = register_and_login(client, "midtown-browser-frame@example.com")
    status_model = MidtownBrowserStatus(
        retailer="midtown",
        account_id=1,
        status="login_required",
        message="Midtown login is required.",
        current_url="https://www.midtowncomics.com/account/orders",
        orders_url="https://www.midtowncomics.com/account/orders",
        authenticated=False,
        order_count=0,
        last_updated_at=datetime.now(timezone.utc),
        viewport_width=1440,
        viewport_height=1100,
        live_session_active=True,
    )
    monkeypatch.setattr(
        "app.api.retailer_browser.get_midtown_browser_live_frame",
        lambda session, owner_user_id: {
            "session": status_model,
            "image_data_url": "data:image/jpeg;base64,abc123",
            "image_width": 1440,
            "image_height": 1100,
            "viewport_width": 1440,
            "viewport_height": 1100,
            "live_session_active": True,
            "captured_at": "2026-06-10T20:00:00Z",
        },
    )

    response = client.get("/api/v1/retailer-browser/midtown/session/frame", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["image_data_url"] == "data:image/jpeg;base64,abc123"
    assert payload["image_width"] == 1440
    assert payload["session"]["live_session_active"] is True


def test_midtown_browser_session_frame_returns_429_when_busy(client, monkeypatch) -> None:
    token = register_and_login(client, "midtown-browser-frame-busy@example.com")

    def raise_busy(session, owner_user_id):
        raise MidtownBrowserBusyError("Midtown browser is busy. Try again shortly.")

    monkeypatch.setattr("app.api.retailer_browser.get_midtown_browser_live_frame", raise_busy)

    response = client.get("/api/v1/retailer-browser/midtown/session/frame", headers=auth_headers(token))
    assert response.status_code == 429, response.text
    assert "Midtown browser is busy. Try again shortly." in response.text


def test_midtown_browser_session_rehydrates_from_saved_state(client, monkeypatch) -> None:
    token = register_and_login(client, "midtown-browser-rehydrate@example.com")
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
        def __init__(self) -> None:
            self.url = "https://www.midtowncomics.com/login"
            self.viewport_size = {"width": 1440, "height": 1100}

        def goto(self, url, wait_until="domcontentloaded"):
            self.url = url

        def wait_for_load_state(self, state, timeout=None):
            return None

        def content(self):
            if self.url.endswith("/account/orders"):
                return "<html><body>orders</body></html>"
            return "<html><body>login</body></html>"

        def screenshot(self, type="jpeg", quality=75):
            return b"fake-image-bytes"

        def is_closed(self):
            return False

        def title(self):
            return "Midtown Login"

    class FakeContext:
        def __init__(self) -> None:
            self.page = FakePage()

        def new_page(self):
            return self.page

        def storage_state(self, path):
            return None

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

        def is_connected(self):
            return True

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
    monkeypatch.setattr("app.services.retailer_browser._MIDTOWN_PLAYWRIGHT", None)
    monkeypatch.setattr("app.services.retailer_browser._MIDTOWN_LIVE_SESSIONS", {})
    monkeypatch.setattr(
        "app.services.retailer_browser.parse_midtown_order_history",
        lambda html: [],
    )
    login_calls: list[tuple[str, str]] = []

    def fake_midtown_login(page, *, username, password):
        login_calls.append((username, password))
        page.url = "https://www.midtowncomics.com/account/orders"

    monkeypatch.setattr("app.services.retailer_browser._midtown_login", fake_midtown_login)
    monkeypatch.setattr(
        "app.services.retailer_browser._read_browser_state",
        lambda account_id: {
            "status": "login_required",
            "current_url": "https://www.midtowncomics.com/login",
            "orders_url": "https://www.midtowncomics.com/account/orders",
            "order_count": 0,
            "authenticated": False,
            "message": "Midtown login is required.",
            "last_updated_at": "2026-06-11T17:00:00Z",
            "viewport_width": 1440,
            "viewport_height": 1100,
            "live_session_active": True,
        },
    )
    monkeypatch.setattr("app.services.retailer_browser._write_browser_state", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.services.retailer_browser._requires_midtown_login", lambda page: page.url.endswith("/login"))
    monkeypatch.setattr("app.services.retailer_browser._has_midtown_challenge", lambda page: False)

    response = client.get("/api/v1/retailer-browser/midtown/session/status", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    payload = response.json()["session"]
    assert payload["live_session_active"] is True
    assert payload["viewport_width"] == 1440
    assert payload["viewport_height"] == 1100
    assert payload["registry_contains_account"] is True
    assert login_calls == [("collector@example.com", "supersafe")]

    frame = client.get("/api/v1/retailer-browser/midtown/session/frame", headers=auth_headers(token))
    assert frame.status_code == 200, frame.text
    frame_payload = frame.json()
    assert frame_payload["endpoint_status"] == 200
    assert frame_payload["image_bytes_size"] > 0
    assert frame_payload["page_url"] == "https://www.midtowncomics.com/account/orders"
    assert frame_payload["session"]["live_session_active"] is True


def _install_midtown_fake_browser(
    monkeypatch,
    *,
    login_url="https://www.midtowncomics.com/login",
    login_side_effect=None,
    screenshot_side_effect=None,
):
    class FakePage:
        def __init__(self) -> None:
            self.url = login_url
            self.viewport_size = {"width": 1440, "height": 1100}

        def goto(self, url, wait_until="domcontentloaded"):
            self.url = url

        def wait_for_load_state(self, state, timeout=None):
            return None

        def content(self):
            return "<html><body>login</body></html>"

        def screenshot(self, type="jpeg", quality=75):
            if screenshot_side_effect is not None:
                screenshot_side_effect()
            return b"fake-image-bytes"

        def is_closed(self):
            return False

        def title(self):
            return "Midtown"

        def evaluate(self, *args, **kwargs):
            return {"tag": None, "name": None, "type": None, "placeholder": None}

    class FakeContext:
        def __init__(self) -> None:
            self.page = FakePage()

        def new_page(self):
            return self.page

        def storage_state(self, path):
            return None

        def close(self):
            pass

    class FakeBrowser:
        def __init__(self) -> None:
            self.context = FakeContext()

        def new_context(self, **kwargs):
            return self.context

        def close(self):
            pass

    class FakeChromium:
        executable_path = "C:/fake/chrome.exe"
        name = "chromium"

        def launch(self, **kwargs):
            return FakeBrowser()

    class FakePlaywright:
        chromium = FakeChromium()

    class FakeSyncPlaywright:
        def __enter__(self):
            return FakePlaywright()

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("playwright.sync_api.sync_playwright", lambda: FakeSyncPlaywright())
    monkeypatch.setattr("app.services.retailer_browser._MIDTOWN_PLAYWRIGHT", None)
    monkeypatch.setattr("app.services.retailer_browser.parse_midtown_order_history", lambda html: [])
    monkeypatch.setattr("app.services.retailer_browser._write_browser_state", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.services.retailer_browser._requires_midtown_login", lambda page: True)
    monkeypatch.setattr("app.services.retailer_browser._has_midtown_challenge", lambda page: False)

    def fake_login(page, *, username, password):
        if login_side_effect is not None:
            login_side_effect()
        page.url = "https://www.midtowncomics.com/account/orders"

    monkeypatch.setattr("app.services.retailer_browser._midtown_login", fake_login)


def _connect_midtown_account(client, token) -> None:
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


def test_midtown_browser_session_start_returns_security_state_on_captcha(client, monkeypatch) -> None:
    token = register_and_login(client, "midtown-browser-start-captcha@example.com")
    _connect_midtown_account(client, token)

    def raise_challenge():
        raise MidtownNeedsAttentionError("Midtown requires security verification.")

    _install_midtown_fake_browser(monkeypatch, login_side_effect=raise_challenge)

    response = client.post("/api/v1/retailer-browser/midtown/session/start", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    assert response.json()["session"]["status"] == "security_verification_required"


def test_midtown_browser_session_frame_serves_screenshot_during_security_verification(client, monkeypatch) -> None:
    token = register_and_login(client, "midtown-browser-frame-captcha@example.com")
    _connect_midtown_account(client, token)

    def raise_challenge():
        raise MidtownNeedsAttentionError("Midtown requires security verification.")

    _install_midtown_fake_browser(monkeypatch, login_side_effect=raise_challenge)

    response = client.get("/api/v1/retailer-browser/midtown/session/frame", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["session"]["status"] == "security_verification_required"
    assert payload["image_data_url"].startswith("data:image/jpeg;base64,")
    assert payload["image_bytes_size"] > 0
    assert payload["frame_available"] is True


def test_midtown_browser_session_frame_never_500_when_capture_fails(client, monkeypatch) -> None:
    token = register_and_login(client, "midtown-browser-frame-fail@example.com")
    _connect_midtown_account(client, token)

    def raise_capture():
        raise RuntimeError("screenshot exploded")

    # No cached screenshot exists for this fresh account, so a capture failure
    # must degrade to a controlled no_frame_available response rather than 500.
    monkeypatch.setattr("app.services.retailer_browser._read_last_screenshot", lambda account_id: None)
    _install_midtown_fake_browser(monkeypatch, screenshot_side_effect=raise_capture)

    response = client.get("/api/v1/retailer-browser/midtown/session/frame", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["session"]["status"] == "no_frame_available"
    assert payload["frame_available"] is False
    assert payload["image_data_url"] == ""


def test_midtown_browser_click_replay_supports_typing(client, monkeypatch) -> None:
    token = register_and_login(client, "midtown-browser-interaction@example.com")
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

    state = {
        "status": "login_required",
        "current_url": "https://www.midtowncomics.com/login",
        "orders_url": "https://www.midtowncomics.com/account/orders",
        "order_count": 0,
        "authenticated": False,
        "message": "Midtown login is required.",
        "last_updated_at": "2026-06-11T17:00:00Z",
        "viewport_width": 1440,
        "viewport_height": 1100,
        "live_session_active": True,
    }
    pages: list[object] = []

    class FakeMouse:
        def __init__(self) -> None:
            self.clicks: list[tuple[float, float, str, int]] = []

        def click(self, x, y, button="left", click_count=1):
            self.clicks.append((x, y, button, click_count))

    class FakeKeyboard:
        def __init__(self) -> None:
            self.typed: list[str] = []
            self.inserted: list[str] = []

        def type(self, text, delay=0):
            self.typed.append(text)

        def insert_text(self, text):
            self.inserted.append(text)

        def press(self, key):
            self.typed.append(f"[{key}]")

    class FakePage:
        def __init__(self) -> None:
            self.url = state["current_url"]
            self.viewport_size = {"width": 1440, "height": 1100}
            self.mouse = FakeMouse()
            self.keyboard = FakeKeyboard()
            self.active_element = {
                "tag": "input",
                "name": "email",
                "type": "email",
                "placeholder": "Email address",
            }

        def goto(self, url, wait_until="domcontentloaded"):
            self.url = url

        def wait_for_load_state(self, state_name, timeout=None):
            return None

        def content(self):
            return "<html><body><input type='email' name='email' placeholder='Email address'></body></html>"

        def screenshot(self, type="jpeg", quality=75):
            return b"fake-image-bytes"

        def is_closed(self):
            return False

        def title(self):
            return "Midtown Login"

        def evaluate(self, script):
            return self.active_element

    class FakeContext:
        def __init__(self, page) -> None:
            self.page = page

        def new_page(self):
            return self.page

        def close(self):
            pass

    class FakeBrowser:
        def __init__(self, page) -> None:
            self.context = FakeContext(page)

        def new_context(self, **kwargs):
            self.context_kwargs = kwargs
            return self.context

        def close(self):
            pass

        def is_connected(self):
            return True

    class FakeChromium:
        executable_path = "C:/fake/chrome.exe"
        name = "chromium"

        def launch(self, **kwargs):
            self.launch_kwargs = kwargs
            page = FakePage()
            pages.append(page)
            return FakeBrowser(page)

    class FakePlaywright:
        chromium = FakeChromium()

    class FakeSyncPlaywright:
        def __enter__(self):
            return FakePlaywright()

        def __exit__(self, exc_type, exc, tb):
            return False

    @contextmanager
    def fake_request_browser(account, *, target_url=None):
        browser = FakeBrowser(FakePage())
        page = browser.context.page
        if target_url is not None:
            page.goto(target_url)
        pages.append(page)
        try:
            yield browser, browser.context, page
        finally:
            pass

    monkeypatch.setattr("playwright.sync_api.sync_playwright", lambda: FakeSyncPlaywright())
    monkeypatch.setattr("app.services.retailer_browser._MIDTOWN_PLAYWRIGHT", None)
    monkeypatch.setattr("app.services.retailer_browser._MIDTOWN_LIVE_SESSIONS", {})
    monkeypatch.setattr("app.services.retailer_browser._MIDTOWN_LIVE_SESSION_METADATA", {})
    monkeypatch.setattr("app.services.retailer_browser._read_browser_state", lambda account_id: state)
    monkeypatch.setattr("app.services.retailer_browser._write_browser_state", lambda account_id, payload: state.update(payload))
    monkeypatch.setattr("app.services.retailer_browser._has_midtown_challenge", lambda page: False)
    monkeypatch.setattr("app.services.retailer_browser._requires_midtown_login", lambda page: True)
    monkeypatch.setattr("app.services.retailer_browser._midtown_request_browser", fake_request_browser)

    click_response = client.post(
        "/api/v1/retailer-browser/midtown/session/click",
        headers=auth_headers(token),
        json={
            "x": 360,
            "y": 220,
            "displayed_image_width": 720,
            "displayed_image_height": 440,
            "viewport_width": 1440,
            "viewport_height": 1100,
        },
    )
    assert click_response.status_code == 200, click_response.text
    assert state["last_click"]["x"] == 360
    assert state["last_click"]["y"] == 220
    assert state["last_click"]["displayed_image_width"] == 720
    assert pages[0].mouse.clicks[0][:2] == (720.0, 550.0)

    type_response = client.post(
        "/api/v1/retailer-browser/midtown/session/type",
        headers=auth_headers(token),
        json={"text": "collector@example.com"},
    )
    assert type_response.status_code == 200, type_response.text
    assert pages[-1].mouse.clicks[-1][:2] == (720.0, 550.0)
    assert pages[-1].keyboard.typed[-1] == "collector@example.com"


@pytest.mark.parametrize(
    ("route", "service_name", "payload", "expected_key"),
    [
        ("/api/v1/retailer-browser/midtown/session/click", "click_midtown_browser_live_session", {"x": 12, "y": 34}, "x"),
        ("/api/v1/retailer-browser/midtown/session/type", "type_midtown_browser_live_session", {"text": "hello"}, "text"),
        ("/api/v1/retailer-browser/midtown/session/key", "key_midtown_browser_live_session", {"key": "Enter"}, "key"),
    ],
)
def test_midtown_browser_session_input_routes_forward_payload(
    client,
    monkeypatch,
    route,
    service_name,
    payload,
    expected_key,
) -> None:
    token = register_and_login(client, "midtown-browser-input@example.com")
    status_model = MidtownBrowserStatus(
        retailer="midtown",
        account_id=1,
        status="ready",
        message="Ready",
        current_url="https://www.midtowncomics.com/account/orders",
        orders_url="https://www.midtowncomics.com/account/orders",
        authenticated=True,
        order_count=3,
        last_updated_at=datetime.now(timezone.utc),
        live_session_active=True,
    )
    captured: dict[str, object] = {}

    def fake_forward(*args, **kwargs):
        captured.update(kwargs)
        return status_model

    monkeypatch.setattr(f"app.api.retailer_browser.{service_name}", fake_forward)

    response = client.post(route, headers=auth_headers(token), json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["session"]["status"] == "ready"
    assert expected_key in captured


def test_midtown_browser_session_retry_returns_refreshed_status(client, monkeypatch) -> None:
    token = register_and_login(client, "midtown-browser-retry@example.com")
    status_model = MidtownBrowserStatus(
        retailer="midtown",
        account_id=1,
        status="ready",
        message="Ready",
        current_url="https://www.midtowncomics.com/account/orders",
        orders_url="https://www.midtowncomics.com/account/orders",
        authenticated=True,
        order_count=9,
        last_updated_at=datetime.now(timezone.utc),
        live_session_active=True,
    )
    monkeypatch.setattr(
        "app.api.retailer_browser.retry_midtown_browser_live_session",
        lambda session, owner_user_id: status_model,
    )

    response = client.post("/api/v1/retailer-browser/midtown/session/retry", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    assert response.json()["session"]["order_count"] == 9


class _DetectionPage:
    def __init__(self, *, url, title, visible_text, password_visible=False, challenge_selectors=()):
        self.url = url
        self._title = title
        self._visible_text = visible_text
        self._password_visible = password_visible
        self._challenge_selectors = set(challenge_selectors)

    def title(self):
        return self._title

    def inner_text(self, selector):
        return self._visible_text

    def content(self):
        # Raw HTML intentionally references Cloudflare/captcha (CDN + widget scripts)
        # the way a normal Midtown page does. Detection must ignore this.
        return (
            "<html><head>"
            "<script src='https://challenges.cloudflare.com/turnstile/v0/api.js'></script>"
            "</head><body>captcha cloudflare " + self._visible_text + "</body></html>"
        )

    def locator(self, selector):
        page = self

        class _Locator:
            def count(self):
                if selector == "input[type='password']":
                    return 1 if page._password_visible else 0
                return 1 if selector in page._challenge_selectors else 0

            @property
            def first(self):
                class _First:
                    def is_visible(self_inner):
                        if selector == "input[type='password']":
                            return page._password_visible
                        return selector in page._challenge_selectors

                return _First()

        return _Locator()


def test_midtown_detection_ignores_incidental_cloudflare_references() -> None:
    from app.services.retailer_browser import _detect_midtown_challenge, _detect_midtown_login

    page = _DetectionPage(
        url="https://www.midtowncomics.com/search?q=batman",
        title="Search Results | Midtown Comics",
        visible_text="Showing 24 results for batman. Add to cart.",
    )
    assert _detect_midtown_challenge(page)[0] is False
    assert _detect_midtown_login(page)[0] is False


def test_midtown_detection_flags_real_cloudflare_interstitial() -> None:
    from app.services.retailer_browser import _detect_midtown_challenge

    by_title = _DetectionPage(
        url="https://www.midtowncomics.com/",
        title="Just a moment...",
        visible_text="",
    )
    detected, reason = _detect_midtown_challenge(by_title)
    assert detected is True
    assert reason and reason.startswith("title:")

    by_text = _DetectionPage(
        url="https://www.midtowncomics.com/",
        title="Midtown Comics",
        visible_text="Checking your browser before accessing midtowncomics.com",
    )
    assert _detect_midtown_challenge(by_text)[0] is True


def test_midtown_login_detection_requires_url_or_visible_password() -> None:
    from app.services.retailer_browser import _detect_midtown_login

    login_url = _DetectionPage(
        url="https://www.midtowncomics.com/login",
        title="Login",
        visible_text="Sign in",
    )
    assert _detect_midtown_login(login_url)[0] is True

    normal = _DetectionPage(
        url="https://www.midtowncomics.com/account-settings",
        title="Account Settings",
        visible_text="Your order history",
    )
    assert _detect_midtown_login(normal)[0] is False

    visible_password = _DetectionPage(
        url="https://www.midtowncomics.com/account-settings",
        title="Account Settings",
        visible_text="Sign in",
        password_visible=True,
    )
    assert _detect_midtown_login(visible_password)[0] is True
