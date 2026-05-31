from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.models.condition_intelligence import ConditionSubgrade, ScanAnalysis
from app.services.condition_intelligence import create_scan_analysis
from app.services.condition_profile_agent import build_condition_profile
from app.services.defect_detection_agent import detect_condition_defects
from app.services.scan_quality_agent import analyze_scan_quality
from app.services.subgrade_agent import SUBGRADE_TYPES, generate_subgrades
from test_scan_quality_agent import _seed_scan_image
from test_inventory import register_and_login


def test_subgrade_agent_generates_four_subgrades(client: TestClient) -> None:
    email = "subgrade-agent@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == email)).one()
        owner_user_id = int(owner.id or 0)
        image = _seed_scan_image(session, owner_user_id=owner_user_id)
        analysis_read = create_scan_analysis(session, owner_user_id=owner_user_id, front_image_id=int(image.id))
        analysis = session.get(ScanAnalysis, analysis_read.id)
        assert analysis is not None
        analyze_scan_quality(session, analysis=analysis)
        detect_condition_defects(session, analysis=analysis)
        build_condition_profile(session, analysis=analysis)
        subgrades = generate_subgrades(session, analysis=analysis)
        assert len(subgrades) == 4
        assert {row.subgrade_type for row in subgrades} == set(SUBGRADE_TYPES)
        for row in subgrades:
            assert 0 <= row.score <= 100
            assert "grade" not in row.subgrade_type.lower()
        stored = session.exec(select(ConditionSubgrade).where(ConditionSubgrade.analysis_id == analysis.id)).all()
        assert len(stored) == 4
