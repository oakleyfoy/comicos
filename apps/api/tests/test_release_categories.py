from __future__ import annotations

from sqlmodel import Session, select

from app.services.release_analytics_service import _compute_categories
from app.services.release_import import import_release_feed
from fastapi.testclient import TestClient
from test_inventory import register_and_login
from test_release_import import _sample_feed

from app.models import User


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_release_category_performance(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p74-cat@example.com")
    owner_id = _owner_id(session, "p74-cat@example.com")
    import_release_feed(session, owner_user_id=owner_id, payload=_sample_feed())
    cats = _compute_categories(session, owner_user_id=owner_id)
    assert isinstance(cats, list)

    resp = client.get(
        "/api/v1/release-monitoring/categories",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    assert isinstance(items, list)
