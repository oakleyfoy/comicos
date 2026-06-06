"""P82 marketplace acquisition intelligence (distinct from P55 marketplace-acquisitions API)."""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import InventoryCopy, User
from test_inventory import auth_headers, create_order, register_and_login


def _seed_inventory(client: TestClient, session: Session, email: str) -> int:
    token = register_and_login(client, email)
    owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
    create_order(
        client,
        token,
        items=[
            {
                "title": "Battle Beast",
                "publisher": "Image",
                "issue_number": "1",
                "cover_name": "Cover A",
                "quantity": 1,
                "raw_item_price": 5.0,
            }
        ],
    )
    for copy in session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).all():
        copy.current_fmv = Decimal("40.00")
        session.add(copy)
    session.commit()
    return owner_id


def test_p82_scan_opportunity_score_and_spread(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p82-scan@example.com")
    resp = client.post(
        "/api/v1/marketplace-acquisition/scan",
        headers=auth_headers(token),
        json={
            "marketplace": "EBAY",
            "external_listing_id": "P82-TEST-1",
            "title": "Amazing Hero #1 NM",
            "publisher": "DC",
            "series": "Amazing Hero",
            "issue": "1",
            "asking_price": 12.0,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["opportunity_score"] > 0
    assert data["discount_to_fmv"] >= 0
    assert data["recommendation"] in {"STRONG_BUY", "GOOD_BUY", "WATCH", "PASS"}


def test_p82_list_and_dashboard(client: TestClient, session: Session) -> None:
    email = "p82-dash@example.com"
    token = register_and_login(client, email)
    _seed_inventory(client, session, email)
    dash = client.get("/api/v1/marketplace-acquisition/dashboard?refresh=true", headers=auth_headers(token))
    assert dash.status_code == 200
    body = dash.json()["data"]
    assert "strong_buys" in body
    listed = client.get("/api/v1/marketplace-acquisition/opportunities?refresh=false", headers=auth_headers(token))
    assert listed.json()["data"]["pagination"]["total_count"] >= 1
    opp_id = listed.json()["data"]["items"][0]["id"]
    detail = client.get(f"/api/v1/marketplace-acquisition/opportunities/{opp_id}", headers=auth_headers(token))
    assert detail.status_code == 200
