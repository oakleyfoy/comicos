from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models.creator_intelligence import CreatorProfile
from app.services.intelligence_seed import seed_intelligence_catalog
from test_inventory import register_and_login


def test_creator_intelligence_seed_includes_named_creators(client: TestClient) -> None:
    register_and_login(client, "creator-intelligence@example.com")
    with Session(get_engine()) as session:
        seed_intelligence_catalog(session)
        names = {row.creator_name for row in session.exec(select(CreatorProfile)).all()}
        for required in (
            "Todd McFarlane",
            "Daniel Warren Johnson",
            "Scott Snyder",
            "Donny Cates",
            "Geoff Johns",
            "Jonathan Hickman",
        ):
            assert required in names
