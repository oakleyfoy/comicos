"""Smoke: P62/P63/P64 intelligence GET routes return Scan API v1 envelopes."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from tests.test_buy_queue_intelligence import _owner_id, _seed_catalog, register_and_login

INTELLIGENCE_GET_PATHS = [
    "/api/v1/recommendation-intelligence/buy-queue/latest",
    "/api/v1/recommendation-intelligence/foc/latest",
    "/api/v1/recommendation-intelligence/pull-forecast/latest",
    "/api/v1/recommendation-intelligence/watchlists/latest",
    "/api/v1/market-intelligence/portfolio/latest",
    "/api/v1/market-intelligence/sell-signals/latest",
    "/api/v1/market-intelligence/acquisition/latest",
    "/api/v1/market-intelligence/signals/latest",
    "/api/v1/collector-assistant/dashboard/latest",
    "/api/v1/collector-assistant/briefing/latest",
    "/api/v1/collector-assistant/recommendations/latest",
]


def test_intelligence_latest_endpoints_smoke(client: TestClient, session: Session) -> None:
    email = "intelligence-smoke@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _seed_catalog(session, owner_id)
    headers = {"Authorization": f"Bearer {token}"}

    for path in INTELLIGENCE_GET_PATHS:
        response = client.get(path, headers=headers)
        assert response.status_code == 200, f"{path} -> {response.status_code} {response.text[:200]}"
        payload = response.json()
        assert "data" in payload, path
        envelope_owner = payload.get("owner_user_id") or (payload.get("meta") or {}).get("owner_user_id")
        assert int(envelope_owner) == owner_id, path
