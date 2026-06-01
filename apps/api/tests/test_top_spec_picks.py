from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models.top_spec_pick import TopSpecPick
from app.services.industry_scanner_automation import run_industry_scanner_refresh
from app.services.top_spec_pick_engine import generate_top_spec_picks
from test_industry_scanner_automation import _import_lunar_issue, _owner_id
from test_inventory import auth_headers, register_and_login


def test_generate_top_spec_picks_persists_and_idempotent(client: TestClient, session: Session) -> None:
    email = "top-spec-persist@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _import_lunar_issue(session, owner_user_id=owner_id)
    run_industry_scanner_refresh(session, owner_user_id=owner_id, trigger_type="MANUAL")

    first = generate_top_spec_picks(session, owner_user_id=owner_id, limit=20)
    rows = session.exec(
        select(TopSpecPick).where(TopSpecPick.owner_user_id == owner_id).order_by(TopSpecPick.rank.asc())
    ).all()
    assert len(rows) >= 1
    assert first.computed >= 1 or first.skipped is True
    assert rows[0].rank == 1
    assert 0.0 <= rows[0].final_score <= 100.0
    assert 0.0 <= rows[0].confidence_score <= 1.0
    assert rows[0].risk_level in {"LOW", "MEDIUM", "HIGH"}
    release_ids = [row.release_id for row in rows if row.release_id is not None]
    assert len(release_ids) == len(set(release_ids))
    spec_ids = [row.spec_input_id for row in rows]
    assert len(spec_ids) == len(set(spec_ids))

    second = generate_top_spec_picks(session, owner_user_id=owner_id, limit=20)
    assert second.skipped is True
    assert second.computed == 0


def test_top_spec_picks_api_and_summary(client: TestClient, session: Session) -> None:
    email = "top-spec-api@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _import_lunar_issue(session, owner_user_id=owner_id)
    run_industry_scanner_refresh(session, owner_user_id=owner_id, trigger_type="MANUAL")

    latest = client.get("/api/v1/top-spec-picks/latest", headers=auth_headers(token))
    assert latest.status_code == 200
    payload = latest.json()["data"]
    assert len(payload["items"]) >= 1
    assert payload["picks_computed"] >= 1 or payload["picks_skipped"] is True
    assert len(payload["items"]) >= 1
    assert payload["items"][0]["rank"] == 1

    listing = client.get("/api/v1/top-spec-picks", headers=auth_headers(token))
    assert listing.status_code == 200
    assert listing.json()["data"]["pagination"]["total_count"] >= 1

    summary = client.get("/api/v1/top-spec-picks/summary", headers=auth_headers(token))
    assert summary.status_code == 200
    assert summary.json()["data"]["total_picks"] >= 1

    repeat = client.get("/api/v1/top-spec-picks/latest", headers=auth_headers(token))
    assert repeat.status_code == 200
    assert repeat.json()["data"]["picks_skipped"] is True
