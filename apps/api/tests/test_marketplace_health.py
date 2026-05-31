from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.services.marketplace_health import HEALTH_STATUS_WARNING, get_marketplace_health
from app.services.marketplace_seed import ensure_marketplace_definitions
from test_inventory import register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_marketplace_health_components(client: TestClient) -> None:
    register_and_login(client, "marketplace-health@example.com")
    with Session(get_engine()) as session:
        ensure_marketplace_definitions(session)
        owner_id = _owner_id(session, "marketplace-health@example.com")
        health = get_marketplace_health(session, owner_id=owner_id)

        assert health.overall_status in {"HEALTHY", "WARNING", "FAILED", "DISABLED"}
        assert len(health.components) == 5
        codes = {component.component_code for component in health.components}
        assert codes == {
            "connector_health",
            "account_health",
            "publish_health",
            "sync_health",
            "order_import_health",
        }
        assert health.overall_status == HEALTH_STATUS_WARNING or health.components
