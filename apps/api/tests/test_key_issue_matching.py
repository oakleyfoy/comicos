from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import ReleaseIssue, ReleaseSeries, User
from app.models.key_issue_intelligence import KeyIssueClassification
from app.services.intelligence_seed import seed_intelligence_catalog
from app.services.key_issue_matching import match_catalog_key_issues_for_owner, match_pattern_key_issues_for_owner
from test_inventory import register_and_login


def test_key_issue_matching_links_spawn_one_and_tmnt_300(client: TestClient) -> None:
    email = "key-issue-matching@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
        seed_intelligence_catalog(session)
        spawn_series = ReleaseSeries(
            owner_user_id=owner_id,
            publisher="Image",
            series_name="Spawn",
            series_type="ONGOING",
            status="ACTIVE",
        )
        tmnt_series = ReleaseSeries(
            owner_user_id=owner_id,
            publisher="IDW",
            series_name="TMNT",
            series_type="ONGOING",
            status="ACTIVE",
        )
        session.add(spawn_series)
        session.add(tmnt_series)
        session.commit()
        session.refresh(spawn_series)
        session.refresh(tmnt_series)
        session.add(
            ReleaseIssue(
                owner_user_id=owner_id,
                release_uuid="ki-spawn-1",
                series_id=int(spawn_series.id or 0),
                issue_number="1",
                title="Spawn #1",
                release_status="SCHEDULED",
            )
        )
        session.add(
            ReleaseIssue(
                owner_user_id=owner_id,
                release_uuid="ki-tmnt-300",
                series_id=int(tmnt_series.id or 0),
                issue_number="300",
                title="TMNT #300",
                release_status="SCHEDULED",
            )
        )
        session.commit()

        catalog_matches = match_catalog_key_issues_for_owner(session, owner_user_id=owner_id)
        pattern_matches = match_pattern_key_issues_for_owner(session, owner_user_id=owner_id)
        assert catalog_matches >= 2
        assert pattern_matches >= 1
        classifications = session.exec(select(KeyIssueClassification)).all()
        assert any(row.classification == "MILESTONE_NUMBERING" for row in classifications)
