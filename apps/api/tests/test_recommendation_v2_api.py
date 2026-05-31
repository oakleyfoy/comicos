from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.services.recommendation_v2_comparison import compare_v1_v2_recommendations
from release_platform_test_helpers import seed_release_platform_horizons
from test_inventory import auth_headers, register_and_login


def test_recommendation_v2_api(client: TestClient, session: Session) -> None:
    email = "rec-v2-api@example.com"
    token = register_and_login(client, email)
    owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
    seed_release_platform_horizons(session, owner_user_id=owner_id)

    run = client.post("/api/v1/recommendations-v2/run", headers=auth_headers(token))
    listing = client.get("/api/v1/recommendations-v2", headers=auth_headers(token))
    top = client.get("/api/v1/recommendations-v2/top", headers=auth_headers(token))
    weekly = client.get("/api/v1/recommendations-v2/weekly-buy-list", headers=auth_headers(token))

    assert run.status_code == 200, run.text
    assert listing.status_code == 200, listing.text
    assert top.status_code == 200
    assert weekly.status_code == 200
    assert run.json()["data"]["recommendations_created"] >= 1

    first_id = listing.json()["data"]["items"][0]["id"]
    detail = client.get(f"/api/v1/recommendations-v2/{first_id}", headers=auth_headers(token))
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"]["components"]

    comparison = compare_v1_v2_recommendations(session, owner_user_id=owner_id, limit=50)
    assert comparison.v2_sample_size >= 0
