from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.services.industry_scanner_automation import run_industry_scanner_refresh
from app.services.top_spec_pick_engine import generate_top_spec_picks
from app.services.weekly_spec_dashboard import build_weekly_spec_dashboard, build_weekly_spec_dashboard_summary
from test_industry_scanner_automation import _import_lunar_issue, _owner_id
from test_inventory import auth_headers, register_and_login


def test_weekly_spec_dashboard_builds_sections(client: TestClient, session: Session) -> None:
    email = "weekly-spec-dash@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _import_lunar_issue(session, owner_user_id=owner_id)
    run_industry_scanner_refresh(session, owner_user_id=owner_id, trigger_type="MANUAL")
    generate_top_spec_picks(session, owner_user_id=owner_id, limit=20)

    dash = build_weekly_spec_dashboard(session, owner_user_id=owner_id)
    assert dash.summary.top_picks_count >= 1
    assert len(dash.top_20_preorder) >= 1
    assert dash.top_20_preorder[0].rank == 1
    assert dash.publisher_breakdown


def test_weekly_spec_dashboard_api(client: TestClient, session: Session) -> None:
    email = "weekly-spec-api@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _import_lunar_issue(session, owner_user_id=owner_id)
    run_industry_scanner_refresh(session, owner_user_id=owner_id, trigger_type="MANUAL")
    generate_top_spec_picks(session, owner_user_id=owner_id, limit=20)

    full = client.get("/api/v1/weekly-spec-dashboard", headers=auth_headers(token))
    assert full.status_code == 200
    body = full.json()["data"]
    assert body["summary"]["top_picks_count"] >= 1
    assert len(body["top_20_preorder"]) >= 1

    summary = client.get("/api/v1/weekly-spec-dashboard/summary", headers=auth_headers(token))
    assert summary.status_code == 200
    sum_body = summary.json()["data"]
    assert sum_body["top_picks_count"] >= 1
    assert sum_body["average_confidence"] >= 0.0

    service_summary = build_weekly_spec_dashboard_summary(session, owner_user_id=owner_id)
    assert service_summary.top_picks_count == sum_body["top_picks_count"]
