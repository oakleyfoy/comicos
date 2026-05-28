from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import get_settings
from test_inventory import auth_headers, register_and_login
from test_scan_defects import _png_bytes, _upload
from test_scan_historical_comparison import _prepare_visual_history_run
from test_scan_review import _review_session


def _authentication(
    client: TestClient,
    token: str,
    *,
    scan_image_id: int,
    visual_evidence_run_id: int | None = None,
    historical_comparison_run_id: int | None = None,
    review_session_id: int | None = None,
    reconciliation_run_id: int | None = None,
):
    body: dict[str, int] = {"scan_image_id": scan_image_id}
    if visual_evidence_run_id is not None:
        body["visual_evidence_run_id"] = visual_evidence_run_id
    if historical_comparison_run_id is not None:
        body["historical_comparison_run_id"] = historical_comparison_run_id
    if review_session_id is not None:
        body["review_session_id"] = review_session_id
    if reconciliation_run_id is not None:
        body["reconciliation_run_id"] = reconciliation_run_id
    return client.post("/api/v1/scan-authentication/run", headers=auth_headers(token), json=body)


def test_scan_authentication_run_is_deterministic(client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    token = register_and_login(client, "scan-auth-det@example.com")
    _prepare_visual_history_run(client, token, monkeypatch, session, body=_png_bytes(shadow=True))
    scan_image_id, visual_run_id = _prepare_visual_history_run(
        client,
        token,
        monkeypatch,
        session,
        body=_png_bytes(shadow=True, spine_stress=True, corner_wear=True),
    )
    historical = client.post(
        "/api/v1/scan-historical-comparison/run",
        headers=auth_headers(token),
        json={"scan_image_id": scan_image_id, "visual_evidence_run_id": visual_run_id},
    )
    assert historical.status_code == 201, historical.text

    first = _authentication(
        client,
        token,
        scan_image_id=scan_image_id,
        visual_evidence_run_id=visual_run_id,
        historical_comparison_run_id=historical.json()["data"]["id"],
    )
    second = _authentication(
        client,
        token,
        scan_image_id=scan_image_id,
        visual_evidence_run_id=visual_run_id,
        historical_comparison_run_id=historical.json()["data"]["id"],
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text
    assert first.json()["data"]["id"] == second.json()["data"]["id"]
    assert first.json()["data"]["authentication_checksum"] == second.json()["data"]["authentication_checksum"]


def test_scan_authentication_generates_signals_findings_and_lineage(client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    token = register_and_login(client, "scan-auth-signals@example.com")
    _prepare_visual_history_run(client, token, monkeypatch, session, body=_png_bytes(shadow=True))
    scan_image_id, visual_run_id = _prepare_visual_history_run(
        client,
        token,
        monkeypatch,
        session,
        body=_png_bytes(shadow=True, surface_defect=True, structural_damage=True),
    )
    historical = client.post(
        "/api/v1/scan-historical-comparison/run",
        headers=auth_headers(token),
        json={"scan_image_id": scan_image_id, "visual_evidence_run_id": visual_run_id},
    )
    assert historical.status_code == 201, historical.text
    response = _authentication(
        client,
        token,
        scan_image_id=scan_image_id,
        visual_evidence_run_id=visual_run_id,
        historical_comparison_run_id=historical.json()["data"]["id"],
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    signal_types = {row["signal_type"] for row in data["signals"]}
    assert "IDENTITY_CONSISTENCY" in signal_types
    assert "SCAN_LINEAGE_INTEGRITY" in signal_types
    assert "HISTORICAL_MATCH_CONSISTENCY" in signal_types
    assert data["findings"]
    assert data["artifacts"]
    assert data["original_scan_checksum"]
    assert data["visual_evidence_checksum"]
    structured = json.dumps(data, sort_keys=True).lower()
    for banned in ("counterfeit", "certified", "official grade", '"fmv"'):
        assert banned not in structured


def test_scan_authentication_handles_identity_and_metadata_conflicts(client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    token = register_and_login(client, "scan-auth-conflict@example.com")
    _prepare_visual_history_run(client, token, monkeypatch, session, body=_png_bytes(shadow=True))
    scan_image_id, visual_run_id = _prepare_visual_history_run(
        client,
        token,
        monkeypatch,
        session,
        body=_png_bytes(shadow=True, glare=True),
    )
    review = _review_session(client, token, scan_image_id=scan_image_id, visual_run_id=visual_run_id)
    assert review.status_code == 201, review.text
    review_id = review.json()["data"]["id"]
    decision = client.post(
        f"/api/v1/scan-review/sessions/{review_id}/decisions",
        headers=auth_headers(token),
        json={
            "decision_type": "IDENTITY_CONFIRMATION",
            "decision_status": "REJECTED",
            "decision_value": "MISMATCH",
            "reason_text": "Identity evidence does not align.",
            "metadata_json": {},
        },
    )
    assert decision.status_code == 200, decision.text
    response = _authentication(client, token, scan_image_id=scan_image_id, visual_evidence_run_id=visual_run_id, review_session_id=review_id)
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    issue_types = {row["issue_type"] for row in data["issues"]}
    finding_statuses = {row["finding_status"] for row in data["findings"]}
    assert "IDENTITY_CONFLICT" in issue_types
    assert "REVIEW_REQUIRED" in finding_statuses or "CONFLICT" in finding_statuses


def test_scan_authentication_handles_lineage_gaps_without_mutating_upstream_artifacts(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = register_and_login(client, "scan-auth-lineage@example.com")
    _prepare_visual_history_run(client, token, monkeypatch, session, body=_png_bytes(shadow=True))
    _, visual_run_id = _prepare_visual_history_run(
        client,
        token,
        monkeypatch,
        session,
        body=_png_bytes(shadow=True, corner_wear=True),
    )
    visual_detail = client.get(f"/api/v1/scan-visual-evidence/runs/{visual_run_id}", headers=auth_headers(token))
    assert visual_detail.status_code == 200, visual_detail.text
    settings = get_settings()
    overlay = next(row for row in visual_detail.json()["data"]["artifacts"] if row["artifact_type"] == "VISUAL_EVIDENCE_OVERLAY")
    overlay_path = settings.scan_visual_evidence_storage_root / overlay["storage_path"]
    before = overlay_path.read_bytes()

    upload = _upload(client, token, _png_bytes(shadow=True, glare=True, surface_defect=True))
    assert upload.status_code in {200, 201}, upload.text
    scan_image_id = upload.json()["data"]["images"][0]["id"]
    response = _authentication(client, token, scan_image_id=scan_image_id)
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    issue_types = {row["issue_type"] for row in data["issues"]}
    assert "LINEAGE_GAP" in issue_types
    assert "VISUAL_EVIDENCE_MISSING" in issue_types
    assert overlay_path.read_bytes() == before


def test_scan_authentication_owner_ops_scoping(client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "scan-auth-ops@example.com")
    get_settings.cache_clear()

    owner = register_and_login(client, "scan-auth-owner@example.com")
    peer = register_and_login(client, "scan-auth-peer@example.com")
    ops = register_and_login(client, "scan-auth-ops@example.com")
    scan_image_id, visual_run_id = _prepare_visual_history_run(client, owner, monkeypatch, session, body=_png_bytes(shadow=True, surface_defect=True))
    response = _authentication(client, owner, scan_image_id=scan_image_id, visual_evidence_run_id=visual_run_id)
    assert response.status_code == 201, response.text
    run_id = response.json()["data"]["id"]

    assert client.get(f"/api/v1/scan-authentication/runs/{run_id}", headers=auth_headers(peer)).status_code == 404
    ops_runs = client.get("/api/v1/ops/scan-authentication/runs", headers=auth_headers(ops))
    assert ops_runs.status_code == 200, ops_runs.text
    assert any(int(row["id"]) == int(run_id) for row in ops_runs.json()["data"]["items"])
    assert client.post("/api/v1/ops/scan-authentication/runs", headers=auth_headers(ops), json={}).status_code == 405
    get_settings.cache_clear()
