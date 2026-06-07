"""Ops ingestion monitoring safe GET envelopes."""

from __future__ import annotations

from fastapi.testclient import TestClient

from test_ops_admin import auth_headers, register_and_login


def test_ops_dashboard_returns_200_with_status(client: TestClient) -> None:
    token = register_and_login(client, "ops-safe-dash@example.com")
    resp = client.get("/ops/dashboard", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("status") in {"OK", "EMPTY"}
    assert "recent_gmail_sync_jobs" in body


def test_ops_market_ingestion_batches_safe_list(client: TestClient) -> None:
    token = register_and_login(client, "ops-safe-mkt@example.com")
    resp = client.get("/api/v1/market/ops/market-ingestion/batches", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data.get("status") in {"OK", "EMPTY"}
    assert "items" in data
