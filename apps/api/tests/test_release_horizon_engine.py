from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db.session import get_engine
from app.models import User
from app.services.release_horizon_engine import build_release_horizons
from release_platform_test_helpers import seed_release_platform_horizons


def test_release_horizon_engine_buckets_future_releases(client: TestClient) -> None:
    with Session(get_engine()) as session:
        owner = User(email="horizon@example.com", password_hash="x", is_active=True)
        session.add(owner)
        session.commit()
        session.refresh(owner)
        owner_user_id = int(owner.id or 0)
        seed_release_platform_horizons(session, owner_user_id=owner_user_id)

        horizons = build_release_horizons(session, owner_user_id=owner_user_id)
        assert horizons.announced
        assert horizons.next_30_days or horizons.next_60_days or horizons.next_90_days
        assert all(row.horizon for row in horizons.announced)

        today = date.today()
        for row in horizons.next_30_days:
            assert row.issue.release_date is not None
            assert 0 <= (row.issue.release_date - today).days <= 30

        announced_primary = {row.horizon for row in horizons.announced}
        assert "ANNOUNCED" in announced_primary
        if horizons.next_90_days:
            today = date.today()
            for row in horizons.next_90_days:
                assert row.issue.release_date is not None
                assert 0 <= (row.issue.release_date - today).days <= 90
