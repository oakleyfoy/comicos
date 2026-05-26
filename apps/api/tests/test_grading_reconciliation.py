"""P37-05 deterministic grading reconciliation tests."""

from __future__ import annotations

from decimal import Decimal

from sqlmodel import Session, select

from fastapi.testclient import TestClient

from test_grading_submission_batches import (
    create_submission_batch,
    inventory_id_from_latest_order,
    make_ready_candidate,
)
from test_inventory import auth_headers, register_and_login

from app.core.config import get_settings
from app.models import (
    GraderPerformanceSnapshot,
    GradingReconciliationHistory,
    GradingReconciliationRecord,
    GradingSubmissionItem,
    InventoryCopy,
    InventoryFmvSnapshot,
    Listing,
    ListingPriceHistory,
)
from app.services.grading_reconciliation import _accuracy_status, deterministic_checksum


def complete_submission_batch(client: TestClient, token: str, batch_id: int) -> None:
    assert client.post(f"/grading-submission-batches/{batch_id}/ready", headers=auth_headers(token)).status_code == 200
    assert client.post(f"/grading-submission-batches/{batch_id}/ship", headers=auth_headers(token)).status_code == 200
    assert client.post(f"/grading-submission-batches/{batch_id}/receive", headers=auth_headers(token)).status_code == 200
    assert client.post(f"/grading-submission-batches/{batch_id}/grading", headers=auth_headers(token)).status_code == 200
    assert client.post(f"/grading-submission-batches/{batch_id}/return-ship", headers=auth_headers(token)).status_code == 200
    assert client.post(
        f"/grading-submission-batches/{batch_id}/shipments",
        headers=auth_headers(token),
        json={
            "shipment_direction": "RETURN",
            "carrier": "UPS",
            "tracking_number": "1ZRECON123",
            "shipped_date": "2026-05-27",
            "delivered_date": "2026-05-30",
            "insured_amount": "125.00",
            "shipping_cost": "18.00",
        },
    ).status_code == 200
    assert client.post(f"/grading-submission-batches/{batch_id}/complete", headers=auth_headers(token)).status_code == 200


def test_accuracy_status_and_checksum_are_deterministic() -> None:
    assert _accuracy_status("9.8", "9.9") == "ABOVE_EXPECTATION"
    assert _accuracy_status("9.8", "9.8") == "MET_EXPECTATION"
    assert _accuracy_status("9.8", "9.6") == "BELOW_EXPECTATION"
    assert _accuracy_status(None, "9.8") == "INSUFFICIENT_DATA"
    payload = {"item": 11, "grade": "9.8", "roi_delta": "0.50000000"}
    assert deterministic_checksum(payload) == deterministic_checksum(payload)


def test_reconcile_persists_final_grade_and_is_replay_safe(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "reconcile-owner@example.com")
    inventory_id = inventory_id_from_latest_order(client, token)
    candidate_id = make_ready_candidate(client, token, inventory_id, target_grader="CGC")
    batch = create_submission_batch(client, token, [candidate_id], batch_name="Recon Batch", target_grader="CGC")
    batch_id = batch["batch"]["id"]
    complete_submission_batch(client, token, batch_id)

    item_id = session.exec(
        select(GradingSubmissionItem.id).where(GradingSubmissionItem.grading_submission_batch_id == batch_id)
    ).one()

    body = {
        "grading_submission_item_id": item_id,
        "final_grade": "9.6",
        "realized_graded_value": "260.00",
        "reconciled_at": "2026-05-30T12:00:00Z",
    }
    first = client.post("/grading-reconciliation/reconcile", headers=auth_headers(token), json=body)
    assert first.status_code == 201, first.text
    payload = first.json()
    assert payload["record"]["reconciliation_status"] == "RECONCILED"
    assert payload["record"]["grading_accuracy_status"] == "BELOW_EXPECTATION"
    assert payload["record"]["roi_delta"] is not None
    assert payload["record"]["final_grade"] == "9.6"
    assert any(row["evidence_type"] == "SUBMISSION_BATCH" for row in payload["evidence"])

    second = client.post("/grading-reconciliation/reconcile", headers=auth_headers(token), json=body)
    assert second.status_code == 201, second.text
    assert second.json()["record"]["id"] == payload["record"]["id"]

    session.expire_all()
    item = session.get(GradingSubmissionItem, item_id)
    assert item is not None
    assert item.final_grade == "9.6"

    perf_rows = session.exec(select(GraderPerformanceSnapshot).where(GraderPerformanceSnapshot.grader == "CGC")).all()
    assert len(perf_rows) >= 1


