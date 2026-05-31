from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.services.release_platform_summary import get_release_platform_summary
from release_platform_test_helpers import seed_release_platform_certification_stack
from test_inventory import register_and_login


def test_release_platform_summary_and_readiness_score(client: TestClient) -> None:
    email = "release-platform-summary@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        seed_release_platform_certification_stack(session, owner_user_id=owner_id)
        summary = get_release_platform_summary(session, owner_user_id=owner_id)
        assert summary.total_releases >= 4
        assert summary.total_series >= 4
        assert summary.total_variants >= 1
        assert summary.total_new_number_ones >= 1
        assert summary.total_watchlists >= 1
        assert summary.platform_readiness_score >= 70.0
        assert summary.scheduler.scheduler_enabled is True
        assert summary.import_summary.total_import_runs >= 1
