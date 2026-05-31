from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.models.recommendation_v2 import RecommendationRunV2, RecommendationScoreV2
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.services.recommendation_quality_calibration import (
    CALIBRATION_FAIL,
    CALIBRATION_PASS,
    calibrate_recommendation_quality,
)
from app.services.recommendation_v2_components import score_issue_components_v2
from app.services.user_preference_engine import create_manual_preference
from test_inventory import register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def _seed_run_with_scores(
    session: Session,
    *,
    owner_user_id: int,
    rows: list[tuple[int, float, str, str]],
) -> None:
    run = RecommendationRunV2(owner_user_id=owner_user_id, status="COMPLETED")
    session.add(run)
    session.commit()
    session.refresh(run)
    run_id = int(run.id or 0)
    for issue_id, total, tier, rec_type in rows:
        session.add(
            RecommendationScoreV2(
                recommendation_run_id=run_id,
                owner_user_id=owner_user_id,
                release_issue_id=issue_id,
                total_score=total,
                recommendation_tier=tier,
                recommendation_type=rec_type,
                confidence_score=0.7,
            )
        )
    session.commit()


def test_calibration_fails_when_top20_all_number_ones(client: TestClient, session: Session) -> None:
    email = "cal-fail-all-ones@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    series = ReleaseSeries(
        owner_user_id=owner_id,
        publisher="MARVEL",
        series_name="Calibration Fail Series",
        series_type="ONGOING",
        status="ACTIVE",
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    issues: list[ReleaseIssue] = []
    for idx in range(22):
        issue = ReleaseIssue(
            owner_user_id=owner_id,
            release_uuid=f"cal-fail-{idx}",
            series_id=int(series.id or 0),
            issue_number="1",
            title=f"Random One {idx}",
            release_status="SCHEDULED",
        )
        session.add(issue)
        session.commit()
        session.refresh(issue)
        issues.append(issue)
    rows = [
        (int(i.id or 0), 90.0 - idx * 0.1, "STRONG_BUY", "INVESTMENT_NUMBER_ONE") for idx, i in enumerate(issues)
    ]
    _seed_run_with_scores(session, owner_user_id=owner_id, rows=rows)
    result = calibrate_recommendation_quality(session, owner_user_id=owner_id)
    assert result.overall_status == CALIBRATION_FAIL
    assert any("dominate" in f or "exclusively" in f for f in result.findings)


def test_calibration_passes_with_diversified_top20(client: TestClient, session: Session) -> None:
    email = "cal-pass-diverse@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    series = ReleaseSeries(
        owner_user_id=owner_id,
        publisher="IDW",
        series_name="Calibration Pass Series",
        series_type="ONGOING",
        status="ACTIVE",
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    issue_rows: list[tuple[ReleaseIssue, str]] = []
    for idx in range(30):
        num = "1" if idx < 5 else str(10 + idx)
        rec_type = "INVESTMENT_NUMBER_ONE" if idx < 5 else "KEY_ISSUE"
        issue = ReleaseIssue(
            owner_user_id=owner_id,
            release_uuid=f"cal-pass-{idx}",
            series_id=int(series.id or 0),
            issue_number=num,
            title=f"Issue {num}",
            release_status="SCHEDULED",
        )
        session.add(issue)
        session.commit()
        session.refresh(issue)
        issue_rows.append((issue, rec_type))
    rows: list[tuple[int, float, str, str]] = []
    for idx, (issue, rec_type) in enumerate(issue_rows):
        total = 95.0 - idx if rec_type == "KEY_ISSUE" else 60.0 - idx
        tier = "STRONG_BUY" if total >= 72 else "BUY"
        rows.append((int(issue.id or 0), total, tier, rec_type))
    _seed_run_with_scores(session, owner_user_id=owner_id, rows=rows)
    result = calibrate_recommendation_quality(session, owner_user_id=owner_id)
    assert result.overall_status != CALIBRATION_FAIL
    assert result.details_json.get("top20_diversity_type_count", 0) >= 3
    assert result.details_json.get("top20_number_one_count", 20) < 18


def test_user_preferences_raise_scores_for_matching_series(client: TestClient, session: Session) -> None:
    email = "cal-user-pref-boost@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_manual_preference(
        session,
        owner_user_id=owner_id,
        preference_type="FRANCHISE",
        preference_label="Batman",
        preference_score=92.0,
    )
    series = ReleaseSeries(
        owner_user_id=owner_id,
        publisher="DC",
        series_name="Batman",
        series_type="ONGOING",
        status="ACTIVE",
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    issue = ReleaseIssue(
        owner_user_id=owner_id,
        release_uuid="cal-batman-25",
        series_id=int(series.id or 0),
        issue_number="25",
        title="Batman #25",
        release_status="SCHEDULED",
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)
    other_series = ReleaseSeries(
        owner_user_id=owner_id,
        publisher="INDIE",
        series_name="Obscure ZZZ",
        series_type="LIMITED",
        status="ACTIVE",
    )
    session.add(other_series)
    session.commit()
    session.refresh(other_series)
    other = ReleaseIssue(
        owner_user_id=owner_id,
        release_uuid="cal-obscure-25",
        series_id=int(other_series.id or 0),
        issue_number="25",
        title="Obscure ZZZ #25",
        release_status="SCHEDULED",
    )
    session.add(other)
    session.commit()
    session.refresh(other)
    batman = score_issue_components_v2(session, owner_user_id=owner_id, issue=issue, series=series)
    obscure = score_issue_components_v2(session, owner_user_id=owner_id, issue=other, series=other_series)
    batman_user = next(c for c in batman.components if c.component_name == "USER_PREFERENCE_SCORE")
    obscure_user = next(c for c in obscure.components if c.component_name == "USER_PREFERENCE_SCORE")
    assert batman_user.component_score > obscure_user.component_score
    assert batman.total_score > obscure.total_score
