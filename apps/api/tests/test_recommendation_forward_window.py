from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import ReleaseIssue, ReleaseSeries, User
from app.services.recommendation_forward_window import (
    FORWARD_RECOMMENDATION_WINDOW_DAYS,
    compute_forward_catalog_priority,
    issue_in_forward_recommendation_window,
)
from app.services.unified_collector_intelligence import (
    generate_unified_collector_recommendations,
    list_latest_unified_collector_recommendations,
)
from test_inventory import register_and_login


def test_forward_window_is_90_days() -> None:
    assert FORWARD_RECOMMENDATION_WINDOW_DAYS == 90


def test_issue_in_forward_window_by_foc_and_release() -> None:
    today = date.today()
    far_foc = ReleaseIssue(
        owner_user_id=1,
        release_uuid="fwd-far-foc",
        series_id=1,
        issue_number="2",
        title="Future Spec 2",
        release_status="SCHEDULED",
        foc_date=today + timedelta(days=75),
        release_date=today + timedelta(days=96),
    )
    assert issue_in_forward_recommendation_window(far_foc, today=today)

    too_far = ReleaseIssue(
        owner_user_id=1,
        release_uuid="fwd-too-far",
        series_id=1,
        issue_number="3",
        title="Future Spec 3",
        release_status="SCHEDULED",
        foc_date=today + timedelta(days=120),
        release_date=today + timedelta(days=140),
    )
    assert not issue_in_forward_recommendation_window(too_far, today=today)


def test_foc_priority_beats_profile_only() -> None:
    today = date.today()
    series = ReleaseSeries(
        owner_user_id=1,
        publisher="Marvel",
        series_name="Priority Test",
        series_type="ONGOING",
        status="ACTIVE",
    )
    issue = ReleaseIssue(
        owner_user_id=1,
        release_uuid="prio-foc",
        series_id=1,
        issue_number="5",
        title="Priority Test 5",
        release_status="SCHEDULED",
        foc_date=today + timedelta(days=2),
        release_date=today + timedelta(days=23),
    )
    foc_score, _, _ = compute_forward_catalog_priority(
        issue=issue,
        series=series,
        owned=False,
        key_signals=[],
        v2_total_score=55.0,
        spec_type=None,
        has_ratio_variant=False,
        today=today,
    )
    profile_only, _, _ = compute_forward_catalog_priority(
        issue=issue,
        series=series,
        owned=False,
        key_signals=[],
        v2_total_score=92.0,
        spec_type=None,
        has_ratio_variant=False,
        today=today,
    )
    assert foc_score >= 93.0
    assert profile_only >= foc_score


def test_forward_catalog_draft_without_pull_list(client: TestClient, session: Session) -> None:
    register_and_login(client, "fwd-no-pull@example.com")
    owner_id = int(session.exec(select(User).where(User.email == "fwd-no-pull@example.com")).one().id or 0)
    today = date.today()
    series = ReleaseSeries(
        owner_user_id=owner_id,
        publisher="Marvel",
        series_name="Cosmic Forward",
        series_type="ONGOING",
        status="ACTIVE",
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    session.add(
        ReleaseIssue(
            owner_user_id=owner_id,
            release_uuid="fwd-no-pull",
            series_id=int(series.id or 0),
            issue_number="1",
            title="Cosmic Forward 1",
            release_status="SCHEDULED",
            foc_date=today + timedelta(days=45),
            release_date=today + timedelta(days=66),
        )
    )
    session.commit()

    created = generate_unified_collector_recommendations(session, owner_user_id=owner_id)
    assert created >= 1
    items, total = list_latest_unified_collector_recommendations(session, owner_user_id=owner_id)
    assert total >= 1
    assert any("Cosmic Forward" in i.title for i in items)
    assert any("P50_RELEASE" in i.source_systems for i in items)
