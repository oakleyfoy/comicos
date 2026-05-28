from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import get_settings
from test_inventory import auth_headers, register_and_login
from test_scan_authentication import _authentication
from test_scan_defects import _png_bytes, _upload
from test_scan_historical_comparison import _prepare_visual_history_run
from test_scan_review import _review_session


def _feed(
    client: TestClient,
    token: str,
    *,
    scan_image_id: int,
    review_session_id: int | None = None,
    visual_evidence_run_id: int | None = None,
    historical_comparison_run_id: int | None = None,
    authentication_run_id: int | None = None,
):
    body: dict[str, int] = {"scan_image_id": scan_image_id}
    if review_session_id is not None:
        body["review_session_id"] = review_session_id
    if visual_evidence_run_id is not None:
        body["visual_evidence_run_id"] = visual_evidence_run_id
    if historical_comparison_run_id is not None:
        body["historical_comparison_run_id"] = historical_comparison_run_id
    if authentication_run_id is not None:
        body["authentication_run_id"] = authentication_run_id
    return client.post("/api/v1/scan-intelligence-feed/run", headers=auth_headers(token), json=body)


def _prepare_feed_run(
    client: TestClient,
    token: str,
    monkeypatch: pytest.MonkeyPatch,
    session: Session,
    *,
    body: bytes,
) -> tuple[int, int, int, int]:
    _prepare_visual_history_run(client, token, monkeypatch, session, body=_png_bytes(shadow=True))
    scan_image_id, visual_run_id = _prepare_visual_history_run(client, token, monkeypatch, session, body=body)
    historical = client.post(
        "/api/v1/scan-historical-comparison/run",
        headers=auth_headers(token),
        json={"scan_image_id": scan_image_id, "visual_evidence_run_id": visual_run_id},
    )
    assert historical.status_code == 201, historical.text
    review = _review_session(client, token, scan_image_id=scan_image_id, visual_run_id=visual_run_id)
    assert review.status_code == 201, review.text
    authentication = _authentication(
        client,
        token,
        scan_image_id=scan_image_id,
        visual_evidence_run_id=visual_run_id,
        historical_comparison_run_id=historical.json()["data"]["id"],
        review_session_id=review.json()["data"]["id"],
    )
    assert authentication.status_code == 201, authentication.text
    return (
        scan_image_id,
        int(visual_run_id),
        int(historical.json()["data"]["id"]),
        int(authentication.json()["data"]["id"]),
    )


