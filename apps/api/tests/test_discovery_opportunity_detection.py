from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.models.p81_discovery import P81DiscoveryOpportunity
from test_inventory import auth_headers, register_and_login
from test_p81_discovery_helpers import seed_milestone_issue, seed_release_number_one


def test_detect_new_series_and_milestone(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p81-detect@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p81-detect@example.com")).one().id or 0)
    seed_release_number_one(session, owner_user_id=owner_id)
    seed_milestone_issue(session, owner_user_id=owner_id)

    response = client.get("/api/v1/discovery/opportunities?refresh=true", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    items = response.json()["data"]["items"]
    assert len(items) >= 2
    scores = [i["discovery_score"] for i in items]
    assert max(scores) >= 50
    rows = session.exec(select(P81DiscoveryOpportunity).where(P81DiscoveryOpportunity.owner_user_id == owner_id)).all()
    assert any(r.opportunity_type == "MILESTONE" for r in rows)