def test_history_appends_and_no_fmv_or_pricing_mutation(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "reconcile-mutation@example.com")
    inventory_id = inventory_id_from_latest_order(client, token)
    candidate_id = make_ready_candidate(client, token, inventory_id, target_grader="PSA")
    batch = create_submission_batch(client, token, [candidate_id], batch_name="Mutation Batch", target_grader="PSA")
    batch_id = batch["batch"]["id"]
    complete_submission_batch(client, token, batch_id)

    inventory = session.get(InventoryCopy, inventory_id)
    assert inventory is not None
    before_fmv = inventory.current_fmv
    before_fmv_snapshots = session.exec(
        select(InventoryFmvSnapshot).where(InventoryFmvSnapshot.inventory_copy_id == inventory_id)
    ).all()
    listing = Listing(
        owner_user_id=int(inventory.user_id or 0),
        canonical_comic_issue_id=None,
        inventory_copy_id=inventory_id,
        source_type="manual",
        status="DRAFT",
        title="Recon Listing",
        description=None,
        condition_summary=None,
        asking_price_amount="111.00",
        asking_price_currency="USD",
        quantity=1,
    )
    session.add(listing)
    session.commit()
    before_price_histories = session.exec(select(ListingPriceHistory).where(ListingPriceHistory.listing_id == listing.id)).all()
    item_id = session.exec(
        select(GradingSubmissionItem.id).where(GradingSubmissionItem.grading_submission_batch_id == batch_id)
    ).one()

    first = client.post(
        "/grading-reconciliation/reconcile",
        headers=auth_headers(token),
        json={
            "grading_submission_item_id": item_id,
            "final_grade": "9.8",
            "realized_graded_value": "300.00",
            "reconciled_at": "2026-05-30T12:00:00Z",
        },
    )
    assert first.status_code == 201, first.text
    second = client.post(
        "/grading-reconciliation/reconcile",
        headers=auth_headers(token),
        json={
            "grading_submission_item_id": item_id,
            "final_grade": "9.9",
            "realized_graded_value": "340.00",
            "reconciled_at": "2026-05-31T12:00:00Z",
        },
    )
    assert second.status_code == 201, second.text

    session.expire_all()
    inventory_after = session.get(InventoryCopy, inventory_id)
    assert inventory_after is not None
    assert inventory_after.current_fmv == before_fmv
    after_fmv_snapshots = session.exec(
        select(InventoryFmvSnapshot).where(InventoryFmvSnapshot.inventory_copy_id == inventory_id)
    ).all()
    assert len(after_fmv_snapshots) == len(before_fmv_snapshots)

    listing_after = session.get(Listing, listing.id)
    assert listing_after is not None
    assert listing_after.asking_price_amount == Decimal("111.00")
    after_price_histories = session.exec(select(ListingPriceHistory).where(ListingPriceHistory.listing_id == listing.id)).all()
    assert len(after_price_histories) == len(before_price_histories)

    histories = session.exec(select(GradingReconciliationHistory).where(GradingReconciliationHistory.inventory_item_id == inventory_id)).all()
    assert len(histories) == 2


def test_owner_scoping_and_ops_visibility(client: TestClient, session: Session, monkeypatch) -> None:
    owner = register_and_login(client, "reconcile-scope-owner@example.com")
    other = register_and_login(client, "reconcile-scope-other@example.com")
    admin = register_and_login(client, "reconcile-scope-admin@example.com")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "reconcile-scope-admin@example.com")
    get_settings.cache_clear()

    owner_inventory = inventory_id_from_latest_order(client, owner)
    other_inventory = inventory_id_from_latest_order(client, other)
    owner_candidate = make_ready_candidate(client, owner, owner_inventory)
    other_candidate = make_ready_candidate(client, other, other_inventory)
    owner_batch = create_submission_batch(client, owner, [owner_candidate], batch_name="Owner Scope")
    other_batch = create_submission_batch(client, other, [other_candidate], batch_name="Other Scope")
    complete_submission_batch(client, owner, owner_batch["batch"]["id"])
    complete_submission_batch(client, other, other_batch["batch"]["id"])

    owner_item_id = session.exec(
        select(GradingSubmissionItem.id).where(GradingSubmissionItem.grading_submission_batch_id == owner_batch["batch"]["id"])
    ).one()
    other_item_id = session.exec(
        select(GradingSubmissionItem.id).where(GradingSubmissionItem.grading_submission_batch_id == other_batch["batch"]["id"])
    ).one()

    owner_record = client.post(
        "/grading-reconciliation/reconcile",
        headers=auth_headers(owner),
        json={"grading_submission_item_id": owner_item_id, "final_grade": "9.8", "realized_graded_value": "300.00"},
    )
    assert owner_record.status_code == 201, owner_record.text
    other_record = client.post(
        "/grading-reconciliation/reconcile",
        headers=auth_headers(other),
        json={"grading_submission_item_id": other_item_id, "final_grade": "9.4", "realized_graded_value": "240.00"},
    )
    assert other_record.status_code == 201, other_record.text

    miss = client.get(f"/grading-reconciliation/{owner_record.json()['record']['id']}", headers=auth_headers(other))
    assert miss.status_code == 404

    ops_list = client.get(
        "/ops/grading-reconciliation",
        params={"owner_user_id": owner_record.json()["record"]["owner_user_id"]},
        headers=auth_headers(admin),
    )
    assert ops_list.status_code == 200, ops_list.text
    assert ops_list.json()["total_items"] >= 1

    ops_perf = client.get(
        "/ops/grader-performance",
        params={"owner_user_id": owner_record.json()["record"]["owner_user_id"]},
        headers=auth_headers(admin),
    )
    assert ops_perf.status_code == 200, ops_perf.text
    assert ops_perf.json()["total_items"] >= 1

    records = session.exec(select(GradingReconciliationRecord)).all()
    assert len(records) >= 2
