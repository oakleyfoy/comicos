from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from test_p66_helpers import seed_p66_owner


def test_quantity_intelligence_split(client: TestClient, session: Session) -> None:
    email = "p66-qty@example.com"
    _, token = seed_p66_owner(client, session, email)
    headers = {"Authorization": f"Bearer {token}"}
    build = client.post("/api/v1/quantity-intelligence/build", headers=headers)
    assert build.status_code == 200
    latest = client.get("/api/v1/quantity-intelligence/latest", headers=headers)
    assert latest.status_code == 200
    items = latest.json()["data"]["items"]
    assert len(items) >= 1
    row = items[0]
    assert row["total_quantity"] == row["collection_quantity"] + row["spec_quantity"] + row["flip_quantity"]
