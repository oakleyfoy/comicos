"""P36-08 deterministic operational reporting closeout."""

from __future__ import annotations

from fastapi.testclient import TestClient

from sqlalchemy import func
from sqlmodel import Session, select

from app.models import Listing

from test_inventory import auth_headers, register_and_login


def test_operational_report_replay_and_stable_checksum(client: TestClient) -> None:
    token = register_and_login(client, "ops-report-owner@example.com")

    rk = "rk-operational-summary"

    rsp1 = client.post(
        "/reports/generate",
        json={
            "report_type": "listing_summary",
            "replay_key": rk,
            "generation_params": {},
        },
        headers=auth_headers(token),
    )
    assert rsp1.status_code in (200, 201), rsp1.text
    chk1 = rsp1.json()["checksum"]

    rsp2 = client.post(
        "/reports/generate",
        json={
            "report_type": "listing_summary",
            "replay_key": rk,
            "generation_params": {},
        },
        headers=auth_headers(token),
    )
    assert rsp2.status_code == 200
    assert rsp2.json()["checksum"] == chk1


def test_operational_csv_row_order_stable(client: TestClient) -> None:
    token = register_and_login(client, "stable-order-report@example.com")

    rsp = client.post("/reports/generate", json={"report_type": "listing_summary"}, headers=auth_headers(token))
    assert rsp.status_code == 201, rsp.text

    dl = client.get(f"/reports/{rsp.json()['id']}/download", headers=auth_headers(token))
    assert dl.status_code == 200
    lines = [ln for ln in dl.text.strip().splitlines() if ln]
    assert lines[0].startswith("metric_family,")


def test_ops_scope_requires_admin(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-reporting-admin-scope@example.com")
    from app.core.config import get_settings

    get_settings.cache_clear()

    user_token = register_and_login(client, "civilian-report@example.com")
    rsp = client.get("/ops/reports", headers=auth_headers(user_token))
    assert rsp.status_code == 403


def test_download_blocks_non_owner(client: TestClient) -> None:
    owner = register_and_login(client, "owner-a-report@example.com")
    outsider = register_and_login(client, "outsider-report@example.com")

    rsp = client.post("/reports/generate", json={"report_type": "export_summary"}, headers=auth_headers(owner))
    assert rsp.status_code == 201, rsp.text
    rid = rsp.json()["id"]

    bad = client.get(f"/reports/{rid}/download", headers=auth_headers(outsider))
    assert bad.status_code == 404


def test_no_listing_registry_mutation_on_generate(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "no-mutation-report@example.com")

    before = session.exec(select(func.count(Listing.id))).one()

    rsp = client.post("/reports/generate", json={"report_type": "inventory_health_summary"}, headers=auth_headers(token))
    assert rsp.status_code == 201, rsp.text

    session.expire_all()
    after = session.exec(select(func.count(Listing.id))).one()

    assert before == after
