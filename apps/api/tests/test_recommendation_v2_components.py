from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import ReleaseIssue, ReleaseSeries, User
from app.models.key_issue_intelligence import KeyIssueProfile
from app.services.market_demand_seed import seed_market_demand_baselines
from app.services.recommendation_v2_components import COMPONENT_NAMES, score_issue_components_v2
from app.services.user_preference_engine import create_manual_preference
from test_inventory import register_and_login


def test_component_names_complete() -> None:
    assert "INVESTMENT_NUMBER_ONE_SCORE" in COMPONENT_NAMES
    assert len(COMPONENT_NAMES) == 16


def test_key_issue_can_outrank_random_number_one(client: TestClient, session: Session) -> None:
    email = "rec-v2-key@example.com"
    register_and_login(client, email)
    owner_id = int(session.exec(select(User).where(User.email == email)).one().id or 0)
    seed_market_demand_baselines(session)
    create_manual_preference(
        session,
        owner_user_id=owner_id,
        preference_type="FRANCHISE",
        preference_label="GI Joe",
        preference_score=85.0,
    )

    random_series = ReleaseSeries(
        owner_user_id=owner_id,
        publisher="INDIE",
        series_name="Low Demand ZZZ",
        series_type="LIMITED",
        status="ACTIVE",
    )
    key_series = ReleaseSeries(
        owner_user_id=owner_id,
        publisher="IDW",
        series_name="GI Joe",
        series_type="ONGOING",
        status="ACTIVE",
    )
    session.add(random_series)
    session.add(key_series)
    session.commit()
    session.refresh(random_series)
    session.refresh(key_series)

    random_issue = ReleaseIssue(
        owner_user_id=owner_id,
        release_uuid="key-random-1",
        series_id=int(random_series.id or 0),
        issue_number="1",
        title="Low Demand ZZZ #1",
        release_status="SCHEDULED",
    )
    key_issue = ReleaseIssue(
        owner_user_id=owner_id,
        release_uuid="key-gijoe-25",
        series_id=int(key_series.id or 0),
        issue_number="25",
        title="GI Joe #25",
        release_status="SCHEDULED",
    )
    session.add(random_issue)
    session.add(key_issue)
    session.commit()
    session.refresh(random_issue)
    session.refresh(key_issue)

    session.add(
        KeyIssueProfile(
            release_issue_id=int(key_issue.id or 0),
            key_issue_type="MILESTONE_NUMBERING",
            importance_score=92.0,
            confidence_score=0.9,
            source_version="P51-02",
        )
    )
    session.commit()

    random_bundle = score_issue_components_v2(
        session, owner_user_id=owner_id, issue=random_issue, series=random_series
    )
    key_bundle = score_issue_components_v2(session, owner_user_id=owner_id, issue=key_issue, series=key_series)
    assert key_bundle.total_score > random_bundle.total_score
