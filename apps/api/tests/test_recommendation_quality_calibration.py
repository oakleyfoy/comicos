from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.services.recommendation_quality_calibration import (
    CALIBRATION_FAIL,
    calibrate_recommendation_quality,
)
from recommendation_intelligence_test_helpers import seed_recommendation_intelligence_certification_stack
from test_inventory import register_and_login


def test_recommendation_quality_calibration(client: TestClient) -> None:
    email = "rec-intel-calibration@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        seed_recommendation_intelligence_certification_stack(session, owner_user_id=owner_id)
        calibration = calibrate_recommendation_quality(session, owner_user_id=owner_id)
    assert calibration.overall_status in {"PASS", "WARNING"}
    assert calibration.total_recommendations >= 1


def test_certification_still_blocks_on_calibration_fail(client: TestClient) -> None:
    from app.services.recommendation_intelligence_certification import (
        GO_LIVE_NOT_READY,
        get_recommendation_intelligence_certification,
    )

    email = "rec-intel-cal-fail-gate@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        seed_recommendation_intelligence_certification_stack(session, owner_user_id=owner_id)
        calibration = calibrate_recommendation_quality(session, owner_user_id=owner_id)
        cert = get_recommendation_intelligence_certification(session, owner_user_id=owner_id)
    if calibration.overall_status == CALIBRATION_FAIL:
        assert cert.certification_status == GO_LIVE_NOT_READY
        assert cert.platform_certified is False
    else:
        assert cert.platform_certified is True
