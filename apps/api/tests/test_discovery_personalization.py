from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.services.p81_discovery_personalization_service import personalize_opportunity_row
from app.services.p77_personalization_engine import load_personalization_context
from test_inventory import auth_headers, register_and_login
from test_p81_discovery_helpers import seed_release_number_one
from app.services.p81_discovery_ingestion import ingest_discovery_opportunities
from app.models.p81_discovery import P81DiscoveryOpportunity


def test_personalized_score_with_profile_boost(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p81-pers@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "p81-pers@example.com")).one().id or 0)
    client.put(
        "/api/v1/collector-profile",
        headers=auth_headers(token),
        json={
            "publishers": [{"interest_type": "PUBLISHER", "label": "DC", "priority_rank": 1}],
            "characters": [{"interest_type": "CHARACTER", "label": "Superman", "priority_rank": 1}],
        },
    )
    seed_release_number_one(session, owner_user_id=owner_id)
    ingest_discovery_opportunities(session, owner_user_id=owner_id)
    row = session.exec(
        select(P81DiscoveryOpportunity).where(P81DiscoveryOpportunity.owner_user_id == owner_id)
    ).first()
    assert row is not None
    ctx = load_personalization_context(session, owner_user_id=owner_id)
    before = float(row.discovery_score)
    read = personalize_opportunity_row(session, owner_user_id=owner_id, row=row, ctx=ctx)
    assert read.personalized_score >= before
    assert read.collector_adjustment > 0

    session.commit()
    api = client.post("/api/v1/discovery/personalized/refresh", headers=auth_headers(token))
    assert api.status_code == 200, api.text
    items = api.json()["data"]["items"]
    assert items
    assert items[0]["personalized_score"] >= items[0]["discovery_score"] - 10
