from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session

from app.models import Listing
from app.core.config import get_settings

from test_inventory import auth_headers, create_order, register_and_login


def _copy_id(client: TestClient, token: str) -> int:
    return int(client.get("/inventory", headers=auth_headers(token)).json()["items"][0]["inventory_copy_id"])


def _listing_id_ready(client: TestClient, token: str, *, rk: str | None = None) -> int:
    cid = _copy_id(client, token)
    rsp = client.post(
        "/listings",
        json={
            "inventory_copy_id": cid,
            "source_type": "manual",
            "title": "Export me",
            "replay_key": rk or f"rk-{uuid.uuid4().hex[:12]}",
        },
        headers=auth_headers(token),
    )
    assert rsp.status_code in (200, 201)
    lid = int(rsp.json()["id"])
    assert client.patch(f"/listings/{lid}", json={"status": "READY"}, headers=auth_headers(token)).status_code == 200
    return lid


def test_default_templates_exist(client: TestClient) -> None:
    token = register_and_login(client, "export-tpl@example.com")
    tpls = client.get("/listing-export-templates", headers=auth_headers(token))
    assert tpls.status_code == 200
    chans = sorted({row["channel"] for row in tpls.json()})
    assert chans == sorted(chans)
    assert "generic_csv" in chans
    assert "ebay" in chans


def test_export_run_deterministic_and_replay(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "export-det@example.com")
    create_order(client, token)
    lid = _listing_id_ready(client, token)

    payload = {"channel": "generic_csv", "listing_ids": [lid], "replay_key": "rk-export-run-a"}

    lst_row = session.get(Listing, lid)
    assert lst_row is not None
    before_status = lst_row.status

    a = client.post("/listing-export-runs", json=payload, headers=auth_headers(token))
    assert a.status_code == 201
    run_id_a = int(a.json()["id"])
    chk_a = a.json()["checksum"]

    dup = client.post("/listing-export-runs", json=payload, headers=auth_headers(token))
    assert dup.status_code == 200
    assert int(dup.json()["id"]) == run_id_a
    assert dup.json()["checksum"] == chk_a

    session.refresh(lst_row)
    assert lst_row.status == before_status


def test_export_checksum_stable_twice_completed(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "export-chk@example.com")
    create_order(client, token)
    lid = _listing_id_ready(client, token)

    p1 = client.post(
        "/listing-export-runs",
        json={"channel": "generic_csv", "listing_ids": [lid]},
        headers=auth_headers(token),
    )
    p2 = client.post(
        "/listing-export-runs",
        json={"channel": "generic_csv", "listing_ids": [lid]},
        headers=auth_headers(token),
    )
    assert p1.status_code == 201
    assert p2.status_code == 201
    assert p1.json()["checksum"] == p2.json()["checksum"]


def test_export_skips_non_exportable(client: TestClient) -> None:
    token = register_and_login(client, "export-skip@example.com")
    create_order(client, token)
    cid = _copy_id(client, token)
    rsp_li = client.post(
        "/listings",
        json={
            "inventory_copy_id": cid,
            "source_type": "manual",
            "title": "Draft only",
            "replay_key": f"rk-draft-{uuid.uuid4().hex[:8]}",
        },
        headers=auth_headers(token),
    )
    assert rsp_li.status_code in (200, 201)
    lid = int(rsp_li.json()["id"])

    rsp = client.post(
        "/listing-export-runs",
        json={"channel": "generic_csv", "listing_ids": [lid]},
        headers=auth_headers(token),
    )
    assert rsp.status_code == 201
    body = rsp.json()
    assert body["skipped_listing_count"] == 1
    assert body["exported_listing_count"] == 0
    skips = [row for row in body["items"] if row["status"] == "SKIPPED"]
    assert skips and skips[0]["skip_reason"] == "SKIP_STATUS_DRAFT"


def test_export_owner_scoping(client: TestClient, session: Session) -> None:
    a = register_and_login(client, "export-own-a@example.com")
    b = register_and_login(client, "export-own-b@example.com")
    create_order(client, a)
    create_order(client, b)
    lid_a = _listing_id_ready(client, a)

    rsp = client.post(
        "/listing-export-runs",
        json={"channel": "generic_csv", "listing_ids": [lid_a]},
        headers=auth_headers(b),
    )
    assert rsp.status_code == 201
    assert rsp.json()["skipped_listing_count"] == 1
    assert rsp.json()["exported_listing_count"] == 0


def test_export_csv_download(client: TestClient) -> None:
    token = register_and_login(client, "export-dl@example.com")
    create_order(client, token)
    lid = _listing_id_ready(client, token)

    rsp = client.post(
        "/listing-export-runs",
        json={"channel": "ebay", "listing_ids": [lid]},
        headers=auth_headers(token),
    )
    assert rsp.status_code == 201
    rid = rsp.json()["id"]
    dl = client.get(f"/listing-export-runs/{rid}/download", headers=auth_headers(token))
    assert dl.status_code == 200
    text = dl.text
    assert "listing_id" in text
    assert "category" in text


def test_export_ops_download(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "export-ops-dl@example.com")
    get_settings.cache_clear()

    ops = register_and_login(client, "export-ops-dl@example.com")
    owner = register_and_login(client, "export-owner-dl@example.com")
    create_order(client, owner)
    lid = _listing_id_ready(client, owner)

    rsp = client.post(
        "/listing-export-runs",
        json={"channel": "generic_csv", "listing_ids": [lid]},
        headers=auth_headers(owner),
    )
    assert rsp.status_code == 201
    rid = int(rsp.json()["id"])

    dl = client.get(f"/ops/listing-export-runs/{rid}/download", headers=auth_headers(ops))
    assert dl.status_code == 200


def test_export_requires_ops(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPS_ADMIN_EMAILS", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()

    tok = register_and_login(client, "export-notops@example.com")
    assert client.get("/ops/listing-export-runs", headers=auth_headers(tok)).status_code == 403

    monkeypatch.setenv("OPS_ADMIN_EMAILS", "export-realops@example.com")
    get_settings.cache_clear()
    ops = register_and_login(client, "export-realops@example.com")
    assert client.get("/ops/listing-export-runs", headers=auth_headers(ops)).status_code == 200


def test_row_order_sorted_ids(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "export-roworder@example.com")
    create_order(client, token, retailer="ShopA")
    create_order(client, token, retailer="ShopB")

    lids = [_listing_id_ready(client, token) for _ in range(2)]
    rsp = client.post(
        "/listing-export-runs",
        json={
            "channel": "generic_csv",
            "listing_ids": sorted(lids, reverse=True),
        },
        headers=auth_headers(token),
    )
    assert rsp.status_code == 201

    exported = [row for row in rsp.json()["items"] if row["status"] == "EXPORTED"]
    lids_out = [int(row["listing_id"]) for row in exported]
    assert lids_out == sorted(lids_out)


class TestListingExportPagination:
    def test_dashboard_summary_returns(self, client: TestClient) -> None:
        token = register_and_login(client, "export-dash@example.com")
        rsp = client.get("/listing-export-runs/dashboard-summary", headers=auth_headers(token))
        assert rsp.status_code == 200
        payload = rsp.json()
        assert "completed_run_count" in payload
        assert "skipped_rows_lifetime_sum" in payload
