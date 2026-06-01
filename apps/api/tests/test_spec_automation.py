from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.models.spec_automation import SpecAutomationRun
from app.models.top_spec_pick import TopSpecPick
from app.services.industry_scanner_automation import run_industry_scanner_refresh
from app.services.recovery_recommendations import build_operations_dashboard
from app.services.spec_automation import run_spec_refresh
from test_industry_scanner_automation import _import_lunar_issue, _owner_id
from test_inventory import auth_headers, register_and_login


def test_run_spec_refresh_persists_pipeline(client: TestClient, session: Session) -> None:
    email = "spec-auto-persist@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _import_lunar_issue(session, owner_user_id=owner_id)
    run_industry_scanner_refresh(session, owner_user_id=owner_id, trigger_type="MANUAL")

    runs_before = len(
        session.exec(select(SpecAutomationRun).where(SpecAutomationRun.owner_user_id == owner_id)).all()
    )
    run = run_spec_refresh(session, owner_user_id=owner_id)
    assert run.status in {"SUCCESS", "NO_CHANGE"}
    assert run.runtime_ms >= 0
    runs_after = session.exec(select(SpecAutomationRun).where(SpecAutomationRun.owner_user_id == owner_id)).all()
    assert len(runs_after) == runs_before + 1
    picks = session.exec(select(TopSpecPick).where(TopSpecPick.owner_user_id == owner_id)).all()
    assert len(picks) >= 1


def test_industry_scanner_triggers_spec_automation(client: TestClient, session: Session) -> None:
    email = "spec-auto-hook@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _import_lunar_issue(session, owner_user_id=owner_id)

    run_industry_scanner_refresh(session, owner_user_id=owner_id, trigger_type="MANUAL")
    row = session.exec(
        select(SpecAutomationRun)
        .where(SpecAutomationRun.owner_user_id == owner_id)
        .order_by(SpecAutomationRun.id.desc())
    ).first()
    assert row is not None
    assert row.status in {"SUCCESS", "NO_CHANGE"}


def test_spec_automation_api_and_ops_panel(client: TestClient, session: Session) -> None:
    email = "spec-auto-api@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _import_lunar_issue(session, owner_user_id=owner_id)
    run_spec_refresh(session, owner_user_id=owner_id)

    latest = client.get("/api/v1/spec-automation/latest", headers=auth_headers(token))
    assert latest.status_code == 200

    runs = client.get("/api/v1/spec-automation/runs", headers=auth_headers(token))
    assert runs.status_code == 200
    assert runs.json()["data"]["pagination"]["total_count"] >= 1

    ok = client.post("/api/v1/spec-automation/run", headers=auth_headers(token))
    assert ok.status_code == 200

    ops = build_operations_dashboard(session, owner_user_id=owner_id)
    assert ops.spec_automation is not None
    assert ops.spec_automation.status in {"SUCCESS", "NO_CHANGE", "NEVER_RUN"}
