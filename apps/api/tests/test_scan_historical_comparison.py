from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from test_inventory import auth_headers, register_and_login
from test_scan_defects import _defect, _png_bytes, _prepare_pipeline


def _post_json(client: TestClient, token: str, path: str, body: dict[str, int]) -> dict:
    response = client.post(path, headers=auth_headers(token), json=body)
    assert response.status_code in {200, 201}, response.text
    return response.json()["data"]


def _prepare_visual_history_run(
    client: TestClient,
    token: str,
    monkeypatch: pytest.MonkeyPatch,
    session: Session,
    *,
    body: bytes,
) -> tuple[int, int]:
    scan_image_id, boundary_run_id, _ = _prepare_pipeline(
        client,
        token,
        monkeypatch,
        body=body,
        with_reconciliation=True,
        session=session,
    )
    _defect(client, token, scan_image_id, boundary_run_id)
    _post_json(client, token, "/api/v1/scan-spine-ticks/run", {"scan_image_id": scan_image_id})
    _post_json(client, token, "/api/v1/scan-corner-edges/run", {"scan_image_id": scan_image_id})
    _post_json(client, token, "/api/v1/scan-surface-defects/run", {"scan_image_id": scan_image_id})
    _post_json(client, token, "/api/v1/scan-structural-damage/run", {"scan_image_id": scan_image_id})
    aggregation = _post_json(client, token, "/api/v1/scan-defect-aggregation/run", {"scan_image_id": scan_image_id})
    grading = _post_json(
        client,
        token,
        "/api/v1/scan-grading-assistance/run",
        {"scan_image_id": scan_image_id, "aggregation_run_id": aggregation["id"]},
    )
    visual = _post_json(
        client,
        token,
        "/api/v1/scan-visual-evidence/run",
        {"scan_image_id": scan_image_id, "aggregation_run_id": aggregation["id"], "grading_assistance_run_id": grading["id"]},
    )
    return scan_image_id, int(visual["id"])


def test_scan_historical_comparison_run_is_deterministic(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = register_and_login(client, "scan-historical-det@example.com")
    _prepare_visual_history_run(client, token, monkeypatch, session, body=_png_bytes(shadow=True))
    scan_image_id, visual_run_id = _prepare_visual_history_run(
        client,
        token,
        monkeypatch,
        session,
        body=_png_bytes(shadow=True, spine_stress=True, corner_wear=True),
    )
    first = client.post(
        "/api/v1/scan-historical-comparison/run",
        headers=auth_headers(token),
        json={"scan_image_id": scan_image_id, "visual_evidence_run_id": visual_run_id},
    )
    second = client.post(
        "/api/v1/scan-historical-comparison/run",
        headers=auth_headers(token),
        json={"scan_image_id": scan_image_id, "visual_evidence_run_id": visual_run_id},
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text
    assert first.json()["data"]["id"] == second.json()["data"]["id"]
    assert first.json()["data"]["historical_comparison_checksum"] == second.json()["data"]["historical_comparison_checksum"]
