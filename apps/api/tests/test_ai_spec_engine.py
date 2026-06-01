from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models.ai_spec_evaluation import AISpecEvaluation
from app.services.ai_spec_engine import generate_ai_spec_evaluations
from app.services.industry_scanner_automation import run_industry_scanner_refresh
from app.services.spec_input_builder import build_spec_inputs
from test_industry_scanner_automation import _import_lunar_issue, _owner_id
from test_inventory import auth_headers, register_and_login


def test_generate_ai_spec_evaluations_fallback_persists(client: TestClient, session: Session) -> None:
    email = "ai-spec-persist@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _import_lunar_issue(session, owner_user_id=owner_id)
    run_industry_scanner_refresh(session, owner_user_id=owner_id, trigger_type="MANUAL")
    build_spec_inputs(session, owner_user_id=owner_id)

    first = generate_ai_spec_evaluations(session, owner_user_id=owner_id)
    assert first.computed + first.skipped + first.updated >= 1
    rows = session.exec(select(AISpecEvaluation).where(AISpecEvaluation.owner_user_id == owner_id)).all()
    assert len(rows) >= 1
    row = rows[0]
    assert row.evaluation_status == "FALLBACK"
    assert row.model_name == "FALLBACK"
    assert row.prompt_version == "P60-03-v1"
    assert 0.0 <= row.ai_score <= 100.0
    assert 0.0 <= row.ai_confidence <= 1.0
    assert row.risk_level in {"LOW", "MEDIUM", "HIGH"}
    assert row.ai_rationale

    second = generate_ai_spec_evaluations(session, owner_user_id=owner_id)
    assert second.skipped >= 1
    assert second.computed == 0


def test_ai_spec_evaluations_api_and_summary(client: TestClient, session: Session) -> None:
    email = "ai-spec-api@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _import_lunar_issue(session, owner_user_id=owner_id)
    run_industry_scanner_refresh(session, owner_user_id=owner_id, trigger_type="MANUAL")

    latest = client.post("/api/v1/ai-spec-evaluations/refresh", headers=auth_headers(token))
    assert latest.status_code == 200
    payload = latest.json()["data"]
    assert payload["evaluations_computed"] + payload["evaluations_skipped"] + payload["evaluations_updated"] >= 1
    assert len(payload["items"]) >= 1
    assert payload["items"][0]["evaluation_status"] == "FALLBACK"

    listing = client.get("/api/v1/ai-spec-evaluations", headers=auth_headers(token))
    assert listing.status_code == 200
    assert listing.json()["data"]["pagination"]["total_count"] >= 1

    summary = client.get("/api/v1/ai-spec-evaluations/summary", headers=auth_headers(token))
    assert summary.status_code == 200
    body = summary.json()["data"]
    assert body["total_evaluations"] >= 1
    assert body["fallback_count"] >= 1

    repeat = client.get("/api/v1/ai-spec-evaluations/latest", headers=auth_headers(token))
    assert repeat.status_code == 200
    assert repeat.json()["data"]["evaluations_computed"] == 0
    assert repeat.json()["data"]["evaluations_skipped"] == 1
