from __future__ import annotations

from sqlmodel import Session, select

from app.services.release_analytics_service import _compute_quantity_accuracy
from app.services.release_import import import_release_feed
from fastapi.testclient import TestClient
from test_inventory import register_and_login
from test_release_import import _sample_feed

from app.models import User


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_quantity_accuracy_metrics(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p74-qtyacc@example.com")
    owner_id = _owner_id(session, "p74-qtyacc@example.com")
    import_release_feed(session, owner_user_id=owner_id, payload=_sample_feed())
    qty, _ = _compute_quantity_accuracy(session, owner_user_id=owner_id)
    assert qty.success_rate_pct >= 0.0
    assert qty.average_roi_pct >= 0.0
    assert isinstance(qty.by_action, dict)

    resp = client.get(
        "/api/v1/release-monitoring/performance",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    perf = resp.json()["data"]
    assert "quantity_accuracy" in perf
    assert "foc_accuracy" in perf
