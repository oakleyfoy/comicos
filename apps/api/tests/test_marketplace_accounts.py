from __future__ import annotations

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.security import decrypt_secret_value
from app.db.session import get_engine
from app.models import MarketplaceConnectionEvent, User
from app.models.marketplace import (
    MarketplaceCredential as MarketplaceFrameworkCredential,
    MarketplaceDefinition as MarketplaceFrameworkDefinition,
)
from app.schemas.marketplace import MarketplaceAccountCreate
from app.services.marketplace_accounts import create_account, disable_account
from app.services.marketplace_seed import ensure_marketplace_definitions
from test_inventory import auth_headers, register_and_login


def _create_organization(client: TestClient, token: str, *, slug: str) -> int:
    response = client.post(
        "/api/v1/organizations",
        headers=auth_headers(token),
        json={"display_name": slug.replace("-", " ").title(), "slug": slug, "organization_type": "DEALER"},
    )
    assert response.status_code == 201, response.text
    return int(response.json()["data"]["id"])


def _connect_marketplace(
    client: TestClient,
    token: str,
    organization_id: int,
    *,
    marketplace_type: str,
    marketplace_account_id: str,
    display_name: str,
    credential_reference: str,
):
    return client.post(
        f"/api/v1/organizations/{organization_id}/marketplaces/connect",
        headers=auth_headers(token),
        json={
            "marketplace_type": marketplace_type,
            "marketplace_account_id": marketplace_account_id,
            "display_name": display_name,
            "credential_type": "oauth_token",
            "credential_reference": credential_reference,
        },
    )


def test_marketplace_connection_registry_and_deterministic_ordering(client: TestClient) -> None:
    owner = register_and_login(client, "marketplace-owner@example.com")
    organization_id = _create_organization(client, owner, slug="marketplace-org")

    ebay = _connect_marketplace(
        client,
        owner,
        organization_id,
        marketplace_type="ebay",
        marketplace_account_id="ebay-alpha",
        display_name="Alpha eBay",
        credential_reference="vault://marketplace/ebay-alpha",
    )
    shopify = _connect_marketplace(
        client,
        owner,
        organization_id,
        marketplace_type="shopify",
        marketplace_account_id="shopify-zeta",
        display_name="Zeta Shopify",
        credential_reference="vault://marketplace/shopify-zeta",
    )

    assert ebay.status_code == 201, ebay.text
    assert shopify.status_code == 201, shopify.text

    listing = client.get(f"/api/v1/organizations/{organization_id}/marketplaces?limit=20&offset=0", headers=auth_headers(owner))
    assert listing.status_code == 200, listing.text
    payload = listing.json()["data"]
    assert [row["marketplace_type"] for row in payload["items"]] == ["ebay", "shopify"]
    assert [row["marketplace_key"] for row in payload["registry"]] == ["ebay", "whatnot", "shopify"]
    assert payload["permissions"]["can_view"] is True
    assert payload["permissions"]["can_manage"] is True
    assert payload["items"][0]["account_status"] == "connected"
    assert payload["items"][0]["verification_status"] == "pending"


