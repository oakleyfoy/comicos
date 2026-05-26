"""P37-01 deterministic grading candidate registry."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select
from test_inventory import auth_headers, create_order, register_and_login

from app.models import InventoryCopy


def inventory_id_from_latest_order(client: TestClient, token: str) -> int:
    rsp = create_order(client, token)
    order_id = rsp["order_id"]
    detail = client.get(f"/orders/{order_id}", headers=auth_headers(token))
    assert detail.status_code == 200
    return detail.json()["items"][0]["inventory_copy_ids"][0]


def test_replay_safe_create_returns_same_detail(client: TestClient) -> None:
    tok = register_and_login(client, "grading-replay@example.com")
    inv_id = inventory_id_from_latest_order(client, tok)

    rk = "rk-grade-cand-001"
    body = {
        "inventory_item_id": inv_id,
        "target_grader": "CGC",
        "candidate_priority": "HIGH",
        "replay_key": rk,
        "estimated_raw_value": "100.00",
        "estimated_graded_value": "250.00",
    }

    rsp1 = client.post("/grading-candidates", json=body, headers=auth_headers(tok))
    assert rsp1.status_code in (200, 201), rsp1.text
    j1 = rsp1.json()

    rsp2 = client.post("/grading-candidates", json=body, headers=auth_headers(tok))
    assert rsp2.status_code == 200
    j2 = rsp2.json()

    assert j1["candidate"]["id"] == j2["candidate"]["id"]
    assert j2["candidate"]["replay_key"] == rk


def test_one_active_candidate_rule_blocks_second_pipeline_copy(client: TestClient) -> None:
    tok = register_and_login(client, "grading-one-active@example.com")
    inv_id = inventory_id_from_latest_order(client, tok)

    r1 = client.post(
        "/grading-candidates",
        json={
            "inventory_item_id": inv_id,
            "target_grader": "PSA",
            "candidate_priority": "LOW",
            "replay_key": "prime",
        },
        headers=auth_headers(tok),
    )
    assert r1.status_code == 201, r1.text

    r2 = client.post(
        "/grading-candidates",
        json={"inventory_item_id": inv_id, "target_grader": "CBCS", "candidate_priority": "LOW"},
        headers=auth_headers(tok),
    )
    assert r2.status_code == 409


def test_lifecycle_happy_path_and_events(client: TestClient) -> None:
    tok = register_and_login(client, "grading-lifecycle@example.com")
    inv_id = inventory_id_from_latest_order(client, tok)
    cid = client.post(
        "/grading-candidates",
        json={"inventory_item_id": inv_id, "target_grader": "CGC", "candidate_priority": "MEDIUM"},
        headers=auth_headers(tok),
    ).json()["candidate"]["id"]

    assert (
        client.post(f"/grading-candidates/{cid}/review", headers=auth_headers(tok)).status_code
        == 200
    )
    assert (
        client.post(f"/grading-candidates/{cid}/ready", headers=auth_headers(tok)).status_code
        == 200
    )
    assert (
        client.post(f"/grading-candidates/{cid}/submit", headers=auth_headers(tok)).status_code
        == 200
    )
    assert (
        client.post(
            f"/grading-candidates/{cid}/grade", json={}, headers=auth_headers(tok)
        ).status_code
        == 200
    )

    detail = client.get(f"/grading-candidates/{cid}", headers=auth_headers(tok)).json()
    assert detail["candidate"]["status"] == "GRADED"
    events = detail["lifecycle_events"]
    types = [e["event_type"] for e in events]
    assert "CREATED" in types
    assert "REVIEW_STARTED" in types
    assert "READY_FOR_SUBMISSION" in types
    assert "SUBMITTED" in types
    assert "GRADED" in types


def test_append_evidence_and_snapshot_stable(client: TestClient) -> None:
    tok = register_and_login(client, "grading-evidence@example.com")
    inv_id = inventory_id_from_latest_order(client, tok)
    cid = client.post(
        "/grading-candidates",
        json={
            "inventory_item_id": inv_id,
            "target_grader": "RAW_ONLY",
            "candidate_priority": "ELITE",
        },
        headers=auth_headers(tok),
    ).json()["candidate"]["id"]

    d1 = client.get(f"/grading-candidates/{cid}", headers=auth_headers(tok)).json()
    chk0 = d1["candidate"]["latest_snapshot_checksum"]

    client.post(
        f"/grading-candidates/{cid}/evidence",
        json={
            "evidence_type": "FMV",
            "lineage_domain": "fmv_attachment",
            "lineage_key": "inv/fmv:v1",
            "reference_json": {"note": "read-only lineage"},
        },
        headers=auth_headers(tok),
    )

    d2 = client.get(f"/grading-candidates/{cid}", headers=auth_headers(tok)).json()
    assert d2["candidate"]["evidence_count"] == 1
    assert d2["candidate"]["latest_snapshot_checksum"] != chk0
    snaps = sorted(d2["snapshots"], key=lambda s: (s["id"],))
    chks = [s["checksum"] for s in snaps]
    assert len(set(chks)) == len(chks)


def test_ops_requires_admin(monkeypatch, client: TestClient) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "grading-admin@example.com")
    from app.core.config import get_settings

    get_settings.cache_clear()

    tok = register_and_login(client, "grading-civilian@example.com")
    rsp = client.get("/ops/grading-candidates", headers=auth_headers(tok))
    assert rsp.status_code == 403


def test_owner_scoping_returns_404_cross_user(client: TestClient) -> None:
    alice = register_and_login(client, "grading-alice@example.com")
    bob = register_and_login(client, "grading-bob@example.com")
    inv_id = inventory_id_from_latest_order(client, alice)
    cid = client.post(
        "/grading-candidates",
        json={"inventory_item_id": inv_id, "target_grader": "CGC", "candidate_priority": "LOW"},
        headers=auth_headers(alice),
    ).json()["candidate"]["id"]

    miss = client.get(f"/grading-candidates/{cid}", headers=auth_headers(bob))
    assert miss.status_code == 404


def test_no_inventory_row_mutation_on_create(client: TestClient, session: Session) -> None:
    tok = register_and_login(client, "grading-no-inv-mut@example.com")
    inv_id = inventory_id_from_latest_order(client, tok)

    before = session.exec(select(InventoryCopy).where(InventoryCopy.id == inv_id)).first()
    assert before is not None
    acq = before.acquisition_cost

    session.expire_all()
    client.post(
        "/grading-candidates",
        json={"inventory_item_id": inv_id, "target_grader": "PSA", "candidate_priority": "HIGH"},
        headers=auth_headers(tok),
    )
    session.expire_all()
    after = session.exec(select(InventoryCopy).where(InventoryCopy.id == inv_id)).first()
    assert after is not None
    assert after.acquisition_cost == acq


def test_latest_snapshot_checksum_stable_on_repeat_read(client: TestClient) -> None:
    tok = register_and_login(client, "grading-stable-read@example.com")
    inv_id = inventory_id_from_latest_order(client, tok)
    cid = client.post(
        "/grading-candidates",
        json={"inventory_item_id": inv_id, "target_grader": "PSA", "candidate_priority": "LOW"},
        headers=auth_headers(tok),
    ).json()["candidate"]["id"]
    a = client.get(f"/grading-candidates/{cid}", headers=auth_headers(tok)).json()
    b = client.get(f"/grading-candidates/{cid}", headers=auth_headers(tok)).json()
    assert a["candidate"]["latest_snapshot_checksum"] == b["candidate"]["latest_snapshot_checksum"]


def test_checksum_differs_when_inventory_item_differs(client: TestClient) -> None:
    tok = register_and_login(client, "grading-chk@example.com")
    i1 = inventory_id_from_latest_order(client, tok)
    i2 = inventory_id_from_latest_order(client, tok)

    def create_for(inv: int, rk: str) -> str:
        rsp = client.post(
            "/grading-candidates",
            json={
                "inventory_item_id": inv,
                "target_grader": "CGC",
                "candidate_priority": "MEDIUM",
                "replay_key": rk,
                "estimated_raw_value": "10.00",
                "estimated_graded_value": "40.00",
                "estimated_spread": "30.00",
                "estimated_grading_cost": "25.00",
                "estimated_roi": "0.25",
            },
            headers=auth_headers(tok),
        )
        assert rsp.status_code in (200, 201), rsp.text
        return rsp.json()["candidate"]["latest_snapshot_checksum"]

    c1 = create_for(i1, "chk-a")
    c2 = create_for(i2, "chk-b")
    assert c1 != c2
