from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.models.industry_release_scan import IndustryReleaseCandidate
from app.models.industry_release_signal import IndustryReleaseSignal
from app.models.release_intelligence import ReleaseIssue, ReleaseKeySignal
from app.schemas.release_intelligence import ReleaseImportFeedRequest
from app.services.industry_release_scanner import scan_industry_releases
from app.services.industry_release_signal_classifier import classify_industry_release_candidate
from app.services.industry_release_signals import classify_latest_industry_release_signals, list_industry_release_signals
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
    series_type: str = "ONGOING",
    variant_name: str = "Cover A",
    variant_type: str = "standard",
    ratio_value: int | None = None,
) -> int:
    classification = classify_lunar_variant(title=series_name, variant_desc=variant_name)
    variant_payload: dict = {
        "variant_uuid": build_variant_uuid(source_item_code=f"{series_name[:3]}-{issue_number}-0", classification=classification),
        "variant_name": variant_name,
        "variant_type": variant_type,
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
                    "series_type": series_type,
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


def _latest_candidate(session: Session, *, owner_user_id: int) -> IndustryReleaseCandidate:
    row = session.exec(
        select(IndustryReleaseCandidate)
        .where(IndustryReleaseCandidate.owner_user_id == owner_user_id)
        .order_by(IndustryReleaseCandidate.id.desc())
    ).first()
    assert row is not None
    return row


def test_classify_number_one_and_ratio(client: TestClient, session: Session) -> None:
    email = "irs-sig-num@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    today = date.today()
    _import_lunar_issue(
        session,
        owner_user_id=owner_id,
        publisher="Image",
        series_name="Launch Comic",
        issue_number="1",
        foc_date=today + timedelta(days=5),
        release_date=today + timedelta(days=19),
        variant_name="Incentive 1:25 Variant",
        ratio_value=25,
    )
    scan_industry_releases(session, owner_user_id=owner_id)
    candidate = _latest_candidate(session, owner_user_id=owner_id)
    from app.models.release_intelligence import ReleaseSeries, ReleaseVariant

    issue = session.get(ReleaseIssue, candidate.release_id)
    assert issue is not None
    series = session.get(ReleaseSeries, issue.series_id)
    assert series is not None
    variants = session.exec(select(ReleaseVariant).where(ReleaseVariant.issue_id == issue.id)).all()
    signals = {d.signal_type for d in classify_industry_release_candidate(session, candidate=candidate, issue=issue, series=series, variants=variants)}
    assert "NUMBER_ONE" in signals
    assert "RATIO_VARIANT" in signals


def test_classify_first_appearance_and_facsimile(client: TestClient, session: Session) -> None:
    email = "irs-sig-fa@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    today = date.today()
    release_id = _import_lunar_issue(
        session,
        owner_user_id=owner_id,
        publisher="Marvel",
        series_name="Hero Team",
        issue_number="5",
        foc_date=today + timedelta(days=4),
        release_date=today + timedelta(days=18),
        title="Hero Team #5 FIRST APPEARANCE of Sidekick",
    )
    session.add(
        ReleaseKeySignal(
            owner_user_id=owner_id,
            issue_id=release_id,
            signal_type="FIRST_APPEARANCE",
            confidence_score=0.88,
            signal_payload_json={"source": "test"},
        )
    )
    session.commit()

    _import_lunar_issue(
        session,
        owner_user_id=owner_id,
        publisher="DC",
        series_name="Classic Tales",
        issue_number="1",
        foc_date=today + timedelta(days=6),
        release_date=today + timedelta(days=20),
        title="Classic Tales #1 FACSIMILE EDITION",
    )
    scan_industry_releases(session, owner_user_id=owner_id)

    latest = classify_latest_industry_release_signals(session, owner_user_id=owner_id)
    types = {item.signal_type for item in latest.items}
    assert "FIRST_APPEARANCE" in types
    assert "FACSIMILE" in types


def test_classify_unknown_when_no_rules(client: TestClient, session: Session) -> None:
    email = "irs-sig-unknown@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    today = date.today()
    _import_lunar_issue(
        session,
        owner_user_id=owner_id,
        publisher="Boom",
        series_name="Regular Series",
        issue_number="14",
        foc_date=today + timedelta(days=8),
        release_date=today + timedelta(days=22),
        title="Regular Series #14",
    )
    scan_industry_releases(session, owner_user_id=owner_id)
    latest = classify_latest_industry_release_signals(session, owner_user_id=owner_id)
    assert any(item.signal_type == "UNKNOWN" for item in latest.items)


def test_industry_release_signals_api(client: TestClient, session: Session) -> None:
    email = "irs-sig-api@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    today = date.today()
    _import_lunar_issue(
        session,
        owner_user_id=owner_id,
        publisher="Oni",
        series_name="Crossover Event",
        issue_number="100",
        foc_date=today + timedelta(days=3),
        release_date=today + timedelta(days=17),
        title="Crossover Event #100 ANNIVERSARY CROSSOVER",
    )
    scan_industry_releases(session, owner_user_id=owner_id)

    latest = client.post("/api/v1/industry-release-signals/refresh", headers=auth_headers(token))
    assert latest.status_code == 200
    body = latest.json()["data"]
    assert body["scan_run_id"] is not None
    assert body["signals_classified"] >= 1
    signal_types = {item["signal_type"] for item in body["items"]}
    assert "MILESTONE" in signal_types or "ANNIVERSARY" in signal_types or "CROSSOVER" in signal_types

    listed = client.get("/api/v1/industry-release-signals", headers=auth_headers(token))
    assert listed.status_code == 200
    assert listed.json()["data"]["pagination"]["total_count"] >= 1

    rows = session.exec(select(IndustryReleaseSignal).where(IndustryReleaseSignal.owner_user_id == owner_id)).all()
    assert len(rows) >= 1
    items, total = list_industry_release_signals(session, owner_user_id=owner_id)
    assert total == len(items)
