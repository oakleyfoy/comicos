from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.services.release_platform_health import get_release_platform_health
from release_platform_test_helpers import seed_release_platform_certification_stack
from test_inventory import register_and_login


def test_release_platform_health_calculates_components(client: TestClient) -> None:
    email = "release-platform-health@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        seed_release_platform_certification_stack(session, owner_user_id=owner_id)
        health = get_release_platform_health(session, owner_user_id=owner_id)
        assert health.overall_status in {"HEALTHY", "WARNING"}
        assert len(health.components) == 8
        codes = {component.component_code for component in health.components}
        assert "release_feed" in codes
        assert "import_pipeline" in codes
