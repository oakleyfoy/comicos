from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from test_inventory import auth_headers, register_and_login


def test_daily_and_weekly_briefings(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p84-brief@example.com")
    daily = client.get("/api/v1/briefings/daily", headers=auth_headers(token))
    assert daily.status_code == 200
    assert daily.json()["data"]["briefing_type"] == "DAILY"
    assert len(daily.json()["data"]["top_actions"]) >= 1
    weekly = client.get("/api/v1/briefings/weekly", headers=auth_headers(token))
    assert weekly.status_code == 200
    assert weekly.json()["data"]["briefing_type"] == "WEEKLY"
    gen = client.post("/api/v1/briefings/generate?briefing_type=BOTH", headers=auth_headers(token))
    assert gen.status_code == 200
    assert "daily" in gen.json()["data"] or "weekly" in gen.json()["data"]
