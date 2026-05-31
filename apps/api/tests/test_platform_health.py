from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.models.operations_reliability import PlatformHealthCheck
from app.services.platform_health import check_database_health, check_platform_health
from test_inventory import register_and_login


def test_check_platform_health_creates_append_only_checks(client: TestClient) -> None:
    register_and_login(client, "platform-health-owner@example.com")

    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == "platform-health-owner@example.com")).one()
        owner_user_id = int(owner.id or 0)
        before = len(session.exec(select(PlatformHealthCheck)).all())
        checks = check_platform_health(session, owner_user_id=owner_user_id)
        after = len(session.exec(select(PlatformHealthCheck)).all())
        db_check = check_database_health(session, owner_user_id=owner_user_id)

    assert len(checks) == 5
    assert after == before + 5
    assert all(check.check_payload_json.get("owner_user_id") == owner_user_id for check in checks)
    assert db_check.health_status == "HEALTHY"
