"""P34-09 scan pipeline dashboards (deterministic aggregates; read-only APIs)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import ScanPipelineReplayRun, User
from app.models.asset_ledger import utc_now
from app.services import background_jobs as background_jobs_module
from app.services.scan_pipeline_dashboard import scan_pipeline_dashboard_summary
from app.services.scan_pipeline_replays import REPLAY_ALGORITHM_VERSION
from test_inventory import auth_headers, create_order, register_and_login


def test_scan_pipeline_dashboard_no_enqueue(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    monkeypatch.setattr(background_jobs_module, "enqueue_cover_image_ocr_for_user", MagicMock())
    monkeypatch.setattr(background_jobs_module, "enqueue_cover_image_ocr_for_ops", MagicMock())
    token = register_and_login(client, "dash-noenq@example.com")
    hdr = auth_headers(token)
    client.post("/scan-sessions", json={"session_type": "bulk_ingest"}, headers=hdr)
    spy = MagicMock(side_effect=AssertionError("enqueue should not execute during dashboards"))
    monkeypatch.setattr(background_jobs_module, "enqueue_cover_image_ocr_for_user", spy)
    monkeypatch.setattr(background_jobs_module, "enqueue_cover_image_ocr_for_ops", spy)
    assert client.get("/scan-pipeline-dashboard", headers=hdr).status_code == 200
    spy.assert_not_called()


def test_owner_dashboard_sessions_table_scoped(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(background_jobs_module, "enqueue_cover_image_ocr_for_user", MagicMock())
    alice = register_and_login(client, "dash-alice-tbl@example.com")
    bob = register_and_login(client, "dash-bob-tbl@example.com")
    ah, bh = auth_headers(alice), auth_headers(bob)
    alice_sid = client.post("/scan-sessions", json={"session_type": "bulk_ingest"}, headers=ah).json()["id"]
    bob_sid = client.post("/scan-sessions", json={"session_type": "bulk_ingest"}, headers=bh).json()["id"]

    alice_dash = client.get("/scan-pipeline-dashboard", headers=ah).json()
    alice_active_ids = [r["id"] for r in alice_dash["active_sessions"]]
    assert alice_sid in alice_active_ids
    assert bob_sid not in alice_active_ids


def test_dashboard_counts_rollups(client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(background_jobs_module, "enqueue_cover_image_ocr_for_user", MagicMock())

    tok = register_and_login(client, "dash-rollups@example.com")
    hdr = auth_headers(tok)
    create_order(client, tok)
    uid_row = session.exec(select(User).where(User.email == "dash-rollups@example.com")).first()
    assert uid_row and uid_row.id

    sid = client.post("/scan-sessions", json={"session_type": "bulk_ingest", "scanner_profile": "Bench Preset"}, headers=hdr).json()[
        "id"
    ]
    client.post(
        "/scan-sessions",
        json={"session_type": "bulk_ingest", "scanner_profile": "Bench Preset"},
        headers=hdr,
    )

    h = "d" * 64
    app = client.post(
        f"/scan-sessions/{sid}/items",
        json={
            "items": [
                {"source_filename": "a.png", "image_sha256": h, "image_width": 10, "image_height": 10},
                {"source_filename": "b.png", "image_sha256": h, "image_width": 10, "image_height": 10},
            ],
        },
        headers=hdr,
    )
    assert app.status_code == 200

    res_app = client.post(
        f"/scan-sessions/{sid}/items",
        json={"items": [{"source_filename": "thin.tif"}]},
        headers=hdr,
    )
    assert res_app.status_code == 200
    res_item_id = res_app.json()["items"][0]["id"]
    client.post(f"/scan-sessions/{sid}/start", headers=hdr)
    assert (
        client.patch(
            f"/scan-sessions/{sid}/items/{res_item_id}",
            json={
                "ingest_status": "failed",
                "ingest_error": "NEEDS_PHYSICAL_RESCAN",
                "image_sha256": "e" * 64,
                "image_width": 900,
                "image_height": 900,
            },
            headers=hdr,
        ).status_code
        == 200
    )

    client.post(f"/scan-sessions/{sid}/run-qa", headers=hdr)
    assert client.post(f"/scan-sessions/{sid}/generate-routing", headers=hdr).status_code == 200

    inv_copy_id = client.get("/inventory", headers=hdr).json()["items"][0]["inventory_copy_id"]
    assert (
        client.post(
            "/high-res-review-requests",
            headers=hdr,
            json={"inventory_copy_id": inv_copy_id, "request_reason": "manual_review", "priority": "medium"},
        ).status_code
        == 200
    )

    item_fail = (
        client.post(f"/scan-sessions/{sid}/items", json={"items": [{"source_filename": "bad.tif"}]}, headers=hdr)
        .json()["items"][0]["id"]
    )
    client.post(f"/scan-sessions/{sid}/start", headers=hdr)
    client.patch(
        f"/scan-sessions/{sid}/items/{item_fail}",
        json={"ingest_status": "failed", "ingest_error": "x"},
        headers=hdr,
    )
    client.post(f"/scan-sessions/{sid}/complete", headers=hdr)

    now = utc_now()
    session.add(
        ScanPipelineReplayRun(
            scan_session_id=int(sid),
            owner_user_id=int(uid_row.id),
            replay_version=REPLAY_ALGORITHM_VERSION,
            scopes_json=["ingest"],
            cancellation_requested=False,
            status="completed",
            total_items=1,
            changed_items=2,
            unchanged_items=0,
            failed_items=0,
            cancelled_items=0,
            notes=None,
            created_at=now,
            updated_at=now,
            completed_at=now,
        ),
    )
    session.commit()

    summary = scan_pipeline_dashboard_summary(session, owner_user_id=int(uid_row.id))
    assert summary.qa_needs_rescan >= 1
    assert summary.routing_recommend_ocr >= 1
    assert summary.high_res_pending >= 1
    assert summary.sessions_completed_with_errors >= 1
    assert summary.failed_items >= 1
    assert summary.replay_runs_with_changes >= 1

    leaderboard = sorted(summary.most_used_scanner_profiles, key=lambda r: r.scan_session_count, reverse=True)
    assert leaderboard[0].profile_label == "Bench Preset"
    assert leaderboard[0].scan_session_count >= 2


def test_ops_scan_pipeline_dashboard_fleet(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(background_jobs_module, "enqueue_cover_image_ocr_for_user", MagicMock())
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "dash-ops-fs@example.com")
    get_settings.cache_clear()

    alice = register_and_login(client, "dash-ops-fs@example.com")

    alice_hdr = auth_headers(alice)
    client.post("/scan-sessions", json={"session_type": "bulk_ingest"}, headers=alice_hdr)
    rsp = client.get("/ops/scan-pipeline-dashboard/summary", headers=alice_hdr)
    assert rsp.status_code == 200
    fleet = rsp.json()
    assert fleet["active_sessions"] >= 1

    monkeypatch.setenv("OPS_ADMIN_EMAILS", "")
    get_settings.cache_clear()
