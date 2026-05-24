"""P34-04 deterministic scan QA routing surface (signals only)."""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session, select

from app.models import CoverImage, CoverImageOcrQualityAnalysis, InventoryCopy, ScanQaResult
import app.tasks.queue as tasks_queue_module
from test_inventory import auth_headers, create_order, register_and_login


def _png_bytes(rgb: tuple[int, int, int] = (10, 90, 200), *, size: tuple[int, int] = (800, 1200)) -> bytes:
    img = Image.new("RGB", size, rgb)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_scan_qa_ready_for_ocr_and_ordering_deterministic(client: TestClient) -> None:
    token = register_and_login(client, "scan-qa-ready@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={"session_type": "bulk_ingest"}, headers=hdr).json()["id"]
    h = "a" * 64

    rsp = client.post(
        f"/scan-sessions/{sid}/items",
        json={
            "items": [
                {"source_filename": "alpha.tif", "image_width": 800, "image_height": 1200, "image_sha256": h},
                {"source_filename": "beta.tif", "image_width": 800, "image_height": 1200, "image_sha256": "f" * 64},
            ],
        },
        headers=hdr,
    )
    assert rsp.status_code == 200

    qa = client.get(f"/scan-sessions/{sid}/qa", headers=hdr).json()
    assert qa["persisted_run"] is False
    assert [row["scan_session_item_id"] for row in qa["items"]] == [row["id"] for row in rsp.json()["items"]]
    for row in qa["items"]:
        assert row["qa_classification"] == "ready_for_ocr"
        assert row["routing_recommendation"] == "queue_for_ocr"


def test_scan_qa_low_resolution_from_quality_signal(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "scan-qa-lowres@example.com")
    hdr = auth_headers(token)
    create_order(client, token)
    inv_copy_id = client.get("/inventory", headers=hdr).json()["items"][0]["inventory_copy_id"]

    cov = client.post(
        f"/inventory/{inv_copy_id}/cover-images",
        headers=hdr,
        files={"file": ("low.png", _png_bytes(), "image/png")},
    )
    assert cov.status_code == 200
    cov_id = cov.json()["id"]

    from datetime import datetime, timezone

    session.add(
        CoverImageOcrQualityAnalysis(
            cover_image_id=cov_id,
            source_ocr_result_id=None,
            quality_type="low_resolution",
            deterministic_score=0.12,
            severity="critical",
            detail_json={"k": True},
            extraction_version="scan-qa-tests",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ),
    )
    session.commit()

    sid = client.post("/scan-sessions", json={"session_type": "bulk_ingest"}, headers=hdr).json()["id"]
    app = client.post(
        f"/scan-sessions/{sid}/items",
        json={
            "items": [
                {
                    "inventory_copy_id": inv_copy_id,
                    "cover_image_id": cov_id,
                    "image_width": 800,
                    "image_height": 1200,
                    "image_sha256": "e" * 64,
                    "source_filename": "tie.png",
                },
            ],
        },
        headers=hdr,
    )
    assert app.status_code == 200
    item_id = app.json()["items"][0]["id"]

    row = client.get(f"/scan-sessions/{sid}/items/{item_id}/qa", headers=hdr).json()
    assert row["qa_classification"] == "low_resolution"
    assert row["routing_recommendation"] == "request_rescan"


def test_scan_qa_corrupt_failed_ingest(client: TestClient) -> None:
    token = register_and_login(client, "scan-qa-corrupt@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={}, headers=hdr).json()["id"]
    app = client.post(
        f"/scan-sessions/{sid}/items",
        json={"items": [{"source_filename": "bad.tif"}]},
        headers=hdr,
    )
    assert app.status_code == 200
    item_id = app.json()["items"][0]["id"]
    client.post(f"/scan-sessions/{sid}/start", headers=hdr)
    patch = client.patch(
        f"/scan-sessions/{sid}/items/{item_id}",
        json={
            "ingest_status": "failed",
            "ingest_error": "cannot identify image format",
            "image_sha256": "b" * 64,
        },
        headers=hdr,
    )
    assert patch.status_code == 200
    qa = client.get(f"/scan-sessions/{sid}/qa", headers=hdr).json()
    assert qa["items"][0]["qa_classification"] == "corrupt_or_unreadable"
    assert qa["items"][0]["routing_recommendation"] == "hold_for_manual_review"


def test_scan_qa_duplicate_hash_within_session(client: TestClient) -> None:
    token = register_and_login(client, "scan-qa-dup@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={}, headers=hdr).json()["id"]
    h = "d" * 64
    app = client.post(
        f"/scan-sessions/{sid}/items",
        json={
            "items": [
                {"image_sha256": h, "source_filename": "a.png", "image_width": 10, "image_height": 10},
                {"image_sha256": h, "source_filename": "b.png", "image_width": 10, "image_height": 10},
            ],
        },
        headers=hdr,
    )
    assert app.status_code == 200
    qa = client.get(f"/scan-sessions/{sid}/qa", headers=hdr).json()
    assert qa["items"][0]["qa_classification"] == "duplicate_scan"
    assert qa["items"][1]["qa_classification"] == "duplicate_scan"
    assert {qa["items"][i]["routing_recommendation"] for i in (0, 1)} == {"no_action_needed"}


def test_scan_qa_already_processed(client: TestClient) -> None:
    token = register_and_login(client, "scan-qa-done@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={}, headers=hdr).json()["id"]
    app = client.post(
        f"/scan-sessions/{sid}/items",
        json={"items": [{"source_filename": "done.png", "image_sha256": "9" * 64}]},
        headers=hdr,
    )
    item_id = app.json()["items"][0]["id"]
    client.post(f"/scan-sessions/{sid}/start", headers=hdr)
    assert (
        client.patch(
            f"/scan-sessions/{sid}/items/{item_id}",
            json={"ingest_status": "imported"},
            headers=hdr,
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/scan-sessions/{sid}/items/{item_id}",
            json={"ingest_status": "queued_for_ocr"},
            headers=hdr,
        ).status_code
        == 200
    )
    patch = client.patch(
        f"/scan-sessions/{sid}/items/{item_id}",
        json={"ingest_status": "ocr_complete"},
        headers=hdr,
    )
    assert patch.status_code == 200

    qa = client.get(f"/scan-sessions/{sid}/qa", headers=hdr).json()
    assert qa["items"][0]["qa_classification"] == "already_processed"
    assert qa["items"][0]["routing_recommendation"] == "no_action_needed"


def test_scan_qa_high_res_review_routing_via_overall_quality(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "scan-qa-overall@example.com")
    hdr = auth_headers(token)
    create_order(client, token)
    inv_copy_id = client.get("/inventory", headers=hdr).json()["items"][0]["inventory_copy_id"]
    cov = client.post(
        f"/inventory/{inv_copy_id}/cover-images",
        headers=hdr,
        files={"file": ("overall.png", _png_bytes(size=(100, 140)), "image/png")},
    )
    cov_id = cov.json()["id"]

    from datetime import datetime, timezone

    session.add(
        CoverImageOcrQualityAnalysis(
            cover_image_id=cov_id,
            quality_type="overall_quality",
            deterministic_score=0.05,
            severity="critical",
            detail_json={},
            extraction_version="scan-qa-tests",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            source_ocr_result_id=None,
        ),
    )
    session.commit()

    sid = client.post("/scan-sessions", json={}, headers=hdr).json()["id"]
    rsp = client.post(
        f"/scan-sessions/{sid}/items",
        json={
            "items": [
                {
                    "inventory_copy_id": inv_copy_id,
                    "cover_image_id": cov_id,
                    "image_width": 100,
                    "image_height": 140,
                    "image_sha256": "5" * 64,
                },
            ],
        },
        headers=hdr,
    )
    assert rsp.status_code == 200
    qa = client.get(f"/scan-sessions/{sid}/qa", headers=hdr).json()
    assert qa["items"][0]["qa_classification"] == "needs_high_res_review"
    assert qa["items"][0]["routing_recommendation"] == "send_to_high_res_review"


def test_scan_qa_rescan_explicit_marker(client: TestClient) -> None:
    token = register_and_login(client, "scan-qa-rescan@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={}, headers=hdr).json()["id"]
    app = client.post(
        f"/scan-sessions/{sid}/items",
        json={"items": [{"source_filename": "thin.tif"}]},
        headers=hdr,
    )
    item_id = app.json()["items"][0]["id"]
    client.post(f"/scan-sessions/{sid}/start", headers=hdr)
    patch = client.patch(
        f"/scan-sessions/{sid}/items/{item_id}",
        json={
            "ingest_status": "failed",
            "ingest_error": "NEEDS_PHYSICAL_RESCAN",
            "image_sha256": "c" * 64,
            "image_width": 900,
            "image_height": 900,
        },
        headers=hdr,
    )
    assert patch.status_code == 200
    qarow = client.get(f"/scan-sessions/{sid}/qa", headers=hdr).json()["items"][0]
    assert qarow["qa_classification"] == "needs_rescan"
    assert qarow["routing_recommendation"] == "request_rescan"


def test_scan_qa_run_persists_and_ops_fleet_summary(
    monkeypatch: pytest.MonkeyPatch, client: TestClient, session: Session
) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("OPS_ADMIN_EMAILS", "scan-qa-ops-fs@example.com")
    get_settings.cache_clear()

    token = register_and_login(client, "scan-qa-persist@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={}, headers=hdr).json()["id"]
    client.post(
        f"/scan-sessions/{sid}/items",
        json={
            "items": [
                {"source_filename": "p1.png", "image_sha256": "1" * 64},
                {"source_filename": "p2.png", "image_sha256": "2" * 64},
            ],
        },
        headers=hdr,
    )

    rsp = client.post(f"/scan-sessions/{sid}/run-qa", headers=hdr)
    assert rsp.status_code == 200
    assert rsp.json()["persisted_run"] is True

    persisted = session.exec(select(ScanQaResult).where(ScanQaResult.scan_session_id == sid)).all()
    assert len(persisted) == 2

    ops_hdr = auth_headers(register_and_login(client, "scan-qa-ops-fs@example.com"))
    fleet = client.get("/ops/scan-qa/summary", headers=ops_hdr).json()
    assert fleet["totals_by_classification"]["ready_for_ocr"] >= 2

    qa_ops = client.get(f"/ops/scan-sessions/{sid}/qa", headers=ops_hdr).json()
    assert qa_ops["scan_session_id"] == sid
    assert qa_ops["items"][0]["qa_classification"] == "ready_for_ocr"


def test_run_qa_no_automatic_enqueue_or_metadata_mutation(
    monkeypatch: pytest.MonkeyPatch, client: TestClient, session: Session
) -> None:
    called: list[int] = []

    def boom(*_a, **_k):  # pragma: no cover - must not trigger
        called.append(1)
        raise AssertionError("OCR enqueue should not run during scan QA")

    monkeypatch.setattr(tasks_queue_module, "enqueue_cover_image_ocr_job", boom)
    monkeypatch.setattr(tasks_queue_module, "enqueue_cover_image_process_job", boom)

    token = register_and_login(client, "scan-qa-safe@example.com")
    hdr = auth_headers(token)
    create_order(client, token)

    rows_before = {r.id: (r.metadata_identity_key, r.order_status) for r in session.exec(select(InventoryCopy)).all()}
    cov_rows_before = session.exec(select(CoverImage)).all()

    sid = client.post("/scan-sessions", json={}, headers=hdr).json()["id"]
    client.post(
        f"/scan-sessions/{sid}/items",
        json={
            "items": [
                {"source_filename": "s1.tif", "image_sha256": "6" * 64},
                {"source_filename": "s2.tif", "image_sha256": "6" * 64},
            ],
        },
        headers=hdr,
    )
    rsp = client.post(f"/scan-sessions/{sid}/run-qa", headers=hdr)
    assert rsp.status_code == 200
    assert called == []

    rows_after = {r.id: (r.metadata_identity_key, r.order_status) for r in session.exec(select(InventoryCopy)).all()}
    assert rows_before == rows_after
    cov_rows_after = session.exec(select(CoverImage)).all()
    assert len(cov_rows_before) == len(cov_rows_after)

    qa_rows = session.exec(select(ScanQaResult).where(ScanQaResult.scan_session_id == sid)).all()
    assert len(qa_rows) >= 2


def test_inventory_scan_qa_panel_owner(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "scan-qa-inv@example.com")
    hdr = auth_headers(token)
    create_order(client, token)
    inv_copy_id = client.get("/inventory", headers=hdr).json()["items"][0]["inventory_copy_id"]
    cov = client.post(
        f"/inventory/{inv_copy_id}/cover-images",
        headers=hdr,
        files={"file": ("cov.png", _png_bytes(size=(400, 400)), "image/png")},
    )
    cid = cov.json()["id"]
    panel = client.get(f"/inventory/{inv_copy_id}/scan-qa", headers=hdr)
    assert panel.status_code == 200
    assert panel.json()["covers"][0]["cover_image_id"] == cid

