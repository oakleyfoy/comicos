from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.models.industry_opportunity import IndustryOpportunityScore
from app.models.industry_release_scan import IndustryReleaseCandidate
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries, ReleaseVariant
from app.schemas.release_intelligence import ReleaseImportFeedRequest
from app.services.industry_opportunities import (
    build_industry_opportunity_summary,
    list_industry_opportunities,
    refresh_latest_industry_opportunities,
)
from app.services.industry_opportunity_engine import compute_industry_opportunity_score
from app.services.industry_release_scanner import scan_industry_releases
from app.services.industry_release_signals import classify_latest_industry_release_signals
from app.services.lunar_variant_classifier import classify_lunar_variant
from app.services.lunar_variant_identity import build_issue_release_uuid, build_variant_uuid
from app.services.release_import import import_release_feed
from test_inventory import auth_headers, register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def _import_lunar_issue(
    session: Session,
    *,
    owner_user_id: int,
    publisher: str,
    series_name: str,
    issue_number: str,
    foc_date: date,
    release_date: date,
    title: str | None = None,
    variant_name: str = "Cover A",
    ratio_value: int | None = None,
) -> int:
    classification = classify_lunar_variant(title=series_name, variant_desc=variant_name)
    variant_payload: dict = {
        "variant_uuid": build_variant_uuid(source_item_code=f"{series_name[:3]}-{issue_number}-0", classification=classification),
        "variant_name": variant_name,
        "variant_type": "standard",
        "source_item_code": f"{series_name[:3]}-{issue_number}-0",
    }
    if ratio_value is not None:
        variant_payload["ratio_value"] = ratio_value
    payload = ReleaseImportFeedRequest.model_validate(
        {
            "series": [
                {
                    "publisher": publisher,
                    "series_name": series_name,
                    "series_type": "ONGOING",
                    "status": "ACTIVE",
                    "issues": [
                        {
                            "release_uuid": build_issue_release_uuid(
                                publisher=publisher,
                                series_name=series_name,
                                issue_number=issue_number,
                            ),
                            "issue_number": issue_number,
                            "title": title or f"{series_name} #{issue_number}",
                            "foc_date": str(foc_date),
                            "release_date": str(release_date),
                            "release_status": "SCHEDULED",
                            "variants": [variant_payload],
                        }
                    ],
                }
            ]
        }
    )
    import_release_feed(session, owner_user_id=owner_user_id, payload=payload)
    release_uuid = build_issue_release_uuid(
        publisher=publisher,
        series_name=series_name,
        issue_number=issue_number,
    )
    issue = session.exec(
        select(ReleaseIssue)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .where(ReleaseIssue.release_uuid == release_uuid)
    ).one()
    return int(issue.id or 0)


def _seed_scan_and_signals(session: Session, *, owner_user_id: int) -> IndustryReleaseCandidate:
    scan_industry_releases(session, owner_user_id=owner_user_id)
    classify_latest_industry_release_signals(session, owner_user_id=owner_user_id)
    candidate = session.exec(
        select(IndustryReleaseCandidate)
        .where(IndustryReleaseCandidate.owner_user_id == owner_user_id)
        .order_by(IndustryReleaseCandidate.id.desc())
    ).first()
    assert candidate is not None
    return candidate


def test_opportunity_engine_high_score_for_first_appearance_number_one(client: TestClient, session: Session) -> None:
    email = "io-high@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    today = date.today()
    release_id = _import_lunar_issue(
        session,
        owner_user_id=owner_id,
        publisher="Marvel",
        series_name="Spider Hero",
        issue_number="1",
        foc_date=today + timedelta(days=5),
        release_date=today + timedelta(days=19),
        title="Spider Hero #1 FIRST APPEARANCE",
        variant_name="1:25 Incentive",
        ratio_value=25,
    )
    candidate = _seed_scan_and_signals(session, owner_user_id=owner_id)
    issue = session.get(ReleaseIssue, release_id)
    assert issue is not None
    series = session.get(ReleaseSeries, issue.series_id)
    assert series is not None
    variants = session.exec(select(ReleaseVariant).where(ReleaseVariant.issue_id == release_id)).all()
    from app.models.industry_release_signal import IndustryReleaseSignal

    signals = session.exec(
        select(IndustryReleaseSignal).where(IndustryReleaseSignal.candidate_id == candidate.id)
    ).all()
    result = compute_industry_opportunity_score(
        session,
        owner_user_id=owner_id,
        candidate=candidate,
        issue=issue,
        series=series,
        variants=variants,
        signals=signals,
    )
    assert result.opportunity_score >= 55.0
    assert 0.0 <= result.confidence_score <= 1.0
    assert result.risk_level in {"LOW", "MEDIUM", "HIGH"}


def test_opportunity_facsimile_risk_flag(client: TestClient, session: Session) -> None:
    email = "io-fac@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    today = date.today()
    _import_lunar_issue(
        session,
        owner_user_id=owner_id,
        publisher="DC",
        series_name="Classic Tales",
        issue_number="1",
        foc_date=today + timedelta(days=4),
        release_date=today + timedelta(days=18),
        title="Classic Tales #1 FACSIMILE EDITION",
    )
    _seed_scan_and_signals(session, owner_user_id=owner_id)
    latest = refresh_latest_industry_opportunities(session, owner_user_id=owner_id)
    assert latest.scores_computed >= 1
    assert any(row.risk_level == "HIGH" for row in latest.items)


def test_refresh_and_summary(client: TestClient, session: Session) -> None:
    email = "io-sum@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    today = date.today()
    _import_lunar_issue(
        session,
        owner_user_id=owner_id,
        publisher="Image",
        series_name="Battle Beast",
        issue_number="100",
        foc_date=today + timedelta(days=6),
        release_date=today + timedelta(days=20),
        title="Battle Beast #100 ANNIVERSARY",
    )
    refresh_latest_industry_opportunities(session, owner_user_id=owner_id)
    summary = build_industry_opportunity_summary(session, owner_user_id=owner_id)
    assert summary.total_opportunities >= 1
    assert summary.scan_run_id is not None

    items, total = list_industry_opportunities(session, owner_user_id=owner_id)
    assert total >= 1
    assert items[0].opportunity_score >= items[-1].opportunity_score


def test_industry_opportunities_api(client: TestClient, session: Session) -> None:
    email = "io-api@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    today = date.today()
    _import_lunar_issue(
        session,
        owner_user_id=owner_id,
        publisher="Boom",
        series_name="Power Squad",
        issue_number="1",
        foc_date=today + timedelta(days=3),
        release_date=today + timedelta(days=17),
    )
    latest = client.post("/api/v1/industry-opportunities/refresh", headers=auth_headers(token))
    assert latest.status_code == 200
    body = latest.json()["data"]
    assert body["scores_computed"] >= 1
    assert len(body["items"]) >= 1

    read_back = client.get("/api/v1/industry-opportunities/latest", headers=auth_headers(token))
    assert read_back.status_code == 200
    assert read_back.json()["data"]["scores_computed"] == 0
    assert len(read_back.json()["data"]["items"]) >= 1

    listed = client.get("/api/v1/industry-opportunities", headers=auth_headers(token))
    assert listed.status_code == 200
    assert listed.json()["data"]["pagination"]["total_count"] >= 1

    summary = client.get("/api/v1/industry-opportunities/summary", headers=auth_headers(token))
    assert summary.status_code == 200
    assert summary.json()["data"]["total_opportunities"] >= 1

    rows = session.exec(select(IndustryOpportunityScore).where(IndustryOpportunityScore.owner_user_id == owner_id)).all()
    assert len(rows) >= 1
