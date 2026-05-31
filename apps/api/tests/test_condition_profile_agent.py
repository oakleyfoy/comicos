from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.models.condition_intelligence import ScanAnalysis
from app.services.condition_intelligence import create_scan_analysis
from app.services.condition_profile_agent import build_condition_profile, calculate_condition_score
from app.services.defect_detection_agent import detect_condition_defects
from app.services.scan_quality_agent import analyze_scan_quality
from test_scan_quality_agent import _seed_scan_image
from test_inventory import register_and_login


def test_condition_profile_agent(client: TestClient) -> None:
    email = "condition-profile@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == email)).one()
        owner_user_id = int(owner.id or 0)
        image = _seed_scan_image(session, owner_user_id=owner_user_id)
        analysis_read = create_scan_analysis(session, owner_user_id=owner_user_id, front_image_id=int(image.id))
        analysis = session.get(ScanAnalysis, analysis_read.id)
        assert analysis is not None
        analyze_scan_quality(session, analysis=analysis)
        session.refresh(analysis)
        detect_condition_defects(session, analysis=analysis)
        session.refresh(analysis)
        profile = build_condition_profile(session, analysis=analysis)
        assert 0 <= profile.overall_condition_score <= 100
        assert 0 <= profile.confidence_score <= 1
        score, confidence = calculate_condition_score(quality_score=80.0, defects=[])
        assert score == 80.0
