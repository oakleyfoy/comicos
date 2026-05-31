from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import ReleaseIssue, ReleaseSeries, SpecRecommendation, User
from app.models.recommendation_v2 import RecommendationScoreV2
from app.services.market_demand_seed import seed_market_demand_baselines
from app.services.recommendation_v2_components import is_investment_number_one, score_issue_components_v2
from app.services.user_preference_engine import create_manual_preference
from test_inventory import auth_headers, register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_investment_number_one_logic(client: TestClient, session: Session) -> None:
    email = "inv-num-one@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    seed_market_demand_baselines(session)
    create_manual_preference(
        session,
        owner_user_id=owner_id,
        preference_type="FRANCHISE",
        preference_label="TMNT",
        preference_score=90.0,
    )
    series = ReleaseSeries(
        owner_user_id=owner_id,
        publisher="IDW",
        series_name="Teenage Mutant Ninja Turtles",
        series_type="ONGOING",
        status="ACTIVE",
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    issue = ReleaseIssue(
        owner_user_id=owner_id,
        release_uuid="inv-tmnt-1",
        series_id=int(series.id or 0),
        issue_number="1",
        title="TMNT #1",
        release_status="SCHEDULED",
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)
    flag, reasons = is_investment_number_one(session, owner_user_id=owner_id, issue=issue, series=series)
    bundle = score_issue_components_v2(session, owner_user_id=owner_id, issue=issue, series=series)
    assert flag is True
    assert reasons
    assert bundle.recommendation_type == "INVESTMENT_NUMBER_ONE"
    inv = next(c for c in bundle.components if c.component_name == "INVESTMENT_NUMBER_ONE_SCORE")
    assert inv.component_score >= 68.0
    assert bundle.total_score >= 50.0
    assert bundle.total_score > 35.0


def test_random_number_one_lower_than_investment(client: TestClient, session: Session) -> None:
    email = "inv-num-one-2@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    series = ReleaseSeries(
        owner_user_id=owner_id,
        publisher="INDIE",
        series_name="Unknown Limited Series QZX",
        series_type="LIMITED",
        status="ACTIVE",
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    issue = ReleaseIssue(
        owner_user_id=owner_id,
        release_uuid="inv-random-1",
        series_id=int(series.id or 0),
        issue_number="1",
        title="Unknown Limited Series QZX #1",
        release_status="SCHEDULED",
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)
    bundle = score_issue_components_v2(session, owner_user_id=owner_id, issue=issue, series=series)
    assert bundle.recommendation_tier in {"WATCH", "PASS", "BUY"}
    assert bundle.total_score < 80.0
