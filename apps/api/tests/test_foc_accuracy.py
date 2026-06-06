from __future__ import annotations

from sqlmodel import Session, select

from app.services.release_analytics_service import _compute_foc_accuracy
from app.services.release_import import import_release_feed
from fastapi.testclient import TestClient
from test_inventory import register_and_login
from test_release_import import _sample_feed

from app.models import User


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_foc_accuracy_metrics(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p74-focacc@example.com")
    owner_id = _owner_id(session, "p74-focacc@example.com")
    import_release_feed(session, owner_user_id=owner_id, payload=_sample_feed())
    foc, _ = _compute_foc_accuracy(session, owner_user_id=owner_id)
    assert foc.accuracy_rate_pct >= 0.0
    assert foc.missed_opportunity_rate_pct >= 0.0

    resp = client.get(
        "/api/v1/release-monitoring/foc-accuracy",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert "accuracy_rate_pct" in body
    assert "upgrade_accuracy_pct" in body
