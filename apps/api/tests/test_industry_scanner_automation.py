from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.models.industry_scanner_automation import IndustryScannerAutomationRun
from app.schemas.release_intelligence import ReleaseImportFeedRequest
from app.services.industry_scanner_automation import run_industry_scanner_refresh
from app.services.lunar_release_refresh import refresh_release_intelligence_after_lunar_import
from app.services.lunar_variant_classifier import classify_lunar_variant
from app.services.lunar_variant_identity import build_issue_release_uuid, build_variant_uuid
from app.services.release_import import import_release_feed
from app.services.recovery_recommendations import build_operations_dashboard
from test_inventory import auth_headers, register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def _import_lunar_issue(session: Session, *, owner_user_id: int) -> None:
    today = date.today()
    classification = classify_lunar_variant(title="Power Squad", variant_desc="Cover A")
    payload = ReleaseImportFeedRequest.model_validate(
        {
            "series": [
                {
                    "publisher": "Boom",
                    "series_name": "Power Squad",
                    "series_type": "ONGOING",
                    "status": "ACTIVE",
                    "issues": [
                        {
                            "release_uuid": build_issue_release_uuid(
                                publisher="Boom",
                                series_name="Power Squad",
                                issue_number="1",
                            ),
                            "issue_number": "1",
                            "title": "Power Squad #1",
                            "foc_date": str(today + timedelta(days=4)),
                            "release_date": str(today + timedelta(days=18)),
                            "release_status": "SCHEDULED",
                            "variants": [
                                {
                                    "variant_uuid": build_variant_uuid(
                                        source_item_code="PS-1-0",
                                        classification=classification,
                                    ),
                                    "variant_name": "Cover A",
                                    "variant_type": "standard",
                                    "source_item_code": "PS-1-0",
                                }
                            ],
                        }
                    ],
                }
            ]
        }
    )
    import_release_feed(session, owner_user_id=owner_user_id, payload=payload)


def test_run_industry_scanner_refresh_records_run(client: TestClient, session: Session) -> None:
    email = "isa-run@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _import_lunar_issue(session, owner_user_id=owner_id)

    run = run_industry_scanner_refresh(session, owner_user_id=owner_id, trigger_type="MANUAL")
    assert run.status in {"SUCCESS", "NO_CHANGE"}
    assert run.releases_scanned >= 1


def test_idempotent_refresh_skips_duplicate_scan(client: TestClient, session: Session) -> None:
    email = "isa-idem@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _import_lunar_issue(session, owner_user_id=owner_id)

    first = run_industry_scanner_refresh(session, owner_user_id=owner_id, trigger_type="MANUAL")
    second = run_industry_scanner_refresh(session, owner_user_id=owner_id, trigger_type="MANUAL")
    assert second.scan_skipped is True
    assert second.status == "NO_CHANGE"
    assert second.signals_upserted == 0
    assert second.scores_updated == 0
    assert first.scan_run_id == second.scan_run_id


def test_lunar_release_refresh_triggers_industry_scanner(client: TestClient, session: Session) -> None:
    email = "isa-lunar@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _import_lunar_issue(session, owner_user_id=owner_id)

    refresh_release_intelligence_after_lunar_import(session, owner_user_id=owner_id)
    row = session.exec(
        select(IndustryScannerAutomationRun)
        .where(IndustryScannerAutomationRun.owner_user_id == owner_id)
        .order_by(IndustryScannerAutomationRun.id.desc())
    ).first()
    assert row is not None
    assert row.trigger_type == "LUNAR_REFRESH"


def test_industry_scanner_automation_api_and_ops_panel(client: TestClient, session: Session) -> None:
    email = "isa-api@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _import_lunar_issue(session, owner_user_id=owner_id)
    run_industry_scanner_refresh(session, owner_user_id=owner_id, trigger_type="MANUAL")

    latest = client.get("/api/v1/industry-scanner/latest", headers=auth_headers(token))
    assert latest.status_code == 200

    runs = client.get("/api/v1/industry-scanner/runs", headers=auth_headers(token))
    assert runs.status_code == 200
    assert runs.json()["data"]["pagination"]["total_count"] >= 1

    ops = build_operations_dashboard(session, owner_user_id=owner_id)
    assert ops.industry_scanner_automation is not None
    assert ops.industry_scanner_automation.status in {"SUCCESS", "NO_CHANGE"}
