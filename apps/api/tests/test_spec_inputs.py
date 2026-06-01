from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models.spec_input import SpecInput
from app.services.industry_scanner_automation import run_industry_scanner_refresh
from app.services.spec_input_builder import build_spec_inputs
from test_industry_scanner_automation import _import_lunar_issue, _owner_id
from test_inventory import auth_headers, register_and_login


def test_build_spec_inputs_persists_and_idempotent(client: TestClient, session: Session) -> None:
    email = "spec-input-persist@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _import_lunar_issue(session, owner_user_id=owner_id)
    run_industry_scanner_refresh(session, owner_user_id=owner_id, trigger_type="MANUAL")

    first = build_spec_inputs(session, owner_user_id=owner_id)
    assert first.created + first.skipped + first.updated >= 1
    rows = session.exec(select(SpecInput).where(SpecInput.owner_user_id == owner_id)).all()
    assert len(rows) >= 1
    row = rows[0]
    assert "PURCHASE_PROFILE" in row.source_systems
    summary = json.loads(row.signal_summary)
    assert summary["version"] == "P60-01"
    assert "purchase_context" in summary

    second = build_spec_inputs(session, owner_user_id=owner_id)
    assert second.skipped >= 1
    assert second.created == 0


def test_spec_inputs_api_and_summary(client: TestClient, session: Session) -> None:
    email = "spec-input-api@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _import_lunar_issue(session, owner_user_id=owner_id)
    run_industry_scanner_refresh(session, owner_user_id=owner_id, trigger_type="MANUAL")

    latest = client.get("/api/v1/spec-inputs/latest", headers=auth_headers(token))
    assert latest.status_code == 200
    payload = latest.json()["data"]
    assert payload["inputs_created"] + payload["inputs_skipped"] + payload["inputs_updated"] >= 1
    assert len(payload["items"]) >= 1

    listing = client.get("/api/v1/spec-inputs", headers=auth_headers(token))
    assert listing.status_code == 200
    assert listing.json()["data"]["pagination"]["total_count"] >= 1

    summary = client.get("/api/v1/spec-inputs/summary", headers=auth_headers(token))
    assert summary.status_code == 200
    body = summary.json()["data"]
    assert body["total_inputs"] >= 1
    assert body["source_system_counts"].get("PURCHASE_PROFILE", 0) >= 1
    assert body["source_system_counts"].get("INDUSTRY_SCANNER", 0) >= 1

    second = client.get("/api/v1/spec-inputs/latest", headers=auth_headers(token))
    assert second.status_code == 200
    assert second.json()["data"]["inputs_skipped"] >= 1
