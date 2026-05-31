from __future__ import annotations

import httpx
import pytest

from app.services.lunar_authenticated_client import (
    LunarAuthenticatedClient,
    LunarAuthenticationError,
    LunarResourceNotFoundError,
    parse_monthly_csv_links,
    select_latest_period_link,
)
from lunar_feed_test_helpers import MOCK_LOGIN_HTML, MOCK_RESOURCES_HTML, SAMPLE_CSV


def test_parse_monthly_csv_links_finds_june_2026() -> None:
    links = parse_monthly_csv_links(MOCK_RESOURCES_HTML, base_url="https://example.test")
    assert len(links) >= 2
    latest = select_latest_period_link(links)
    assert latest.period_key == "2026-06"
    assert latest.file_type == "LUNAR_FORMAT"


def test_select_period_missing_raises() -> None:
    links = parse_monthly_csv_links(MOCK_RESOURCES_HTML, base_url="https://example.test")
    with pytest.raises(LunarResourceNotFoundError):
        select_latest_period_link(links, period="2020-01")


def test_authenticated_client_login_and_download(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUNAR_USERNAME", "store-user")
    monkeypatch.setenv("LUNAR_PASSWORD", "secret-value")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/home/login":
            return httpx.Response(200, text=MOCK_LOGIN_HTML)
        if request.url.path == "/account/login":
            return httpx.Response(200, text="Welcome", headers={"set-cookie": "session=abc"})
        if request.url.path == "/home/resources":
            return httpx.Response(200, text=MOCK_RESOURCES_HTML)
        if request.url.path == "/files/june-2026-lunar-format.csv":
            return httpx.Response(200, content=SAMPLE_CSV.encode("utf-8"))
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    with LunarAuthenticatedClient(base_url="https://example.test", transport=transport) as client:
        client.login()
        downloaded = client.download_product_csv()
        assert downloaded.file_period == "2026-06"
        assert b"Battle Beast" in downloaded.content_bytes


def test_login_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUNAR_USERNAME", "bad")
    monkeypatch.setenv("LUNAR_PASSWORD", "bad")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/home/login":
            return httpx.Response(200, text=MOCK_LOGIN_HTML)
        if request.url.path == "/account/login":
            return httpx.Response(
                200,
                text="Invalid login attempt",
                request=httpx.Request("POST", "https://example.test/home/login"),
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    with LunarAuthenticatedClient(base_url="https://example.test", transport=transport) as client:
        with pytest.raises(LunarAuthenticationError):
            client.login()
