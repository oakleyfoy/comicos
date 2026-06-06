from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.models.p81_discovery import P81FuturePullListItem
from test_inventory import auth_headers, register_and_login
from test_p81_discovery_helpers import seed_milestone_issue, seed_release_number_one


def test_future_pull_list_pipeline(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p81-fpl@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p81-fpl@example.com")).one().id or 0)
    seed_release_number_one(session, owner_user_id=owner_id)
    seed_milestone_issue(session, owner_user_id=owner_id)

    response = client.get("/api/v1/discovery/future-pull-list?refresh=true", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    items = response.json()["data"]["items"]
    assert len(items) >= 1
    row = items[0]
    assert row["pipeline_status"] in {"DISCOVERED", "WATCHING", "ANNOUNCED", "FOC"}
    assert row["recommendation_action"] in {"BUY", "WATCH", "PASS"}
    assert row["recommendation_quantity"] >= 0

    db_rows = session.exec(select(P81FuturePullListItem).where(P81FuturePullListItem.owner_user_id == owner_id)).all()
    assert len(db_rows) >= 1
