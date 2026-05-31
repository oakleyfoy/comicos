from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models.production_readiness import ProductionCertification
from app.services.production_certification import (
    calculate_readiness_score,
    generate_certification,
    generate_go_live_assessment,
)
from app.services.production_readiness import CHECK_STATUS_PASS, CHECK_STATUS_WARNING, validate_production_readiness


def test_calculate_readiness_score_is_deterministic() -> None:
    assert calculate_readiness_score([CHECK_STATUS_PASS, CHECK_STATUS_PASS]) == 100.0
    assert calculate_readiness_score([CHECK_STATUS_PASS, CHECK_STATUS_WARNING]) == 85.0
    assert calculate_readiness_score([CHECK_STATUS_WARNING]) == 70.0


def test_certification_history_is_retained(client: TestClient) -> None:
    owner_user_id = 9001
    with Session(get_engine()) as session:
        validate_production_readiness(session, owner_user_id=owner_user_id)
        first = generate_certification(session, owner_user_id=owner_user_id)
        second = generate_certification(session, owner_user_id=owner_user_id)
        assessment = generate_go_live_assessment(session, owner_user_id=owner_user_id, certification=second)

        cert_rows = session.exec(select(ProductionCertification)).all()
        assert len(cert_rows) >= 2
        assert first.certification_uuid != second.certification_uuid
        assert assessment.assessment_uuid
        assert second.readiness_score >= 0.0