def test_scan_intelligence_feed_is_deterministic_and_replay_safe(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = register_and_login(client, "scan-feed-det@example.com")
    scan_image_id, visual_run_id, historical_run_id, authentication_run_id = _prepare_feed_run(
        client,
        token,
        monkeypatch,
        session,
        body=_png_bytes(shadow=True, spine_stress=True, corner_wear=True, surface_defect=True),
    )
    review_runs = client.get(f"/api/v1/scan-review/sessions?scan_image_id={scan_image_id}&limit=5&offset=0", headers=auth_headers(token))
    assert review_runs.status_code == 200, review_runs.text
    review_session_id = review_runs.json()["data"]["items"][0]["id"]

    first = _feed(
        client,
        token,
        scan_image_id=scan_image_id,
        visual_evidence_run_id=visual_run_id,
        historical_comparison_run_id=historical_run_id,
        review_session_id=review_session_id,
        authentication_run_id=authentication_run_id,
    )
    second = _feed(
        client,
        token,
        scan_image_id=scan_image_id,
        visual_evidence_run_id=visual_run_id,
        historical_comparison_run_id=historical_run_id,
        review_session_id=review_session_id,
        authentication_run_id=authentication_run_id,
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text
    first_data = first.json()["data"]
    second_data = second.json()["data"]
    assert first_data["id"] == second_data["id"]
    assert first_data["feed_checksum"] == second_data["feed_checksum"]
    assert [row["event_key"] for row in first_data["events"]] == [row["event_key"] for row in second_data["events"]]


def test_scan_intelligence_feed_normalizes_mixed_upstream_sources_and_artifacts(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = register_and_login(client, "scan-feed-mixed@example.com")
    scan_image_id, visual_run_id, historical_run_id, authentication_run_id = _prepare_feed_run(
        client,
        token,
        monkeypatch,
        session,
        body=_png_bytes(shadow=True, surface_defect=True, structural_damage=True),
    )
    review_runs = client.get(f"/api/v1/scan-review/sessions?scan_image_id={scan_image_id}&limit=5&offset=0", headers=auth_headers(token))
    review_session_id = review_runs.json()["data"]["items"][0]["id"]
    response = _feed(
        client,
        token,
        scan_image_id=scan_image_id,
        visual_evidence_run_id=visual_run_id,
        historical_comparison_run_id=historical_run_id,
        review_session_id=review_session_id,
        authentication_run_id=authentication_run_id,
    )
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    categories = {row["event_category"] for row in data["events"]}
    assert {"INGESTION", "NORMALIZATION", "OCR", "RECONCILIATION", "VISUAL_EVIDENCE", "REVIEW", "HISTORICAL_COMPARISON", "AUTHENTICATION"} <= categories
    assert [row["timeline_rank"] for row in data["events"]] == list(range(1, len(data["events"]) + 1))
    artifact_types = {row["artifact_type"] for row in data["artifacts"]}
    assert artifact_types == {"FEED_MANIFEST", "SCAN_TIMELINE_EXPORT", "SCAN_FEED_EXPORT", "OPS_FEED_EXPORT", "FEED_DEBUG_PREVIEW"}
    manifest = next(row for row in data["artifacts"] if row["artifact_type"] == "FEED_MANIFEST")
    artifact_detail = client.get(f"/api/v1/scan-intelligence-feed/artifacts/{manifest['id']}", headers=auth_headers(token))
    assert artifact_detail.status_code == 200, artifact_detail.text
    assert '"feed_status"' in (artifact_detail.json()["data"]["text_preview"] or "")


def test_scan_intelligence_feed_owner_isolation_ops_visibility_and_lineage_gaps(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    session: Session,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "scan-feed-ops@example.com")
    get_settings.cache_clear()

    owner = register_and_login(client, "scan-feed-owner@example.com")
    peer = register_and_login(client, "scan-feed-peer@example.com")
    ops = register_and_login(client, "scan-feed-ops@example.com")
    upload = _upload(client, owner, _png_bytes(shadow=True, glare=True))
    assert upload.status_code in {200, 201}, upload.text
    scan_image_id = upload.json()["data"]["images"][0]["id"]
    created = _feed(client, owner, scan_image_id=scan_image_id)
    assert created.status_code == 201, created.text
    run_id = created.json()["data"]["id"]

    owner_detail = client.get(f"/api/v1/scan-intelligence-feed/runs/{run_id}", headers=auth_headers(owner))
    assert owner_detail.status_code == 200, owner_detail.text
    issue_types = {row["issue_type"] for row in owner_detail.json()["data"]["issues"]}
    assert "LINEAGE_GAP" in issue_types
    assert client.get(f"/api/v1/scan-intelligence-feed/runs/{run_id}", headers=auth_headers(peer)).status_code == 404

    ops_runs = client.get("/api/v1/ops/scan-intelligence-feed/runs", headers=auth_headers(ops))
    assert ops_runs.status_code == 200, ops_runs.text
    assert any(int(row["id"]) == int(run_id) for row in ops_runs.json()["data"]["items"])
    ops_failures = client.get("/api/v1/ops/scan-intelligence-feed/failures", headers=auth_headers(ops))
    assert ops_failures.status_code == 200, ops_failures.text
    assert client.post("/api/v1/ops/scan-intelligence-feed/runs", headers=auth_headers(ops), json={}).status_code == 405
    get_settings.cache_clear()
