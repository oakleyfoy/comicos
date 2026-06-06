from __future__ import annotations

from pathlib import Path

from app.services.release_intelligence_certification import run_release_intelligence_certification
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from test_inventory import register_and_login
from test_release_import import _sample_feed

from app.models import User
from app.services.release_import import import_release_feed


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_p74_certification_passes(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p74-cert@example.com")
    owner_id = _owner_id(session, "p74-cert@example.com")
    import_release_feed(session, owner_user_id=owner_id, payload=_sample_feed())
    cert = run_release_intelligence_certification(session, owner_user_id=owner_id)
    assert cert.approved_for_production is True
    assert cert.platform_status == "APPROVED_FOR_PRODUCTION"
    assert all(c.passed for c in cert.checks)

    resp = client.get(
        "/api/v1/release-monitoring/certification",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["approved_for_production"] is True


def test_p74_production_review_doc_exists() -> None:
    path = Path(__file__).resolve().parents[3] / "docs" / "P74_PRODUCTION_REVIEW.md"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "APPROVED_FOR_PRODUCTION" in text
    assert "P74-01" in text and "P74-03" in text
