from __future__ import annotations

import hashlib

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import get_settings
from app.models import ScanImage
from test_inventory import auth_headers, register_and_login
from test_scan_defects import _png_bytes, _upload
from test_scan_intelligence_feed import _prepare_feed_run


def _replay(
    client: TestClient,
    token: str,
    *,
    scan_image_id: int | None,
    replay_scope: str = "FULL_P40_PIPELINE",
    selected_phase_key: str | None = None,
):
    body: dict[str, object] = {"replay_scope": replay_scope}
    if scan_image_id is not None:
        body["scan_image_id"] = scan_image_id
    if selected_phase_key is not None:
        body["selected_phase_key"] = selected_phase_key
    return client.post("/api/v1/scan-replay/run", headers=auth_headers(token), json=body)


def test_scan_replay_is_deterministic_and_preserves_upstream_artifacts(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = register_and_login(client, "scan-replay-det@example.com")
    scan_image_id, _, _, _ = _prepare_feed_run(
        client,
        token,
        monkeypatch,
        session,
        body=_png_bytes(shadow=True, spine_stress=True, corner_wear=True, surface_defect=True),
    )
    settings = get_settings()
    scan_image = session.get(ScanImage, scan_image_id)
    assert scan_image is not None
    scan_path = settings.scan_ingestion_storage_root / scan_image.storage_path
    before_bytes = scan_path.read_bytes()
    before_checksum = hashlib.sha256(before_bytes).hexdigest()

    first = _replay(client, token, scan_image_id=scan_image_id)
    second = _replay(client, token, scan_image_id=scan_image_id)
    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text

    first_data = first.json()["data"]
    second_data = second.json()["data"]
    assert first_data["id"] == second_data["id"]
    assert first_data["replay_checksum"] == second_data["replay_checksum"]
    assert [row["phase_key"] for row in first_data["steps"]] == [row["phase_key"] for row in second_data["steps"]]
    assert before_checksum == hashlib.sha256(scan_path.read_bytes()).hexdigest()


def test_scan_replay_records_artifacts_and_lineage_gaps(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = register_and_login(client, "scan-replay-gaps@example.com")
    scan_image_id, _, _, _ = _prepare_feed_run(
        client,
        token,
        monkeypatch,
        session,
        body=_png_bytes(shadow=True, structural_damage=True),
    )
    response = _replay(client, token, scan_image_id=scan_image_id)
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    artifact_types = {row["artifact_type"] for row in data["artifacts"]}
    assert artifact_types == {
        "REPLAY_REPORT",
        "CHECKSUM_AUDIT_EXPORT",
        "LINEAGE_AUDIT_EXPORT",
        "DISCREPANCY_REPORT",
        "REPLAY_MANIFEST",
        "REPLAY_DEBUG_PREVIEW",
    }
    manifest = next(row for row in data["artifacts"] if row["artifact_type"] == "REPLAY_MANIFEST")
    artifact_detail = client.get(f"/api/v1/scan-replay/artifacts/{manifest['id']}", headers=auth_headers(token))
    assert artifact_detail.status_code == 200, artifact_detail.text
    assert '"artifacts"' in (artifact_detail.json()["data"]["text_preview"] or "")

    gap_owner = register_and_login(client, "scan-replay-gap-owner@example.com")
    upload = _upload(client, gap_owner, _png_bytes(shadow=True, glare=True))
    assert upload.status_code in {200, 201}, upload.text
    gap_scan_image_id = upload.json()["data"]["images"][0]["id"]
    gap_response = _replay(client, gap_owner, scan_image_id=gap_scan_image_id)
    assert gap_response.status_code == 201, gap_response.text
    issue_types = {row["issue_type"] for row in gap_response.json()["data"]["issues"]}
    discrepancy_types = {row["discrepancy_type"] for row in gap_response.json()["data"]["discrepancies"]}
    assert "LINEAGE_INCOMPLETE" in issue_types
    assert "SOURCE_RECORD_MISSING" in discrepancy_types


def test_scan_replay_owner_isolation_and_ops_routes(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "scan-replay-ops@example.com")
    get_settings.cache_clear()

    owner = register_and_login(client, "scan-replay-owner@example.com")
    peer = register_and_login(client, "scan-replay-peer@example.com")
    ops = register_and_login(client, "scan-replay-ops@example.com")
    scan_image_id, _, _, _ = _prepare_feed_run(client, owner, monkeypatch, session, body=_png_bytes(shadow=True, corner_wear=True))
    created = _replay(client, owner, scan_image_id=scan_image_id)
    assert created.status_code == 201, created.text
    run_id = created.json()["data"]["id"]

    owner_detail = client.get(f"/api/v1/scan-replay/runs/{run_id}", headers=auth_headers(owner))
    assert owner_detail.status_code == 200, owner_detail.text
    assert client.get(f"/api/v1/scan-replay/runs/{run_id}", headers=auth_headers(peer)).status_code == 404

    steps = client.get(f"/api/v1/scan-replay/steps?run_id={run_id}&limit=200&offset=0", headers=auth_headers(owner))
    checks = client.get(f"/api/v1/scan-replay/checks?run_id={run_id}&limit=200&offset=0", headers=auth_headers(owner))
    assert steps.status_code == 200, steps.text
    assert checks.status_code == 200, checks.text

    ops_runs = client.get("/api/v1/ops/scan-replay/runs", headers=auth_headers(ops))
    ops_critical = client.get("/api/v1/ops/scan-replay/critical", headers=auth_headers(ops))
    assert ops_runs.status_code == 200, ops_runs.text
    assert ops_critical.status_code == 200, ops_critical.text
    assert any(int(row["id"]) == int(run_id) for row in ops_runs.json()["data"]["items"])
    assert client.post("/api/v1/ops/scan-replay/runs", headers=auth_headers(ops), json={}).status_code == 405
    get_settings.cache_clear()
