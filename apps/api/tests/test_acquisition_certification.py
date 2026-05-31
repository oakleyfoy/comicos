from __future__ import annotations

import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import InventoryCopy, User
from app.models.acquisition_certification import AcquisitionCertificationRun
from app.services.acquisition_certification import run_acquisition_certification
from app.services.acquisition_opportunities import persist_acquisition_opportunities
from app.services.collection_gaps import persist_collection_gaps
from app.services.marketplace_acquisitions import ensure_marketplace_acquisition_sources
from app.services.recovery_recommendations import build_operations_dashboard
from test_inventory import auth_headers, create_order, register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def _battle_beast_items(numbers: list[str]) -> list[dict]:
    return [
        {
            "title": "Battle Beast",
            "publisher": "Image",
            "issue_number": num,
            "cover_name": "Cover A",
            "printing": None,
            "ratio": None,
            "variant_type": None,
            "cover_artist": None,
            "quantity": 1,
            "raw_item_price": 5.00,
        }
        for num in numbers
    ]


def test_run_acquisition_certification_persists(client: TestClient, session: Session) -> None:
    email = "ac-cert@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    report = run_acquisition_certification(session, owner_user_id=owner_id)
    assert report.readiness_score >= 90.0
    assert report.certification_result == "APPROVED_FOR_PRODUCTION"
    assert report.report.health_status == "HEALTHY"
    assert len(report.checks) >= 7
    row = session.exec(
        select(AcquisitionCertificationRun).where(AcquisitionCertificationRun.owner_user_id == owner_id)
    ).one()
    assert row.readiness_score == report.readiness_score


def test_certification_domain_scores(client: TestClient, session: Session) -> None:
    email = "ac-domains@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    report = run_acquisition_certification(session, owner_user_id=owner_id)
    assert report.collection_gap_score == 100.0
    assert report.marketplace_score == 100.0
    assert report.determinism_score == 100.0


def test_certification_api_latest_and_ops(client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    email = "ac-cert-api@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    run_acquisition_certification(session, owner_user_id=owner_id)
    latest = client.get("/api/v1/acquisition-certification/latest", headers=auth_headers(token))
    assert latest.status_code == 200
    assert latest.json()["data"]["readiness_score"] >= 90.0
    forbidden = client.post("/api/v1/acquisition-certification/run", headers=auth_headers(token))
    assert forbidden.status_code == 403


def test_certification_rerun_appends_history(client: TestClient, session: Session) -> None:
    email = "ac-rerun@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    run_acquisition_certification(session, owner_user_id=owner_id)
    run_acquisition_certification(session, owner_user_id=owner_id)
    rows = session.exec(
        select(AcquisitionCertificationRun).where(AcquisitionCertificationRun.owner_user_id == owner_id)
    ).all()
    assert len(rows) == 2


def test_battle_beast_stack_certification(client: TestClient, session: Session) -> None:
    email = "ac-battle@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token, items=_battle_beast_items(["1", "2", "4", "5"]))
    copies = list(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).all())
    for copy in copies:
        copy.current_fmv = Decimal("25.00")
        session.add(copy)
    session.commit()
    list_id = client.get("/api/v1/want-lists", headers=auth_headers(token)).json()["data"]["items"][0]["id"]
    client.post(
        f"/api/v1/want-lists/{list_id}/items",
        headers=auth_headers(token),
        json={
            "publisher": "Image",
            "series_name": "Battle Beast",
            "issue_number": "3",
            "priority": "CRITICAL",
        },
    )
    persist_collection_gaps(session, owner_user_id=owner_id)
    persist_acquisition_opportunities(session, owner_user_id=owner_id)
    manual_id = next(s for s in ensure_marketplace_acquisition_sources(session) if s.source_type == "MANUAL").id
    created = client.post(
        "/api/v1/marketplace-acquisitions",
        headers=auth_headers(token),
        json={
            "marketplace_source_id": int(manual_id or 0),
            "title": "Battle Beast #3",
            "publisher": "Image",
            "series_name": "Battle Beast",
            "issue_number": "3",
            "total_price": 10.0,
        },
    )
    cand_id = created.json()["data"]["id"]
    client.post(f"/api/v1/marketplace-acquisitions/{cand_id}/evaluate", headers=auth_headers(token))
    report = run_acquisition_certification(session, owner_user_id=owner_id)
    assert report.readiness_score >= 90.0
    assert report.certification_result == "APPROVED_FOR_PRODUCTION"
    dash = build_operations_dashboard(session, owner_user_id=owner_id)
    assert dash.acquisition_certification is not None
    assert dash.acquisition_certification.readiness_score >= 90.0
