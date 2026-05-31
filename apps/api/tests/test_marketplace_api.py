from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.models.marketplace import MarketplaceDefinition
from app.services.marketplace_execution import start_execution
from app.services.marketplace_seed import ensure_marketplace_definitions
from test_inventory import auth_headers, register_and_login


def _marketplace_id(session: Session, *, code: str) -> int:
    ensure_marketplace_definitions(session)
    row = session.exec(select(MarketplaceDefinition).where(MarketplaceDefinition.marketplace_code == code)).one()
    return int(row.id or 0)


def _user_id(session: Session, *, email: str) -> int:
    row = session.exec(select(User).where(User.email == email)).one()
    return int(row.id or 0)


def test_marketplace_api_lists_seeded_marketplaces(client: TestClient) -> None:
    token = register_and_login(client, "marketplace-api-list@example.com")
    with Session(get_engine()) as session:
        ensure_marketplace_definitions(session)

    response = client.get("/api/v1/marketplaces?limit=20&offset=0", headers=auth_headers(token))

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["meta"]["owner_user_id"] is not None
    assert [row["marketplace_code"] for row in payload["data"]["items"]] == ["EBAY", "HIPCOMIC", "SHOPIFY", "WHATNOT"]


def test_marketplace_api_account_routes_are_owner_scoped(client: TestClient) -> None:
    owner_token = register_and_login(client, "marketplace-api-owner@example.com")
    outsider_token = register_and_login(client, "marketplace-api-outsider@example.com")
    with Session(get_engine()) as session:
        marketplace_id = _marketplace_id(session, code="SHOPIFY")

    created = client.post(
        "/api/v1/marketplace-accounts",
        headers=auth_headers(owner_token),
        json={
            "marketplace_id": marketplace_id,
            "account_name": "API Shopify",
            "account_identifier": "api-shopify-1",
            "status": "ACTIVE",
            "credential_type": "oauth_token",
            "credential_payload": "owner-token",
        },
    )
    assert created.status_code == 201, created.text
    created_data = created.json()["data"]
    account_id = created_data["id"]
    assert "credential_payload" not in created_data
    assert created_data["marketplace"]["marketplace_code"] == "SHOPIFY"

    listing = client.get("/api/v1/marketplace-accounts?limit=20&offset=0", headers=auth_headers(owner_token))
    detail = client.get(f"/api/v1/marketplace-accounts/{account_id}", headers=auth_headers(owner_token))
    denied = client.get(f"/api/v1/marketplace-accounts/{account_id}", headers=auth_headers(outsider_token))
    disabled = client.post(f"/api/v1/marketplace-accounts/{account_id}/disable", headers=auth_headers(owner_token))

    assert listing.status_code == 200, listing.text
    assert detail.status_code == 200, detail.text
    assert denied.status_code == 404, denied.text
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["data"]["status"] == "DISABLED"


def test_marketplace_api_execution_routes_list_and_detail(client: TestClient) -> None:
    token = register_and_login(client, "marketplace-api-execution@example.com")
    with Session(get_engine()) as session:
        owner_id = _user_id(session, email="marketplace-api-execution@example.com")
        marketplace_id = _marketplace_id(session, code="EBAY")

    account = client.post(
        "/api/v1/marketplace-accounts",
        headers=auth_headers(token),
        json={
            "marketplace_id": marketplace_id,
            "account_name": "Execution API Account",
            "account_identifier": "execution-api-account",
            "status": "PENDING",
        },
    )
    assert account.status_code == 201, account.text
    account_id = account.json()["data"]["id"]

    with Session(get_engine()) as session:
        execution = start_execution(
            session,
            marketplace_id=marketplace_id,
            account_id=account_id,
            execution_type="connect.dry_run",
            execution_uuid="api-execution-1",
        )

    listing = client.get("/api/v1/marketplace-executions?limit=20&offset=0", headers=auth_headers(token))
    detail = client.get(f"/api/v1/marketplace-executions/{execution.id}", headers=auth_headers(token))

    assert listing.status_code == 200, listing.text
    assert detail.status_code == 200, detail.text
    assert listing.json()["data"]["items"][0]["execution_uuid"] == "api-execution-1"
    assert detail.json()["data"]["execution"]["execution_uuid"] == "api-execution-1"
    assert detail.json()["data"]["account"]["owner_id"] == owner_id
