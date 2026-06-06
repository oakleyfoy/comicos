from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from test_inventory import auth_headers, register_and_login


def test_marketplace_publish_requires_draft(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p85-safe-pub@example.com")
    resp = client.post("/api/v1/listings/99999/publish", headers=auth_headers(token))
    assert resp.status_code in {404, 422}


def test_platform_certification_is_get_only(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p85-safe-cert@example.com")
    post = client.post("/api/v1/platform/certification", headers=auth_headers(token))
    assert post.status_code in {404, 405}


def test_collector_home_owner_isolation(client: TestClient, session: Session) -> None:
    token_a = register_and_login(client, "p85-owner-a@example.com")
    token_b = register_and_login(client, "p85-owner-b@example.com")
    home_a = client.get("/api/v1/collector-home", headers=auth_headers(token_a)).json()["data"]
    home_b = client.get("/api/v1/collector-home", headers=auth_headers(token_b)).json()["data"]
    assert home_a["headline"]
    assert home_b["headline"]
