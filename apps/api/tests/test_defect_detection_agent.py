from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.models.condition_intelligence import ConditionDefect, ScanAnalysis
from app.services.condition_intelligence import create_scan_analysis
from app.services.defect_detection_agent import detect_condition_defects
from test_scan_quality_agent import _seed_scan_image
from test_inventory import register_and_login


def test_defect_detection_agent_creates_defects(client: TestClient) -> None:
    email = "defect-detect@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == email)).one()
        owner_user_id = int(owner.id or 0)
        image = _seed_scan_image(session, owner_user_id=owner_user_id)
        analysis_read = create_scan_analysis(session, owner_user_id=owner_user_id, front_image_id=int(image.id))
        analysis = session.get(ScanAnalysis, analysis_read.id)
        assert analysis is not None
        defects = detect_condition_defects(session, analysis=analysis)
        assert len(defects) >= 1
        types = {row.defect_type for row in defects}
        assert types.issubset(
            {
                "CORNER_WEAR",
                "EDGE_WEAR",
                "SURFACE_DEFECT",
                "CREASE",
                "SCRATCH",
                "STAIN",
                "WHITENING",
                "PRINT_DEFECT",
                "REGISTRATION_ISSUE",
            }
        )
        stored = session.exec(select(ConditionDefect).where(ConditionDefect.analysis_id == analysis.id)).all()
        assert len(stored) == len(defects)
