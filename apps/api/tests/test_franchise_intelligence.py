from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models.franchise_intelligence import FranchiseProfile
from app.services.intelligence_seed import seed_intelligence_catalog
from test_inventory import register_and_login


def test_franchise_intelligence_seed_includes_collector_franchises(client: TestClient) -> None:
    register_and_login(client, "franchise-intelligence@example.com")
    with Session(get_engine()) as session:
        seed_intelligence_catalog(session)
        names = {row.franchise_name for row in session.exec(select(FranchiseProfile)).all()}
        for required in ("Batman", "Spider-Man", "TMNT", "Transformers", "Invincible", "Star Wars", "X-Men"):
            assert required in names
