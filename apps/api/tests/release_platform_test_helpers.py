from __future__ import annotations

from datetime import date, timedelta

from sqlmodel import Session

from app.models import ReleaseIssue, ReleaseSeries
from app.models.lunar_feed import LunarFeedRun
from app.models.lunar_scheduler import LunarScheduleConfig
from spec_test_helpers import seed_spec_release_inputs
from app.services.spec_recommendation_agent import run_spec_recommendations
from app.services.spec_scoring_agent import run_spec_scoring


def seed_release_platform_horizons(session: Session, *, owner_user_id: int) -> dict[str, int]:
    ids = seed_spec_release_inputs(session, owner_user_id=owner_user_id)
    today = date.today()

    announced_series = ReleaseSeries(
        owner_user_id=owner_user_id,
        publisher="Image",
        series_name="Future Spec",
        series_type="LIMITED",
        status="ACTIVE",
    )
    session.add(announced_series)
    session.commit()
    session.refresh(announced_series)

    announced_issue = ReleaseIssue(
        owner_user_id=owner_user_id,
        release_uuid=f"platform-announced-{owner_user_id}",
        series_id=int(announced_series.id or 0),
        issue_number="1",
        title="Future Spec #1",
        foc_date=None,
        release_date=today + timedelta(days=120),
        cover_price=5.99,
        release_status="ANNOUNCED",
    )
    session.add(announced_issue)
    session.commit()
    session.refresh(announced_issue)
    return {**ids, "announced_issue_id": int(announced_issue.id or 0)}


def seed_release_platform_certification_stack(session: Session, *, owner_user_id: int) -> dict[str, int]:
    ids = seed_release_platform_horizons(session, owner_user_id=owner_user_id)
    run_spec_scoring(session, owner_user_id=owner_user_id)
    run_spec_recommendations(session, owner_user_id=owner_user_id)
    session.add(
        LunarFeedRun(
            owner_user_id=owner_user_id,
            source_type="LUNAR",
            file_name="certification-fixture.csv",
            file_period="2026-W22",
            status="COMPLETED",
            records_processed=12,
            records_created=4,
            records_updated=8,
        )
    )
    session.add(
        LunarScheduleConfig(
            owner_user_id=owner_user_id,
            enabled=True,
            schedule_type="DAILY",
            schedule_time="06:00",
        )
    )
    session.commit()
    return ids