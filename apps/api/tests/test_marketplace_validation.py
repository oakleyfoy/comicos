from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.services.marketplace_seed import ensure_marketplace_definitions
from app.services.marketplace_validation import (
    PLATFORM_STATUS_PASS,
    PLATFORM_STATUS_WARNING,
    validate_connectors,
    validate_marketplace_platform,
)
from test_inventory import register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_marketplace_validation_connectors_and_platform(client: TestClient) -> None:
    register_and_login(client, "marketplace-validation@example.com")
    with Session(get_engine()) as session:
        ensure_marketplace_definitions(session)
        owner_id = _owner_id(session, "marketplace-validation@example.com")
        connectors = validate_connectors(session, owner_id=owner_id)
        platform = validate_marketplace_platform(session, owner_id=owner_id)

        assert connectors.status in {PLATFORM_STATUS_PASS, PLATFORM_STATUS_WARNING}
        assert platform.overall_status in {PLATFORM_STATUS_PASS, PLATFORM_STATUS_WARNING}
        assert len(platform.checks) == 6
        assert {check.check_code for check in platform.checks} == {
            "connectors",
            "accounts",
            "listings",
            "publish_engine",
            "inventory_sync",
            "order_import",
        }
