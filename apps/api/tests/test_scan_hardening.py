from __future__ import annotations

import hashlib

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import get_settings
from app.models import ScanImage
from test_inventory import auth_headers, register_and_login
from test_scan_defects import _png_bytes, _upload
from test_scan_historical_comparison import _prepare_visual_history_run
from test_scan_intelligence_feed import _feed, _prepare_feed_run
from test_scan_replay import _replay
from test_scan_review import _review_session
from test_scan_authentication import _authentication


def _assert_v1_list_envelope(response) -> dict:
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body.keys()) == {"data", "meta"}
    assert "pagination" in body["data"]
    assert "engine_versions" in body["meta"]
    return body


def _prepare_full_p40_stack(
    client: TestClient,
    token: str,
    monkeypatch: pytest.MonkeyPatch,
    session: Session,
    *,
    body: bytes,
) -> tuple[int, int, int, int, int | None]:
    scan_image_id, visual_run_id, historical_run_id, authentication_run_id = _prepare_feed_run(
        client,
        token,
        monkeypatch,
        session,
        body=body,
    )
    review_runs = client.get(f"/api/v1/scan-review/sessions?scan_image_id={scan_image_id}&limit=5&offset=0", headers=auth_headers(token))
    assert review_runs.status_code == 200, review_runs.text
    review_session_id = review_runs.json()["data"]["items"][0]["id"]
    return scan_image_id, visual_run_id, historical_run_id, authentication_run_id, review_session_id