def test_marketplace_connect_is_idempotent_and_detail_is_replay_safe(client: TestClient) -> None:
    owner = register_and_login(client, "marketplace-idempotent-owner@example.com")
    organization_id = _create_organization(client, owner, slug="marketplace-idempotent-org")

    first = _connect_marketplace(
        client,
        owner,
        organization_id,
        marketplace_type="ebay",
        marketplace_account_id="ebay-idem",
        display_name="Idempotent eBay",
        credential_reference="vault://marketplace/ebay-idem",
    )
    second = _connect_marketplace(
        client,
        owner,
        organization_id,
        marketplace_type="ebay",
        marketplace_account_id="ebay-idem",
        display_name="Idempotent eBay",
        credential_reference="vault://marketplace/ebay-idem",
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text
    first_data = first.json()["data"]
    second_data = second.json()["data"]
    assert first_data["account"]["id"] == second_data["account"]["id"]
    assert len(second_data["connection_events"]) == 1
    assert [row["event_type"] for row in second_data["connection_events"]] == ["marketplace_connected"]
    assert [row["credential_reference"] for row in second_data["credentials"]] == ["vault://marketplace/ebay-idem"]


def test_marketplace_verification_disconnect_and_append_only_lineage(client: TestClient) -> None:
    owner = register_and_login(client, "marketplace-lineage-owner@example.com")
    organization_id = _create_organization(client, owner, slug="marketplace-lineage-org")

    connected = _connect_marketplace(
        client,
        owner,
        organization_id,
        marketplace_type="whatnot",
        marketplace_account_id="whatnot-live-1",
        display_name="Whatnot Live",
        credential_reference="vault://marketplace/whatnot-live-1",
    )
    assert connected.status_code == 201, connected.text
    account_id = connected.json()["data"]["account"]["id"]

    failed = client.post(
        f"/api/v1/organizations/{organization_id}/marketplaces/verify",
        headers=auth_headers(owner),
        json={"account_id": account_id, "verification_status": "failed", "reason": "Manual review pending"},
    )
    verified = client.post(
        f"/api/v1/organizations/{organization_id}/marketplaces/verify",
        headers=auth_headers(owner),
        json={"account_id": account_id, "verification_status": "verified"},
    )
    disconnected = client.post(
        f"/api/v1/organizations/{organization_id}/marketplaces/disconnect",
        headers=auth_headers(owner),
        json={"account_id": account_id, "reason": "End of test"},
    )

    assert failed.status_code == 200, failed.text
    assert verified.status_code == 200, verified.text
    assert disconnected.status_code == 200, disconnected.text
    detail = disconnected.json()["data"]
    assert detail["account"]["account_status"] == "disconnected"
    assert detail["account"]["verification_status"] == "verified"
    assert detail["account"]["disconnected_at"] is not None
    assert [row["event_type"] for row in detail["connection_events"]] == [
        "marketplace_connected",
        "marketplace_verification_failed",
        "marketplace_verified",
        "marketplace_disconnected",
    ]


def test_marketplace_org_isolation_and_unauthorized_access_denial(client: TestClient, session: Session) -> None:
    owner = register_and_login(client, "marketplace-isolation-owner@example.com")
    outsider = register_and_login(client, "marketplace-isolation-outsider@example.com")
    organization_id = _create_organization(client, owner, slug="marketplace-isolation-org")
    _create_organization(client, outsider, slug="marketplace-outsider-org")

    connected = _connect_marketplace(
        client,
        owner,
        organization_id,
        marketplace_type="shopify",
        marketplace_account_id="shopify-owner-1",
        display_name="Owner Shopify",
        credential_reference="vault://marketplace/shopify-owner-1",
    )
    assert connected.status_code == 201, connected.text
    account_id = connected.json()["data"]["account"]["id"]

    denied_listing = client.get(f"/api/v1/organizations/{organization_id}/marketplaces", headers=auth_headers(outsider))
    denied_disconnect = client.post(
        f"/api/v1/organizations/{organization_id}/marketplaces/disconnect",
        headers=auth_headers(outsider),
        json={"account_id": account_id, "reason": "Unauthorized"},
    )

    assert denied_listing.status_code == 403, denied_listing.text
    assert denied_disconnect.status_code == 403, denied_disconnect.text

    session.expire_all()
    events = session.exec(
        select(MarketplaceConnectionEvent)
        .where(MarketplaceConnectionEvent.organization_id == organization_id)
        .order_by(MarketplaceConnectionEvent.created_at.asc(), MarketplaceConnectionEvent.id.asc())
    ).all()
    assert events[-2].event_type == "unauthorized_marketplace_access_attempt"
    assert events[-1].event_type == "unauthorized_marketplace_access_attempt"


def test_marketplace_identity_is_owned_by_single_organization(client: TestClient) -> None:
    first_owner = register_and_login(client, "marketplace-first-owner@example.com")
    second_owner = register_and_login(client, "marketplace-second-owner@example.com")
    first_org = _create_organization(client, first_owner, slug="marketplace-first-org")
    second_org = _create_organization(client, second_owner, slug="marketplace-second-org")

    first = _connect_marketplace(
        client,
        first_owner,
        first_org,
        marketplace_type="ebay",
        marketplace_account_id="shared-ebay-account",
        display_name="Shared eBay",
        credential_reference="vault://marketplace/shared-ebay-account",
    )
    second = _connect_marketplace(
        client,
        second_owner,
        second_org,
        marketplace_type="ebay",
        marketplace_account_id="shared-ebay-account",
        display_name="Shared eBay Duplicate",
        credential_reference="vault://marketplace/shared-ebay-account-duplicate",
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 409, second.text


def test_connector_framework_account_create_encrypts_credentials(client: TestClient) -> None:
    register_and_login(client, "connector-framework-owner@example.com")
    with Session(get_engine()) as session:
        ensure_marketplace_definitions(session)
        owner = session.exec(select(User).where(User.email == "connector-framework-owner@example.com")).one()
        marketplace = session.exec(
            select(MarketplaceFrameworkDefinition).where(MarketplaceFrameworkDefinition.marketplace_code == "SHOPIFY")
        ).one()

        account = create_account(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceAccountCreate(
                marketplace_id=int(marketplace.id or 0),
                account_name="Framework Shopify",
                account_identifier="framework-shopify-1",
                status="PENDING",
                credential_type="oauth_token",
                credential_payload="top-secret-token",
            ),
        )

        credential = session.exec(
            select(MarketplaceFrameworkCredential).where(MarketplaceFrameworkCredential.account_id == account.id)
        ).one()
        assert account.status == "PENDING"
        assert account.marketplace is not None
        assert credential.encrypted_payload != "top-secret-token"
        assert decrypt_secret_value(credential.encrypted_payload) == "top-secret-token"


def test_connector_framework_account_disable_is_owner_scoped(client: TestClient) -> None:
    register_and_login(client, "connector-disable-owner@example.com")
    register_and_login(client, "connector-disable-outsider@example.com")
    with Session(get_engine()) as session:
        ensure_marketplace_definitions(session)
        owner = session.exec(select(User).where(User.email == "connector-disable-owner@example.com")).one()
        outsider = session.exec(select(User).where(User.email == "connector-disable-outsider@example.com")).one()
        marketplace = session.exec(
            select(MarketplaceFrameworkDefinition).where(MarketplaceFrameworkDefinition.marketplace_code == "EBAY")
        ).one()

        account = create_account(
            session,
            owner_id=int(owner.id or 0),
            payload=MarketplaceAccountCreate(
                marketplace_id=int(marketplace.id or 0),
                account_name="Disable Me",
                account_identifier="disable-me-1",
                status="ACTIVE",
            ),
        )

        disabled = disable_account(session, owner_id=int(owner.id or 0), account_id=account.id)
        assert disabled.status == "DISABLED"

        try:
            disable_account(session, owner_id=int(outsider.id or 0), account_id=account.id)
        except HTTPException as exc:
            assert exc.status_code == 404
        else:  # pragma: no cover - defensive
            raise AssertionError("Expected owner scoping to hide the account from other users.")
