from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.models.industry_release_scan import IndustryReleaseCandidate, IndustryReleaseScanRun
from app.schemas.industry_publisher import IndustryPublisherUpdate
from app.schemas.release_intelligence import ReleaseImportFeedRequest
from app.services.industry_publisher_scan_config import list_industry_publishers, update_industry_publisher
from app.services.industry_release_scanner import load_lunar_catalog_releases, scan_industry_releases
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
    variant_count: int = 1,
) -> int:
    classification = classify_lunar_variant(title=series_name, variant_desc="Cover A")
    variants = []
    for idx in range(variant_count):
        variants.append(
            {
                "variant_uuid": build_variant_uuid(
                    source_item_code=f"{series_name[:3]}-{issue_number}-{idx}",
                    classification=classification,
                ),
                "variant_name": f"Cover {chr(65 + idx)}",
                "variant_type": "standard",
                "source_item_code": f"{series_name[:3]}-{issue_number}-{idx}",
            }
        )
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
                            "title": f"{series_name} #{issue_number}",
                            "foc_date": str(foc_date),
                            "release_date": str(release_date),
                            "release_status": "SCHEDULED",
                            "variants": variants,
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
    from app.models.release_intelligence import ReleaseIssue

    issue = session.exec(
        select(ReleaseIssue)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .where(ReleaseIssue.release_uuid == release_uuid)
    ).one()
    return int(issue.id or 0)


def test_load_lunar_catalog_and_publisher_filter(client: TestClient, session: Session) -> None:
    email = "irs-catalog@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    today = date.today()
    _import_lunar_issue(
        session,
        owner_user_id=owner_id,
        publisher="Image",
        series_name="Battle Beast",
        issue_number="1",
        foc_date=today + timedelta(days=7),
        release_date=today + timedelta(days=21),
    )
    _import_lunar_issue(
        session,
        owner_user_id=owner_id,
        publisher="Acme Comics",
        series_name="Unknown Title",
        issue_number="1",
        foc_date=today + timedelta(days=7),
        release_date=today + timedelta(days=21),
    )

    catalog = load_lunar_catalog_releases(session, owner_user_id=owner_id)
    assert len(catalog) == 2

    run = scan_industry_releases(session, owner_user_id=owner_id)
    assert run.status == "SUCCESS"
    assert run.releases_scanned == 2
    assert run.candidates_created == 1
    assert run.candidates_total == 1
    assert run.publishers_included == 10


def test_scan_excludes_unsupported_publisher_when_marvel_excluded(client: TestClient, session: Session) -> None:
    email = "irs-marvel@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    pubs = list_industry_publishers(session, owner_user_id=owner_id)
    marvel = next(p for p in pubs if p.publisher_code == "MARVEL")
    update_industry_publisher(
        session,
        owner_user_id=owner_id,
        publisher_id=marvel.id,
        update=IndustryPublisherUpdate(inclusion_status="EXCLUDED"),
    )
    today = date.today()
    _import_lunar_issue(
        session,
        owner_user_id=owner_id,
        publisher="Marvel",
        series_name="Spider-Hero",
        issue_number="1",
        foc_date=today + timedelta(days=3),
        release_date=today + timedelta(days=17),
    )

    run = scan_industry_releases(session, owner_user_id=owner_id)
    assert run.candidates_created == 0


def test_scan_idempotent_within_run(client: TestClient, session: Session) -> None:
    email = "irs-idem@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    today = date.today()
    _import_lunar_issue(
        session,
        owner_user_id=owner_id,
        publisher="DC",
        series_name="Caped Knight",
        issue_number="12",
        foc_date=today + timedelta(days=10),
        release_date=today + timedelta(days=24),
        variant_count=2,
    )

    first = scan_industry_releases(session, owner_user_id=owner_id)
    second = scan_industry_releases(session, owner_user_id=owner_id)
    assert first.candidates_created == 1
    assert second.candidates_created == 1

    runs = session.exec(select(IndustryReleaseScanRun).where(IndustryReleaseScanRun.owner_user_id == owner_id)).all()
    assert len(runs) == 2
    candidates = session.exec(
        select(IndustryReleaseCandidate).where(IndustryReleaseCandidate.owner_user_id == owner_id)
    ).all()
    assert len(candidates) == 2


def test_industry_release_scanner_api(client: TestClient, session: Session) -> None:
    email = "irs-api@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    today = date.today()
    _import_lunar_issue(
        session,
        owner_user_id=owner_id,
        publisher="Boom",
        series_name="Power Squad",
        issue_number="5",
        foc_date=today + timedelta(days=4),
        release_date=today + timedelta(days=18),
    )

    run_resp = client.post("/api/v1/industry-release-scans/run", headers=auth_headers(token))
    assert run_resp.status_code == 201
    run_data = run_resp.json()["data"]
    assert run_data["status"] == "SUCCESS"
    assert run_data["candidates_created"] == 1

    scans = client.get("/api/v1/industry-release-scans", headers=auth_headers(token))
    assert scans.status_code == 200
    assert scans.json()["data"]["pagination"]["total_count"] >= 1

    candidates = client.get("/api/v1/industry-release-candidates", headers=auth_headers(token))
    assert candidates.status_code == 200
    items = candidates.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["publisher_code"] == "BOOM"
    assert items[0]["series_name"] == "Power Squad"
    assert items[0]["monitoring_status"] == "MONITOR"