def test_scan_p40_hardening_integrity_and_replay_stability(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = register_and_login(client, "scan-hardening-det@example.com")
    scan_image_id, visual_run_id, historical_run_id, authentication_run_id, review_session_id = _prepare_full_p40_stack(
        client,
        token,
        monkeypatch,
        session,
        body=_png_bytes(shadow=True, spine_stress=True, corner_wear=True, surface_defect=True, structural_damage=True),
    )
    settings = get_settings()
    scan_image = session.get(ScanImage, scan_image_id)
    assert scan_image is not None
    scan_path = settings.scan_ingestion_storage_root / scan_image.storage_path
    before_scan_checksum = hashlib.sha256(scan_path.read_bytes()).hexdigest()

    feed_first = _feed(
        client,
        token,
        scan_image_id=scan_image_id,
        visual_evidence_run_id=visual_run_id,
        historical_comparison_run_id=historical_run_id,
        review_session_id=review_session_id,
        authentication_run_id=authentication_run_id,
    )
    feed_second = _feed(
        client,
        token,
        scan_image_id=scan_image_id,
        visual_evidence_run_id=visual_run_id,
        historical_comparison_run_id=historical_run_id,
        review_session_id=review_session_id,
        authentication_run_id=authentication_run_id,
    )
    assert feed_first.status_code == 201, feed_first.text
    assert feed_second.status_code == 200, feed_second.text
    feed_first_data = feed_first.json()["data"]
    feed_second_data = feed_second.json()["data"]
    assert feed_first_data["id"] == feed_second_data["id"]
    assert feed_first_data["feed_checksum"] == feed_second_data["feed_checksum"]
    assert [row["timeline_rank"] for row in feed_first_data["events"]] == list(range(1, len(feed_first_data["events"]) + 1))
    assert [row["event_key"] for row in feed_first_data["events"]] == [row["event_key"] for row in feed_second_data["events"]]
    assert [row["event_type"] for row in feed_first_data["history"]] == [row["event_type"] for row in feed_second_data["history"]]
    assert feed_first_data["scan_image_id"] == scan_image_id
    assert feed_first_data["total_events"] == len(feed_first_data["events"])

    replay_first = _replay(client, token, scan_image_id=scan_image_id)
    replay_second = _replay(client, token, scan_image_id=scan_image_id)
    assert replay_first.status_code == 201, replay_first.text
    assert replay_second.status_code == 200, replay_second.text
    replay_first_data = replay_first.json()["data"]
    replay_second_data = replay_second.json()["data"]
    assert replay_first_data["id"] == replay_second_data["id"]
    assert replay_first_data["replay_checksum"] == replay_second_data["replay_checksum"]
    assert [row["phase_key"] for row in replay_first_data["steps"]] == [
        "P40_01_SCAN_INGESTION",
        "P40_02_NORMALIZATION",
        "P40_03_BOUNDARY",
        "P40_04_OCR",
        "P40_05_RECONCILIATION",
        "P40_06_DEFECT_FOUNDATION",
        "P40_07_SPINE",
        "P40_08_CORNER_EDGE",
        "P40_09_SURFACE",
        "P40_10_STRUCTURAL",
        "P40_11_AGGREGATION",
        "P40_12_GRADING_ASSISTANCE",
        "P40_13_VISUAL_EVIDENCE",
        "P40_14_REVIEW",
        "P40_15_HISTORICAL_COMPARISON",
        "P40_16_AUTHENTICATION",
        "P40_17_FEED",
    ]
    assert [row["step_rank"] for row in replay_first_data["steps"]] == list(range(1, 18))
    assert [row["discrepancy_type"] for row in replay_first_data["discrepancies"]] == [row["discrepancy_type"] for row in replay_second_data["discrepancies"]]
    assert [row["issue_type"] for row in replay_first_data["issues"]] == [row["issue_type"] for row in replay_second_data["issues"]]
    assert len(replay_first_data["lineage_chain"]) == 17
    assert [row["phase_key"] for row in replay_first_data["lineage_chain"]] == [row["phase_key"] for row in replay_first_data["steps"]]
    assert [row["id"] for row in replay_first_data["history"]] == sorted(row["id"] for row in replay_first_data["history"])

    scan_after_checksum = hashlib.sha256(scan_path.read_bytes()).hexdigest()
    assert before_scan_checksum == scan_after_checksum

    feed_detail = client.get(f"/api/v1/scan-intelligence-feed/runs/{feed_first_data['id']}", headers=auth_headers(token))
    replay_detail = client.get(f"/api/v1/scan-replay/runs/{replay_first_data['id']}", headers=auth_headers(token))
    assert feed_detail.status_code == 200, feed_detail.text
    assert replay_detail.status_code == 200, replay_detail.text
    assert feed_detail.json()["data"]["feed_checksum"] == feed_first_data["feed_checksum"]
    assert replay_detail.json()["data"]["replay_checksum"] == replay_first_data["replay_checksum"]

    feed_artifact = next(row for row in feed_first_data["artifacts"] if row["artifact_type"] == "FEED_MANIFEST")
    replay_artifact = next(row for row in replay_first_data["artifacts"] if row["artifact_type"] == "REPLAY_MANIFEST")
    feed_artifact_detail = client.get(f"/api/v1/scan-intelligence-feed/artifacts/{feed_artifact['id']}", headers=auth_headers(token))
    replay_artifact_detail = client.get(f"/api/v1/scan-replay/artifacts/{replay_artifact['id']}", headers=auth_headers(token))
    assert feed_artifact_detail.status_code == 200, feed_artifact_detail.text
    assert replay_artifact_detail.status_code == 200, replay_artifact_detail.text
    assert feed_artifact_detail.json()["data"]["artifact_checksum"] == feed_artifact["artifact_checksum"]
    assert replay_artifact_detail.json()["data"]["artifact_checksum"] == replay_artifact["artifact_checksum"]

    review_runs = client.get(f"/api/v1/scan-review/sessions?scan_image_id={scan_image_id}&limit=5&offset=0", headers=auth_headers(token))
    historical_runs = client.get(f"/api/v1/scan-historical-comparison/runs?scan_image_id={scan_image_id}&limit=5&offset=0", headers=auth_headers(token))
    authentication_runs = client.get(f"/api/v1/scan-authentication/runs?scan_image_id={scan_image_id}&limit=5&offset=0", headers=auth_headers(token))
    assert review_runs.status_code == 200, review_runs.text
    assert historical_runs.status_code == 200, historical_runs.text
    assert authentication_runs.status_code == 200, authentication_runs.text
    assert review_runs.json()["data"]["items"][0]["id"] == review_runs.json()["data"]["items"][0]["id"]
    assert historical_runs.json()["data"]["items"][0]["id"] == historical_runs.json()["data"]["items"][0]["id"]
    assert authentication_runs.json()["data"]["items"][0]["id"] == authentication_runs.json()["data"]["items"][0]["id"]

    feed_list = _assert_v1_list_envelope(client.get("/api/v1/scan-intelligence-feed/runs?limit=5&offset=0", headers=auth_headers(token)))
    replay_list = _assert_v1_list_envelope(client.get("/api/v1/scan-replay/runs?scan_image_id=%s&limit=5&offset=0" % scan_image_id, headers=auth_headers(token)))
    assert feed_list["meta"]["engine_versions"]["scan_intelligence_feed"] == "P41-17"
    assert replay_list["meta"]["engine_versions"]["scan_replay"] == "P40-18"
    assert feed_list["data"]["pagination"]["total_count"] >= 1
    assert replay_list["data"]["pagination"]["total_count"] >= 1


def test_scan_p40_hardening_owner_isolation_envelopes_and_ops_hardening(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "scan-hardening-ops@example.com")
    get_settings.cache_clear()

    owner = register_and_login(client, "scan-hardening-owner@example.com")
    peer = register_and_login(client, "scan-hardening-peer@example.com")
    ops = register_and_login(client, "scan-hardening-ops@example.com")
    scan_image_id, visual_run_id, historical_run_id, authentication_run_id, review_session_id = _prepare_full_p40_stack(
        client,
        owner,
        monkeypatch,
        session,
        body=_png_bytes(shadow=True, glare=True, surface_defect=True),
    )

    feed_run = _feed(
        client,
        owner,
        scan_image_id=scan_image_id,
        visual_evidence_run_id=visual_run_id,
        historical_comparison_run_id=historical_run_id,
        review_session_id=review_session_id,
        authentication_run_id=authentication_run_id,
    )
    replay_run = _replay(client, owner, scan_image_id=scan_image_id)
    assert feed_run.status_code in {200, 201}, feed_run.text
    assert replay_run.status_code in {200, 201}, replay_run.text
    feed_id = feed_run.json()["data"]["id"]
    replay_id = replay_run.json()["data"]["id"]

    assert client.get(f"/api/v1/scan-intelligence-feed/runs/{feed_id}", headers=auth_headers(peer)).status_code == 404
    assert client.get(f"/api/v1/scan-replay/runs/{replay_id}", headers=auth_headers(peer)).status_code == 404

    owner_feed_list = _assert_v1_list_envelope(client.get("/api/v1/scan-intelligence-feed/runs?limit=5&offset=0", headers=auth_headers(owner)))
    owner_replay_list = _assert_v1_list_envelope(client.get("/api/v1/scan-replay/runs?limit=5&offset=0", headers=auth_headers(owner)))
    owner_review_list = _assert_v1_list_envelope(
        client.get(f"/api/v1/scan-review/sessions?scan_image_id={scan_image_id}&limit=5&offset=0", headers=auth_headers(owner))
    )
    owner_historical_list = _assert_v1_list_envelope(
        client.get(f"/api/v1/scan-historical-comparison/runs?scan_image_id={scan_image_id}&limit=5&offset=0", headers=auth_headers(owner))
    )
    owner_auth_list = _assert_v1_list_envelope(
        client.get(f"/api/v1/scan-authentication/runs?scan_image_id={scan_image_id}&limit=5&offset=0", headers=auth_headers(owner))
    )
    assert owner_feed_list["data"]["items"][0]["id"] == feed_id
    assert owner_replay_list["data"]["items"][0]["id"] == replay_id
    assert owner_review_list["data"]["items"]
    assert owner_historical_list["data"]["items"]
    assert owner_auth_list["data"]["items"]

    ops_feed_list = client.get("/api/v1/ops/scan-intelligence-feed/runs?limit=5&offset=0", headers=auth_headers(ops))
    ops_replay_list = client.get("/api/v1/ops/scan-replay/runs?limit=5&offset=0", headers=auth_headers(ops))
    ops_feed_body = _assert_v1_list_envelope(ops_feed_list)
    ops_replay_body = _assert_v1_list_envelope(ops_replay_list)
    assert any(int(row["id"]) == int(feed_id) for row in ops_feed_body["data"]["items"])
    assert any(int(row["id"]) == int(replay_id) for row in ops_replay_body["data"]["items"])
    assert client.post("/api/v1/ops/scan-intelligence-feed/runs", headers=auth_headers(ops), json={}).status_code == 405
    assert client.post("/api/v1/ops/scan-replay/runs", headers=auth_headers(ops), json={}).status_code == 405

    feed_artifact = next(row for row in feed_run.json()["data"]["artifacts"] if row["artifact_type"] == "FEED_MANIFEST")
    replay_artifact = next(row for row in replay_run.json()["data"]["artifacts"] if row["artifact_type"] == "REPLAY_MANIFEST")
    assert client.get(f"/api/v1/scan-intelligence-feed/artifacts/{feed_artifact['id']}", headers=auth_headers(peer)).status_code == 404
    assert client.get(f"/api/v1/scan-replay/artifacts/{replay_artifact['id']}", headers=auth_headers(peer)).status_code == 404

    get_settings.cache_clear()
