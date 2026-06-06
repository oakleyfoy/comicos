from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from test_inventory import auth_headers, register_and_login

_ENDPOINTS = [
    "/api/v1/daily-actions",
    "/api/v1/daily-actions/summary",
    "/api/v1/collector-command-center",
    "/api/v1/notifications",
    "/api/v1/briefings/daily",
    "/api/v1/briefings/weekly",
    "/api/v1/platform/workflow-health",
    "/api/v1/collector-home",
]


def test_page_load_endpoints_return_200_without_500(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p84-hotfix@example.com")
    headers = auth_headers(token)
    for path in _ENDPOINTS:
        resp = client.get(path, headers=headers)
        assert resp.status_code == 200, (path, resp.text[:500])


def test_daily_actions_list_has_status_envelope(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p84-hotfix-actions@example.com")
    resp = client.get("/api/v1/daily-actions", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "items" in data
    assert data.get("status") in {"OK", "SKIPPED", "ERROR"}


def test_notifications_refresh_disabled_on_get(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p84-hotfix-notif@example.com")
    resp = client.get("/api/v1/notifications?refresh=true", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data.get("status") == "ERROR"
    assert data.get("items") == []


def test_briefings_cached_or_skipped(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p84-hotfix-brief@example.com")
    headers = auth_headers(token)
    for path in ("/api/v1/briefings/daily", "/api/v1/briefings/weekly"):
        resp = client.get(path, headers=headers)
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body.get("status") in {"OK", "SKIPPED", "ERROR"}


def test_command_center_fast_payload(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p84-hotfix-cc@example.com")
    resp = client.get("/api/v1/collector-command-center", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data.get("status") in {"OK", "ERROR"}
    assert "budget_status" in data
    assert data.get("marketplace_deals") == []


def test_workflow_health_no_deep_scan(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p84-hotfix-wh@example.com")
    resp = client.get("/api/v1/platform/workflow-health", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "health_score" in data
    skipped = [i for i in data.get("issues", []) if i.get("issue_type") == "SKIPPED"]
    assert skipped, "expected deep_scan SKIPPED issue"
