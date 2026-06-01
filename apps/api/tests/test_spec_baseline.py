from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models.spec_baseline_score import SpecBaselineScore
from app.services.industry_scanner_automation import run_industry_scanner_refresh
from app.services.spec_baseline_engine import generate_spec_baseline_scores
from app.services.spec_input_builder import build_spec_inputs
from test_industry_scanner_automation import _import_lunar_issue, _owner_id
from test_inventory import auth_headers, register_and_login


def test_generate_spec_baseline_scores_persists_and_idempotent(client: TestClient, session: Session) -> None:
    email = "spec-baseline-persist@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _import_lunar_issue(session, owner_user_id=owner_id)
    run_industry_scanner_refresh(session, owner_user_id=owner_id, trigger_type="MANUAL")
    build_spec_inputs(session, owner_user_id=owner_id)

    first = generate_spec_baseline_scores(session, owner_user_id=owner_id)
    assert first.computed + first.skipped + first.updated >= 1
    row = session.exec(select(SpecBaselineScore).where(SpecBaselineScore.owner_user_id == owner_id)).one()
    assert 0.0 <= row.baseline_score <= 100.0
    assert 0.0 <= row.confidence_score <= 1.0
    assert 0.0 <= row.risk_score <= 100.0
    assert row.rationale

    second = generate_spec_baseline_scores(session, owner_user_id=owner_id)
    assert second.skipped >= 1
    assert second.computed == 0


def test_spec_baseline_api_and_summary(client: TestClient, session: Session) -> None:
    email = "spec-baseline-api@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _import_lunar_issue(session, owner_user_id=owner_id)
    run_industry_scanner_refresh(session, owner_user_id=owner_id, trigger_type="MANUAL")

    latest = client.post("/api/v1/spec-baseline-scores/refresh", headers=auth_headers(token))
    assert latest.status_code == 200
    payload = latest.json()["data"]
    assert payload["scores_computed"] + payload["scores_skipped"] + payload["scores_updated"] >= 1
    assert len(payload["items"]) >= 1
    assert 0.0 <= payload["items"][0]["baseline_score"] <= 100.0

    listing = client.get("/api/v1/spec-baseline-scores", headers=auth_headers(token))
    assert listing.status_code == 200
    assert listing.json()["data"]["pagination"]["total_count"] >= 1

    summary = client.get("/api/v1/spec-baseline-scores/summary", headers=auth_headers(token))
    assert summary.status_code == 200
    body = summary.json()["data"]
    assert body["total_scores"] >= 1
    assert body["average_baseline_score"] >= 0.0

    repeat = client.get("/api/v1/spec-baseline-scores/latest", headers=auth_headers(token))
    assert repeat.status_code == 200
    assert repeat.json()["data"]["scores_computed"] == 0
    assert repeat.json()["data"]["scores_skipped"] == 1
