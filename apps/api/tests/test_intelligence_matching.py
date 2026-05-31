from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.models.intelligence_matching import ReleaseIntelligenceMatch
from app.services.intelligence_matching import ENTITY_FRANCHISE, match_release_issue, sync_owner_release_matches
from app.services.intelligence_seed import seed_intelligence_catalog
from release_platform_test_helpers import seed_release_platform_horizons
from test_inventory import register_and_login


def test_intelligence_matching_links_batman_franchise(client: TestClient) -> None:
    email = "intelligence-matching@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        seed_intelligence_catalog(session)
        seed_release_platform_horizons(session, owner_user_id=owner_id)
        from app.models.release_intelligence import ReleaseIssue, ReleaseSeries

        issue = session.exec(select(ReleaseIssue).where(ReleaseIssue.owner_user_id == owner_id)).first()
        assert issue is not None
        series = session.exec(select(ReleaseSeries).where(ReleaseSeries.id == issue.series_id)).one()
        result = match_release_issue(session, issue=issue, series=series)
        assert any(row.entity_type == ENTITY_FRANCHISE for row in result.matched_entities)
        assert result.combined_popularity_score > 0
        synced = sync_owner_release_matches(session, owner_user_id=owner_id)
        assert synced >= 1
        assert session.exec(select(ReleaseIntelligenceMatch).where(ReleaseIntelligenceMatch.owner_user_id == owner_id)).first()
