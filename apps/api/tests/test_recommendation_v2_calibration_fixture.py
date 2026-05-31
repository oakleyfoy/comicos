from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.services.recommendation_v2_calibration_fixture import (
    assert_fixture_ranking_passes,
    dominant_ranking_driver,
    score_calibration_fixture,
    seed_calibration_fixture,
)
from test_inventory import register_and_login


def test_calibration_fixture_ranking(client: TestClient, session: Session) -> None:
    email = "rec-v2-cal-fixture@example.com"
    register_and_login(client, email)
    owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
    refs = seed_calibration_fixture(session, owner_user_id=owner_id)
    rows = score_calibration_fixture(session, owner_user_id=owner_id, refs=refs)
    assert len(rows) == 10
    assert_fixture_ranking_passes(rows)


def test_fixture_surfaces_run_start_or_post_total_dominance(client: TestClient, session: Session) -> None:
    email = "rec-v2-cal-fixture-diag@example.com"
    register_and_login(client, email)
    owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
    refs = seed_calibration_fixture(session, owner_user_id=owner_id)
    rows = score_calibration_fixture(session, owner_user_id=owner_id, refs=refs)
    drivers = {dominant_ranking_driver(r.bundle)[0] for r in rows}
    assert drivers, "Expected per-row dominant driver labels"
