"""P37-04 deterministic grading submission batches."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from test_inventory import auth_headers, create_order, register_and_login

from app.core.config import get_settings
from app.models import GradingSubmissionBatch, GradingSubmissionLifecycleEvent, InventoryCopy


def inventory_id_from_latest_order(client: TestClient, token: str) -> int:
    rsp = create_order(client, token)
    order_id = rsp["order_id"]
    detail = client.get(f"/orders/{order_id}", headers=auth_headers(token))
    assert detail.status_code == 200
    return detail.json()["items"][0]["inventory_copy_ids"][0]


def make_ready_candidate(client: TestClient, token: str, inventory_id: int, target_grader: str = "CGC") -> int:
    create_rsp = client.post(
        "/grading-candidates",
        headers=auth_headers(token),
        json={
            "inventory_item_id": inventory_id,
            "target_grader": target_grader,
            "target_grade": "9.8",
            "candidate_priority": "HIGH",
            "estimated_raw_value": "100.00",
            "estimated_graded_value": "240.00",
            "estimated_grading_cost": "35.00",
            "estimated_roi": "1.45",
        },
    )
    assert create_rsp.status_code in (200, 201), create_rsp.text
    candidate_id = create_rsp.json()["candidate"]["id"]
    assert client.post(f"/grading-candidates/{candidate_id}/review", headers=auth_headers(token)).status_code == 200
    assert client.post(f"/grading-candidates/{candidate_id}/ready", headers=auth_headers(token)).status_code == 200
    return candidate_id


def create_submission_batch(
    client: TestClient,
    token: str,
    candidate_ids: list[int],
    *,
    batch_name: str = "May Grader Drop",
    target_grader: str = "CGC",
    replay_key: str = "submission-rk-001",
) -> dict:
    rsp = client.post(
        "/grading-submission-batches",
        headers=auth_headers(token),
        json={
            "grading_candidate_ids": candidate_ids,
            "target_grader": target_grader,
            "batch_name": batch_name,
            "estimated_turnaround_days": 90,
            "submission_date": "2026-05-26",
            "replay_key": replay_key,
            "notes": "submission batch seed",
        },
    )
    assert rsp.status_code in (200, 201), rsp.text
    return rsp.json()


def test_replay_safe_creation_and_candidate_submission(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "submission-owner@example.com")
    inv1 = inventory_id_from_latest_order(client, token)
    inv2 = inventory_id_from_latest_order(client, token)
    c1 = make_ready_candidate(client, token, inv1)
    c2 = make_ready_candidate(client, token, inv2)

    first = create_submission_batch(client, token, [c1, c2], replay_key="submission-rk-001")
    assert first["batch"]["status"] == "DRAFT"
    assert first["batch"]["item_count"] == 2
    assert first["batch"]["estimated_total_cost"] == "95.00"
    assert [item["status"] for item in first["items"]] == ["INCLUDED", "INCLUDED"]

    second = create_submission_batch(client, token, [c1, c2], replay_key="submission-rk-001")
    assert second["batch"]["id"] == first["batch"]["id"]
    assert second["batch"]["checksum"] == first["batch"]["checksum"]

    detail = client.get(f"/grading-candidates/{c1}", headers=auth_headers(token))
    assert detail.status_code == 200
    assert detail.json()["candidate"]["status"] == "SUBMITTED"

    lifecycle_events = session.exec(select(GradingSubmissionLifecycleEvent)).all()
    assert any(event.event_type == "CREATED" for event in lifecycle_events)


def test_lifecycle_transitions_shipment_tracking_and_completion(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "submission-lifecycle@example.com")
    inventory_id = inventory_id_from_latest_order(client, token)
    candidate_id = make_ready_candidate(client, token, inventory_id, target_grader="PSA")
    batch = create_submission_batch(client, token, [candidate_id], batch_name="Lifecycle Batch", target_grader="PSA")
    batch_id = batch["batch"]["id"]

    assert client.post(f"/grading-submission-batches/{batch_id}/ready", headers=auth_headers(token)).status_code == 200
    assert client.post(f"/grading-submission-batches/{batch_id}/ship", headers=auth_headers(token)).status_code == 200
    assert client.post(f"/grading-submission-batches/{batch_id}/receive", headers=auth_headers(token)).status_code == 200
    assert client.post(f"/grading-submission-batches/{batch_id}/grading", headers=auth_headers(token)).status_code == 200
    assert client.post(f"/grading-submission-batches/{batch_id}/return-ship", headers=auth_headers(token)).status_code == 200
    shipped = client.post(
        f"/grading-submission-batches/{batch_id}/shipments",
        headers=auth_headers(token),
        json={
            "shipment_direction": "RETURN",
            "carrier": "UPS",
            "tracking_number": "1ZRETURN123",
            "shipped_date": "2026-05-27",
            "delivered_date": "2026-05-30",
            "insured_amount": "120.00",
            "shipping_cost": "17.50",
        },
    )
    assert shipped.status_code == 200, shipped.text
    completed = client.post(f"/grading-submission-batches/{batch_id}/complete", headers=auth_headers(token))
    assert completed.status_code == 200, completed.text
    payload = completed.json()
    assert payload["batch"]["status"] == "COMPLETED"
    assert payload["batch"]["actual_turnaround_days"] == 4
    assert payload["items"][0]["status"] == "RETURNED"
    assert payload["items"][0]["final_grade"] is None
    assert len(payload["shipments"]) == 1
    assert payload["shipments"][0]["tracking_number"] == "1ZRETURN123"

    candidate_detail = client.get(f"/grading-candidates/{candidate_id}", headers=auth_headers(token))
    assert candidate_detail.status_code == 200
    assert candidate_detail.json()["candidate"]["status"] == "GRADED"

    events = session.exec(select(GradingSubmissionLifecycleEvent).where(GradingSubmissionLifecycleEvent.grading_submission_batch_id == batch_id)).all()
    assert {event.event_type for event in events} >= {"CREATED", "READY", "SHIPPED", "RECEIVED_BY_GRADER", "GRADING_STARTED", "RETURN_SHIPPED", "COMPLETED"}


def test_one_active_batch_rule_and_no_inventory_mutation(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "submission-conflict@example.com")
    inventory_id = inventory_id_from_latest_order(client, token)
    candidate_id = make_ready_candidate(client, token, inventory_id, target_grader="CBCS")
    before = session.get(InventoryCopy, inventory_id)
    assert before is not None
    before_fmv = before.current_fmv

    first = create_submission_batch(client, token, [candidate_id], replay_key="submission-conflict-1")
    assert first["batch"]["status"] == "DRAFT"

    conflict = client.post(
        "/grading-submission-batches",
        headers=auth_headers(token),
        json={
            "grading_candidate_ids": [candidate_id],
            "target_grader": "CBCS",
            "batch_name": "Second batch",
            "replay_key": "submission-conflict-2",
        },
    )
    assert conflict.status_code == 409

    session.expire_all()
    after = session.get(InventoryCopy, inventory_id)
    assert after is not None
    assert after.current_fmv == before_fmv


def test_owner_scoping_and_ops_visibility(client: TestClient, session: Session, monkeypatch) -> None:
    owner = register_and_login(client, "submission-owner-scope@example.com")
    other = register_and_login(client, "submission-other-scope@example.com")
    admin = register_and_login(client, "submission-admin@example.com")

    monkeypatch.setenv("OPS_ADMIN_EMAILS", "submission-admin@example.com")
    get_settings.cache_clear()

    owner_inventory = inventory_id_from_latest_order(client, owner)
    other_inventory = inventory_id_from_latest_order(client, other)
    owner_candidate = make_ready_candidate(client, owner, owner_inventory, target_grader="PSA")
    other_candidate = make_ready_candidate(client, other, other_inventory, target_grader="CGC")
    owner_batch = create_submission_batch(client, owner, [owner_candidate], replay_key="submission-owner-scope")
    other_batch = create_submission_batch(client, other, [other_candidate], replay_key="submission-other-scope")

    miss = client.get(f"/grading-submission-batches/{owner_batch['batch']['id']}", headers=auth_headers(other))
    assert miss.status_code == 404

    ops_list = client.get(
        "/ops/grading-submission-batches",
        params={"owner_user_id": owner_batch["batch"]["owner_user_id"]},
        headers=auth_headers(admin),
    )
    assert ops_list.status_code == 200, ops_list.text
    ops_json = ops_list.json()
    assert ops_json["total_items"] >= 1

    events = client.get(
        "/ops/grading-submission-events",
        params={"owner_user_id": owner_batch["batch"]["owner_user_id"]},
        headers=auth_headers(admin),
    )
    assert events.status_code == 200, events.text

    shipments = client.get("/ops/grading-submission-shipments", headers=auth_headers(admin))
    assert shipments.status_code == 200, shipments.text

    batch_row = session.get(GradingSubmissionBatch, owner_batch["batch"]["id"])
    assert batch_row is not None
    assert batch_row.owner_user_id == owner_batch["batch"]["owner_user_id"]
    _ = other_batch
