from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models.character_intelligence import CharacterProfile
from app.models.creator_intelligence import CreatorProfile
from app.models.franchise_intelligence import FranchiseProfile
from app.services.intelligence_seed import seed_intelligence_catalog
from test_inventory import register_and_login


def test_character_intelligence_seed_meets_minimum_catalog(client: TestClient) -> None:
    register_and_login(client, "character-intelligence@example.com")
    with Session(get_engine()) as session:
        summary = seed_intelligence_catalog(session)
        assert summary.character_count >= 100
        assert summary.franchise_count >= 50
        assert summary.creator_count >= 100
        names = {row.character_name for row in session.exec(select(CharacterProfile)).all()}
        for required in ("Batman", "Spider-Man", "Venom", "Wolverine", "Deadpool"):
            assert required in names
