from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.models.release_intelligence import ReleaseIssue, ReleaseKeySignal, ReleaseSeries
from app.services.cross_system_recommendation_engine import (
    build_cross_system_candidates,
    generate_cross_system_recommendations,
)
from app.services.executive_dashboard import get_executive_dashboard, get_executive_dashboard_ranking_audit
from app.services.recommendation_ranking_diagnostics import build_recommendation_ranking_audit
from test_inventory import register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def _add_forward_issue(
    session: Session,
    *,
    owner_id: int,
    series_name: str,
    issue_number: str,
    foc_days: int = 14,
    cover_price: float = 4.99,
) -> ReleaseIssue:
    series = ReleaseSeries(
        owner_user_id=owner_id,
        publisher="Marvel",
        series_name=series_name,
        series_type="ONGOING",
        status="ACTIVE",
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    foc = date.today() + timedelta(days=foc_days)
    issue = ReleaseIssue(
        owner_user_id=owner_id,
        release_uuid=f"rank-{series_name}-{issue_number}",
        series_id=int(series.id or 0),
        issue_number=issue_number,
        title=f"{series_name} {issue_number}",
        release_status="SCHEDULED",
        foc_date=foc,
        release_date=foc + timedelta(days=21),
        cover_price=cover_price,
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)
    return issue


def test_top_recommendations_sorted_by_score_not_title(client: TestClient, session: Session) -> None:
    register_and_login(client, "rank-order@example.com")
    owner_id = _owner_id(session, "rank-order@example.com")
    angel = _add_forward_issue(session, owner_id=owner_id, series_name="Angel", issue_number="5")
    zod = _add_forward_issue(session, owner_id=owner_id, series_name="Zod", issue_number="1")
    session.add(
        ReleaseKeySignal(
            owner_user_id=owner_id,
            issue_id=int(zod.id or 0),
            signal_type="NEW_NUMBER_ONE",
            confidence_score=0.9,
            signal_payload_json={},
        )
    )
    session.commit()

    generate_cross_system_recommendations(session, owner_user_id=owner_id)
    dash = get_executive_dashboard(session, owner_user_id=owner_id)
    assert dash.top_recommendations.items
    titles = [i.title for i in dash.top_recommendations.items]
    assert titles[0].startswith("Zod")
    assert dash.top_recommendations.ranking_diagnostics is not None
    assert dash.top_recommendations.ranking_diagnostics.sort_order_valid is True
    assert dash.top_recommendations.ranking_diagnostics.appears_alphabetical_by_title is False


def test_ranking_audit_lists_scores_and_spread(client: TestClient, session: Session) -> None:
    register_and_login(client, "rank-audit@example.com")
    owner_id = _owner_id(session, "rank-audit@example.com")
    _add_forward_issue(session, owner_id=owner_id, series_name="Alpha", issue_number="2")
    _add_forward_issue(session, owner_id=owner_id, series_name="Beta", issue_number="3")
    audit = get_executive_dashboard_ranking_audit(session, owner_user_id=owner_id, limit=100)
    assert audit.listed_count >= 2
    assert audit.min_score is not None
    assert audit.max_score is not None
    assert audit.distinct_score_count >= 1
    assert audit.items[0].priority_score >= audit.items[-1].priority_score
    assert all(row.rank >= 1 for row in audit.items)


def test_cross_system_candidates_have_score_separation(client: TestClient, session: Session) -> None:
    register_and_login(client, "rank-spread@example.com")
    owner_id = _owner_id(session, "rank-spread@example.com")
    low = _add_forward_issue(session, owner_id=owner_id, series_name="Low", issue_number="9", foc_days=60)
    high = _add_forward_issue(session, owner_id=owner_id, series_name="High", issue_number="1", foc_days=3)
    session.add(
        ReleaseKeySignal(
            owner_user_id=owner_id,
            issue_id=int(high.id or 0),
            signal_type="FIRST_APPEARANCE",
            confidence_score=0.88,
            signal_payload_json={},
        )
    )
    session.commit()
    candidates = build_cross_system_candidates(session, owner_user_id=owner_id)
    forward = [c for c in candidates if c.title.startswith("High") or c.title.startswith("Low")]
    assert len(forward) >= 2
    high_c = next(c for c in forward if c.title.startswith("High"))
    low_c = next(c for c in forward if c.title.startswith("Low"))
    assert high_c.priority_score > low_c.priority_score

    audit = build_recommendation_ranking_audit(session, owner_user_id=owner_id, limit=100, refresh=True)
    assert audit.top_20_score_spread is not None
    assert audit.top_20_score_spread > 0.0
