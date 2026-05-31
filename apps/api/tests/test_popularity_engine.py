from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db.session import get_engine
from app.services.intelligence_seed import seed_intelligence_catalog
from app.services.popularity_engine import combined_popularity_score, refresh_popularity_scores
from test_inventory import register_and_login


def test_popularity_engine_is_deterministic(client: TestClient) -> None:
    register_and_login(client, "popularity-engine@example.com")
    with Session(get_engine()) as session:
        seed_intelligence_catalog(session)
        first = refresh_popularity_scores(session)
        second = refresh_popularity_scores(session)
        assert first == 0
        assert second == 0
        assert combined_popularity_score(character=90.0, franchise=80.0, creator=70.0) == 82.5
