from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.models.marketplace import MarketplaceExecution
from app.schemas.whatnot import WhatnotConnectRequest
from app.services.marketplace_seed import ensure_marketplace_definitions
from app.services.whatnot_accounts import connect_account, disconnect_account, validate_account
from app.services.whatnot_connector import reset_whatnot_stub_state
from test_inventory import register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_whatnot_connector_validate_connect_and_track_executions(client: TestClient) -> None:
    reset_whatnot_stub_state()
    register_and_login(client, "whatnot-connector@example.com")
    with Session(get_engine()) as session:
        ensure_marketplace_definitions(session)
        owner_id = _owner_id(session, "whatnot-connector@example.com")
        executions_before = len(session.exec(select(MarketplaceExecution)).all())

        with pytest.raises(HTTPException):
            connect_account(
                session,
                owner_id=owner_id,
                payload=WhatnotConnectRequest(
                    account_name="Bad",
                    account_identifier="bad-whatnot",
                    api_token="invalid-token",
                ),
            )

        account = connect_account(
            session,
            owner_id=owner_id,
            payload=WhatnotConnectRequest(
                account_name="Whatnot Shop",
                account_identifier="whatnot-shop-1",
                api_token="whatnot_valid_token_abc",
            ),
        )
        status = validate_account(session, owner_id=owner_id)
        disconnected = disconnect_account(session, owner_id=owner_id)
        executions_after = len(session.exec(select(MarketplaceExecution)).all())

        assert account.status == "ACTIVE"
        assert status.credentials_valid is True
        assert disconnected.status == "DISABLED"
        assert executions_after > executions_before
