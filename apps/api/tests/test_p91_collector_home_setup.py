from __future__ import annotations

from fastapi.testclient import TestClient

from test_inventory import auth_headers, register_and_login


def test_mark_recommendations_viewed(client: TestClient) -> None:
    token = register_and_login(client, "p91-rec-view@example.com")
    status = client.get("/api/v1/collector-home/setup-status", headers=auth_headers(token))
    assert status.json()["data"]["recommendations_viewed"] is False

    marked = client.post(
        "/api/v1/collector-profile/recommendations/mark-viewed",
        headers=auth_headers(token),
    )
    assert marked.status_code == 200, marked.text
    assert marked.json()["data"]["recommendations_viewed"] is True

    again = client.post(
        "/api/v1/collector-profile/recommendations/mark-viewed",
        headers=auth_headers(token),
    )
    assert again.status_code == 200
    assert again.json()["data"]["recommendations_viewed"] is True


def test_setup_status_percent_and_import_review_rules(client: TestClient) -> None:
    token = register_and_login(client, "p91-setup-rules@example.com")
    resp = client.get("/api/v1/collector-home/setup-status", headers=auth_headers(token))
    data = resp.json()["data"]
    assert data["has_any_import"] is False
    assert data["imports_review_complete"] is False
    assert data["percent_complete"] == 0
    assert "total_count" in data
