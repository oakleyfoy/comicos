from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.models.marketplace import MarketplaceExecution
from app.schemas.shopify import ShopifyConnectRequest
from app.services.marketplace_seed import ensure_marketplace_definitions
from app.services.shopify_accounts import connect_account, disconnect_account, validate_account
from app.services.shopify_connector import reset_shopify_stub_state
from test_inventory import register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_shopify_connector_validate_connect_and_track_executions(client: TestClient) -> None:
    reset_shopify_stub_state()
    register_and_login(client, "shopify-connector@example.com")
    with Session(get_engine()) as session:
        ensure_marketplace_definitions(session)
        owner_id = _owner_id(session, "shopify-connector@example.com")
        executions_before = len(session.exec(select(MarketplaceExecution)).all())

        with pytest.raises(HTTPException):
            connect_account(
                session,
                owner_id=owner_id,
                payload=ShopifyConnectRequest(
                    account_name="Bad Shop",
                    shop_domain="bad-shop.myshopify.com",
                    admin_api_token="invalid-token",
                ),
            )

        account = connect_account(
            session,
            owner_id=owner_id,
            payload=ShopifyConnectRequest(
                account_name="Comic Shop",
                shop_domain="comics.myshopify.com",
                admin_api_token="shopify_valid_token_abc",
            ),
        )
        status = validate_account(session, owner_id=owner_id)
        disconnected = disconnect_account(session, owner_id=owner_id)
        executions_after = len(session.exec(select(MarketplaceExecution)).all())

        assert account.status == "ACTIVE"
        assert status.credentials_valid is True
        assert disconnected.status == "DISABLED"
        assert executions_after > executions_before
