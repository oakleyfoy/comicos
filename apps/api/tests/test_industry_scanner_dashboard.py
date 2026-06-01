from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.schemas.release_intelligence import ReleaseImportFeedRequest
from app.services.industry_scanner_dashboard import (
    build_industry_scanner_dashboard,
    build_industry_scanner_dashboard_summary,
)
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
    title: str,
    ratio_value: int | None = None,
) -> None:
    classification = classify_lunar_variant(title=series_name, variant_desc="Cover A")
    variant_payload: dict = {
        "variant_uuid": build_variant_uuid(source_item_code=f"{series_name[:3]}-{issue_number}-0", classification=classification),
        "variant_name": "1:25 Incentive" if ratio_value else "Cover A",
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
                            "title": title,
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


def test_industry_scanner_dashboard_sections(client: TestClient, session: Session) -> None:
    email = "isd-sections@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    today = date.today()
    _import_lunar_issue(
        session,
        owner_user_id=owner_id,
        publisher="Marvel",
        series_name="Spider Hero",
        issue_number="1",
        foc_date=today + timedelta(days=4),
        release_date=today + timedelta(days=18),
        title="Spider Hero #1 FIRST APPEARANCE",
        ratio_value=25,
    )
    _import_lunar_issue(
        session,
        owner_user_id=owner_id,
        publisher="DC",
        series_name="Classic Tales",
        issue_number="1",
        foc_date=today + timedelta(days=5),
        release_date=today + timedelta(days=19),
        title="Classic Tales #1 FACSIMILE EDITION",
    )

    dash = build_industry_scanner_dashboard(session, owner_user_id=owner_id, refresh=True)
    assert dash.scan_run_id is not None
    assert dash.summary.releases_scanned >= 2
    assert dash.summary.signals_detected >= 2
    assert len(dash.top_number_one_issues) >= 1
    assert len(dash.ratio_variants) >= 1
    assert len(dash.facsimiles) >= 1


def test_industry_scanner_dashboard_summary_counts(client: TestClient, session: Session) -> None:
    email = "isd-summary@example.com"
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

    summary = build_industry_scanner_dashboard_summary(session, owner_user_id=owner_id, refresh=True)
    assert summary.releases_scanned >= 1
    assert summary.signals_detected >= 1
    assert summary.number_one_issues >= 0


def test_industry_scanner_dashboard_api(client: TestClient, session: Session) -> None:
    email = "isd-api@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    today = date.today()
    _import_lunar_issue(
        session,
        owner_user_id=owner_id,
        publisher="Boom",
        series_name="Event Squad",
        issue_number="1",
        foc_date=today + timedelta(days=3),
        release_date=today + timedelta(days=17),
        title="Event Squad #1 KEY EVENT CROSSOVER",
    )

    full = client.get("/api/v1/industry-scanner-dashboard", headers=auth_headers(token))
    assert full.status_code == 200
    data = full.json()["data"]
    assert "summary" in data
    assert "top_number_one_issues" in data
    assert "watchlist" in data
    assert data["summary"]["releases_scanned"] >= 1

    summary = client.get("/api/v1/industry-scanner-dashboard/summary", headers=auth_headers(token))
    assert summary.status_code == 200
    assert summary.json()["data"]["signals_detected"] >= 1
