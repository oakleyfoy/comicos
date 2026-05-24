"""P34-08 deterministic scan pipeline replay (read-only + diff bookkeeping)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

import app.services.queue_routing as queue_routing_module
import app.services.scan_pipeline_replays as scan_pipeline_replays_module
from app.core.config import get_settings
from app.models import ScanQaResult
from app.services import background_jobs
from app.services import scan_qa as scan_qa_module
from test_inventory import auth_headers, register_and_login


def test_scan_pipeline_replay_create_list_start_unchanged_ingest(client: TestClient) -> None:
    token = register_and_login(client, "replay-unchanged@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={"session_type": "bulk_ingest"}, headers=hdr).json()["id"]
    assert (
        client.post(
            f"/scan-sessions/{sid}/items",
            json={"items": [{"source_filename": "a.tif"}, {"source_filename": "b.tif"}]},
            headers=hdr,
        ).status_code
        == 200
    )

    rsp = client.post("/scan-pipeline-replays", json={"scan_session_id": sid, "scopes": ["ingest"]}, headers=hdr)
    assert rsp.status_code == 201
    rid = rsp.json()["id"]
    assert rsp.json()["status"] == "pending"

    lst = client.get("/scan-pipeline-replays", headers=hdr)
    assert lst.status_code == 200
    ids = [r["id"] for r in lst.json()["items"]]
    assert rid in ids

    started = client.post(f"/scan-pipeline-replays/{rid}/start", headers=hdr)
    assert started.status_code == 200
    body = started.json()
    assert body["status"] == "completed"
    assert body["total_items"] == 2
    assert body["changed_items"] == 0
    assert body["unchanged_items"] == 2
    assert body["failed_items"] == 0
    assert body["cancelled_items"] == 0
    for item in body["items"]:
        assert item["result_state"] == "unchanged"
        assert item["diff_categories"] == []

    detail = client.get(f"/scan-pipeline-replays/{rid}", headers=hdr)
    assert detail.status_code == 200
    assert len(detail.json()["items"]) == 2


def test_scan_pipeline_replay_routing_detects_changed_vs_persist_absent(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        scan_qa_module,
        "run_scan_session_qa",
        MagicMock(side_effect=AssertionError("scan QA must not persist during replay")),
    )
    monkeypatch.setattr(
        queue_routing_module,
        "generate_scan_session_routing",
        MagicMock(side_effect=AssertionError("routing generation must not run during replay")),
    )
    monkeypatch.setattr(
        background_jobs,
        "enqueue_cover_image_ocr_for_user",
        MagicMock(side_effect=AssertionError("OCR enqueue must not run during replay")),
    )
    monkeypatch.setattr(
        background_jobs,
        "enqueue_cover_image_ocr_for_ops",
        MagicMock(side_effect=AssertionError("OCR enqueue must not run during replay")),
    )

    token = register_and_login(client, "replay-routing-diff@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={}, headers=hdr).json()["id"]
    assert (
        client.post(
            f"/scan-sessions/{sid}/items",
            json={"items": [{"source_filename": "solo.tif"}]},
            headers=hdr,
        ).status_code
        == 200
    )
    rsp = client.post("/scan-pipeline-replays", json={"scan_session_id": sid, "scopes": ["routing"]}, headers=hdr)
    assert rsp.status_code == 201
    rid = rsp.json()["id"]
    body = client.post(f"/scan-pipeline-replays/{rid}/start", headers=hdr).json()
    assert body["status"] == "completed"
    assert body["changed_items"] == 1
    assert body["unchanged_items"] == 0
    cats = body["items"][0]["diff_categories"]
    assert "routing_changed" in cats


def test_scan_pipeline_replay_qa_detects_stale_persist_vs_live(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = register_and_login(client, "replay-qa-diff@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={}, headers=hdr).json()["id"]
    app_rsp = client.post(
        f"/scan-sessions/{sid}/items",
        json={"items": [{"source_filename": "solo.tif"}]},
        headers=hdr,
    )
    assert app_rsp.status_code == 200
    item_id = app_rsp.json()["items"][0]["id"]
    assert client.post(f"/scan-sessions/{sid}/run-qa", headers=hdr).status_code == 200

    monkeypatch.setattr(
        scan_qa_module,
        "run_scan_session_qa",
        MagicMock(side_effect=AssertionError("run_scan_session_qa must not execute during replay")),
    )
    monkeypatch.setattr(
        background_jobs,
        "enqueue_cover_image_ocr_for_user",
        MagicMock(side_effect=AssertionError("no OCR enqueue during replay")),
    )

    assert (
        client.patch(
            f"/scan-sessions/{sid}/items/{item_id}",
            json={"ingest_status": "failed", "ingest_error": "boom"},
            headers=hdr,
        ).status_code
        == 200
    )

    replay = client.post("/scan-pipeline-replays", json={"scan_session_id": sid, "scopes": ["qa"]}, headers=hdr)
    assert replay.status_code == 201
    rid = replay.json()["id"]
    replay_body = client.post(f"/scan-pipeline-replays/{rid}/start", headers=hdr).json()
    assert replay_body["status"] == "completed"
    assert replay_body["changed_items"] == 1
    assert replay_body["items"][0]["result_state"] == "changed"
    assert "qa_changed" in replay_body["items"][0]["diff_categories"]


def test_scan_pipeline_replay_isolated_item_failure(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    monkeypatch.setattr(background_jobs, "enqueue_cover_image_ocr_for_user", MagicMock())
    monkeypatch.setattr(background_jobs, "enqueue_cover_image_ocr_for_ops", MagicMock())

    token = register_and_login(client, "replay-fail@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={}, headers=hdr).json()["id"]

    app = client.post(
        f"/scan-sessions/{sid}/items",
        json={
            "items": [
                {"source_filename": "one.tif"},
                {"source_filename": "two.tif"},
            ],
        },
        headers=hdr,
    )
    assert app.status_code == 200
    items_sorted = sorted(app.json()["items"], key=lambda r: int(r["sequence_index"]))
    dup_id = int(items_sorted[1]["id"])

    original_ingest = scan_pipeline_replays_module._ingest_slice
    ingest_calls_by_id: dict[int, int] = {}

    def flaky_second_only(row):
        rid = int(row.id or 0)
        ingest_calls_by_id[rid] = ingest_calls_by_id.get(rid, 0) + 1
        if rid == dup_id and ingest_calls_by_id[rid] == 2:
            raise RuntimeError("forced flake")
        return original_ingest(row)

    monkeypatch.setattr(scan_pipeline_replays_module, "_ingest_slice", flaky_second_only)

    rid = client.post("/scan-pipeline-replays", json={"scan_session_id": sid, "scopes": ["ingest"]}, headers=hdr).json()["id"]
    body = client.post(f"/scan-pipeline-replays/{rid}/start", headers=hdr).json()
    assert body["status"] == "completed_with_failures"
    states = sorted([r["result_state"] for r in body["items"]])
    assert states == ["failed", "unchanged"]


def test_scan_pipeline_replay_no_qa_rows_leak(client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(background_jobs, "enqueue_cover_image_ocr_for_user", MagicMock())
    monkeypatch.setattr(background_jobs, "enqueue_cover_image_ocr_for_ops", MagicMock())

    token = register_and_login(client, "replay-count@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={}, headers=hdr).json()["id"]
    assert (
        client.post(f"/scan-sessions/{sid}/items", json={"items": [{"source_filename": "x.tif"}]}, headers=hdr).status_code
        == 200
    )

    assert client.post(f"/scan-sessions/{sid}/run-qa", headers=hdr).status_code == 200
    before_rows = session.exec(select(ScanQaResult).where(ScanQaResult.scan_session_id == sid)).all()

    replay = client.post(
        "/scan-pipeline-replays",
        json={
            "scan_session_id": sid,
            "scopes": ["ingest", "qa", "routing", "ocr_visibility", "high_res_review"],
        },
        headers=hdr,
    )
    rid = replay.json()["id"]
    assert client.post(f"/scan-pipeline-replays/{rid}/start", headers=hdr).status_code == 200

    after_rows = session.exec(select(ScanQaResult).where(ScanQaResult.scan_session_id == sid)).all()
    assert len(after_rows) == len(before_rows)
    for b, a in zip(
        sorted(before_rows, key=lambda r: int(r.scan_session_item_id)),
        sorted(after_rows, key=lambda r: int(r.scan_session_item_id)),
        strict=True,
    ):
        assert b.updated_at == a.updated_at
        assert b.qa_classification == a.qa_classification


def test_scan_pipeline_replay_cancel_pending(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(background_jobs, "enqueue_cover_image_ocr_for_user", MagicMock())
    token = register_and_login(client, "replay-cancel-pend@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={}, headers=hdr).json()["id"]

    rsp = client.post("/scan-pipeline-replays", json={"scan_session_id": sid}, headers=hdr)
    rid = rsp.json()["id"]
    cancel = client.post(f"/scan-pipeline-replays/{rid}/cancel", headers=hdr)
    assert cancel.status_code == 200
    cancelled = cancel.json()
    assert cancelled["status"] == "cancelled"
    assert cancelled["cancellation_requested"] is True


def test_scan_pipeline_replay_start_after_completion_denied(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(background_jobs, "enqueue_cover_image_ocr_for_user", MagicMock())
    token = register_and_login(client, "replay-dupstart@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={}, headers=hdr).json()["id"]
    rsp = client.post("/scan-pipeline-replays", json={"scan_session_id": sid}, headers=hdr)
    rid = rsp.json()["id"]
    assert client.post(f"/scan-pipeline-replays/{rid}/start", headers=hdr).status_code == 200
    again = client.post(f"/scan-pipeline-replays/{rid}/start", headers=hdr)
    assert again.status_code == 400


def test_ops_lists_scan_pipeline_replay_detail(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "replay-ops-fs@example.com")
    get_settings.cache_clear()

    token = register_and_login(client, "replay-ops-fs@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={}, headers=hdr).json()["id"]
    rsp = client.post("/scan-pipeline-replays", json={"scan_session_id": sid}, headers=hdr)
    assert rsp.status_code == 201

    ops_rsp = client.get("/ops/scan-pipeline-replays", headers=hdr)
    assert ops_rsp.status_code == 200
    rows = ops_rsp.json().get("items")
    assert isinstance(rows, list) and len(rows) >= 1
    replay_id = rows[0]["id"]

    detail = client.get(f"/ops/scan-pipeline-replays/{replay_id}", headers=hdr)
    assert detail.status_code == 200
    assert detail.json()["id"] == replay_id

    monkeypatch.setenv("OPS_ADMIN_EMAILS", "")
    get_settings.cache_clear()


def test_scan_session_detail_includes_latest_replay_summary(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(background_jobs, "enqueue_cover_image_ocr_for_user", MagicMock())
    token = register_and_login(client, "replay-latest@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={}, headers=hdr).json()["id"]
    assert client.post(f"/scan-sessions/{sid}/items", json={"items": [{"source_filename": "q.tif"}]}, headers=hdr).status_code == 200

    client.post("/scan-pipeline-replays", json={"scan_session_id": sid, "scopes": ["ingest"]}, headers=hdr)

    recap = client.get(f"/scan-sessions/{sid}", headers=hdr).json().get("latest_scan_pipeline_replay")
    assert recap is not None
    assert recap["scan_session_id"] == sid


def test_scan_pipeline_replay_rerun_preserves_prior_runs(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(background_jobs, "enqueue_cover_image_ocr_for_user", MagicMock())
    token = register_and_login(client, "replay-preserve@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={}, headers=hdr).json()["id"]
    assert (
        client.post(f"/scan-sessions/{sid}/items", json={"items": [{"source_filename": "one.tif"}]}, headers=hdr).status_code
        == 200
    )

    r1 = client.post("/scan-pipeline-replays", json={"scan_session_id": sid, "scopes": ["ingest"]}, headers=hdr).json()[
        "id"
    ]
    assert client.post(f"/scan-pipeline-replays/{r1}/start", headers=hdr).status_code == 200

    r2 = client.post("/scan-pipeline-replays", json={"scan_session_id": sid, "scopes": ["ingest"]}, headers=hdr).json()[
        "id"
    ]
    assert client.post(f"/scan-pipeline-replays/{r2}/start", headers=hdr).status_code == 200
    assert r1 != r2

    lst = client.get("/scan-pipeline-replays", params={"scan_session_id": sid}, headers=hdr)
    assert lst.status_code == 200
    ids = sorted([row["id"] for row in lst.json()["items"]])
    assert ids == sorted([r1, r2])
