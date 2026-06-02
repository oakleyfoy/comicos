from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlmodel import select
from sqlmodel import Session

from app.db.session import get_engine
from app.models import ReleaseIssue, ReleaseSeries, User
from app.models.spec_intelligence import SpecRecommendation
from app.services.foc_dates import utc_today
from app.services.recommendation_forward_window import issue_in_forward_recommendation_window
from app.services.spec_recommendation_agent import list_recommendations_for_owner, run_spec_recommendations
from app.services.spec_review import mark_accepted, mark_dismissed, mark_reviewed
from app.services.spec_scoring_agent import run_spec_scoring
from spec_test_helpers import seed_spec_release_inputs


def test_spec_recommendations_idempotent_rerun(client: TestClient) -> None:
    with Session(get_engine()) as session:
        owner = User(email="spec-idem@example.com", password_hash="x", is_active=True)
        session.add(owner)
        session.commit()
        session.refresh(owner)
        owner_user_id = int(owner.id or 0)
        seed_spec_release_inputs(session, owner_user_id=owner_user_id)
        run_spec_scoring(session, owner_user_id=owner_user_id)
        first, _ = run_spec_recommendations(session, owner_user_id=owner_user_id)
        assert len(first) == 3
        total = len(session.exec(select(SpecRecommendation)).all())
        second, _ = run_spec_recommendations(session, owner_user_id=owner_user_id)
        assert len(second) == 0
        assert len(session.exec(select(SpecRecommendation)).all()) == total


def test_spec_recommendations_forward_window_bounded_catalog(client: TestClient) -> None:
    with Session(get_engine()) as session:
        owner = User(email="spec-bounded@example.com", password_hash="x", is_active=True)
        session.add(owner)
        session.commit()
        session.refresh(owner)
        owner_user_id = int(owner.id or 0)
        today = utc_today()
        series = ReleaseSeries(
            owner_user_id=owner_user_id,
            publisher="Marvel",
            series_name="Bounded Catalog",
            series_type="ONGOING",
            status="ACTIVE",
        )
        session.add(series)
        session.commit()
        session.refresh(series)
        series_id = int(series.id or 0)
        for index in range(30):
            in_window = index < 4
            foc_date = today + timedelta(days=10 if in_window else 500 + index)
            session.add(
                ReleaseIssue(
                    owner_user_id=owner_user_id,
                    release_uuid=f"bounded-{owner_user_id}-{index}",
                    series_id=series_id,
                    issue_number=str(index + 1),
                    title=f"Bounded #{index + 1}",
                    release_status="SCHEDULED",
                    foc_date=foc_date,
                    release_date=foc_date + timedelta(days=21),
                )
            )
        session.commit()
        run_spec_scoring(session, owner_user_id=owner_user_id)
        created, _ = run_spec_recommendations(session, owner_user_id=owner_user_id)
        in_window_count = sum(
            1
            for issue in session.exec(
                select(ReleaseIssue).where(ReleaseIssue.owner_user_id == owner_user_id)
            ).all()
            if issue_in_forward_recommendation_window(issue, today=today)
        )
        assert in_window_count == 4
        assert len(created) == 4


def test_spec_recommendations_and_reviews_are_append_only(client: TestClient) -> None:
    with Session(get_engine()) as session:
        owner = User(email="spec-recommendations@example.com", password_hash="x", is_active=True)
        session.add(owner)
        session.commit()
        session.refresh(owner)
        owner_user_id = int(owner.id or 0)

        seed_spec_release_inputs(session, owner_user_id=owner_user_id)
        run_spec_scoring(session, owner_user_id=owner_user_id)
        created, execution = run_spec_recommendations(session, owner_user_id=owner_user_id)

        assert execution.agent_code == "spec_recommendation"
        assert len(created) == 3
        assert {row.recommendation_type for row in created} >= {"STRONG_BUY", "BUY", "PASS"}

        recommendation_id = created[0].id
        reviewed = mark_reviewed(
            session, owner_user_id=owner_user_id, recommendation_id=recommendation_id, review_notes="Manual look"
        )
        accepted = mark_accepted(session, owner_user_id=owner_user_id, recommendation_id=recommendation_id)
        dismissed = mark_dismissed(
            session, owner_user_id=owner_user_id, recommendation_id=recommendation_id, review_notes="Not this week"
        )

        assert reviewed.review.review_status == "REVIEWED"
        assert accepted.review.review_status == "ACCEPTED"
        assert dismissed.review.review_status == "DISMISSED"

        listed, total = list_recommendations_for_owner(session, owner_user_id=owner_user_id, limit=10, offset=0)
        assert total == 3
        assert len(listed) == 3
        assert session.exec(select(SpecRecommendation)).all()
