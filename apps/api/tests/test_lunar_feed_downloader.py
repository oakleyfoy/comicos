from __future__ import annotations

import httpx
import pytest

from app.services.lunar_authenticated_client import LunarAuthenticatedClient, LunarResourceNotFoundError
from app.services.lunar_feed_downloader import download_latest_monthly_products_csv
from lunar_feed_test_helpers import MOCK_LOGIN_HTML, MOCK_RESOURCES_HTML, SAMPLE_CSV


def test_download_latest_monthly_products_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUNAR_USERNAME", "store-user")
    monkeypatch.setenv("LUNAR_PASSWORD", "secret-value")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/home/login":
            return httpx.Response(200, text=MOCK_LOGIN_HTML)
        if request.url.path == "/account/login":
            return httpx.Response(200, text="ok")
        if request.url.path == "/home/resources":
            return httpx.Response(200, text=MOCK_RESOURCES_HTML)
        if request.url.path.endswith(".csv"):
            return httpx.Response(200, content=SAMPLE_CSV.encode("utf-8"))
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = LunarAuthenticatedClient(base_url="https://example.test", transport=transport)
    downloaded = download_latest_monthly_products_csv(client=client)
    assert downloaded.file_name.endswith(".csv")
    assert downloaded.file_period == "2026-06"


def test_missing_csv_link(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUNAR_USERNAME", "store-user")
    monkeypatch.setenv("LUNAR_PASSWORD", "secret-value")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/home/login":
            return httpx.Response(200, text=MOCK_LOGIN_HTML)
        if request.url.path == "/account/login":
            return httpx.Response(200, text="ok")
        if request.url.path == "/home/resources":
            return httpx.Response(200, text="<html><body>No files</body></html>")
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = LunarAuthenticatedClient(base_url="https://example.test", transport=transport)
    with pytest.raises(LunarResourceNotFoundError):
        download_latest_monthly_products_csv(client=client)
