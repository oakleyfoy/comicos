from __future__ import annotations

from sqlmodel import Session, select

from app.models.p81_discovery import P81DiscoveryOpportunity
from app.services.p81_discovery_ingestion import ingest_discovery_opportunities
from test_inventory import register_and_login
from test_p81_discovery_helpers import seed_external_first_issue, seed_release_number_one


def test_ingest_from_releases_and_catalog(client, session: Session) -> None:
    register_and_login(client, "p81-ingest@example.com")
    from sqlmodel import select as sel
    from app.models import User

    owner_id = int(session.exec(sel(User).where(User.email == "p81-ingest@example.com")).one().id or 0)
    seed_release_number_one(session, owner_user_id=owner_id)
    seed_external_first_issue(session)
    count = ingest_discovery_opportunities(session, owner_user_id=owner_id)
    session.commit()
    assert count >= 2
    rows = session.exec(select(P81DiscoveryOpportunity).where(P81DiscoveryOpportunity.owner_user_id == owner_id)).all()
    assert len(rows) >= 2
    types = {r.opportunity_type for r in rows}
    assert "NEW_1" in types or "NEW_SERIES" in types
