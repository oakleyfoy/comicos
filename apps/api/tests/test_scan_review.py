from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from test_inventory import auth_headers, register_and_login
from test_scan_defects import _png_bytes, _prepare_pipeline
from test_scan_historical_comparison import _prepare_visual_history_run


def _review_session(
    client: TestClient,
    token: str,
    *,
    scan_image_id: int,
    visual_run_id: int | None = None,
    grading_run_id: int | None = None,
    reconciliation_run_id: int | None = None,
):
    body: dict[str, int] = {"scan_image_id": scan_image_id}
    if visual_run_id is not None:
        body["visual_evidence_run_id"] = visual_run_id
    if grading_run_id is not None:
        body["grading_assistance_run_id"] = grading_run_id
    if reconciliation_run_id is not None:
        body["reconciliation_run_id"] = reconciliation_run_id
    return client.post("/api/v1/scan-review/sessions", headers=auth_headers(token), json=body)


def test_scan_review_session_can_attach_to_visual_history_context(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = register_and_login(client, "scan-review-smoke@example.com")
    scan_image_id, visual_run_id = _prepare_visual_history_run(
        client,
        token,
        monkeypatch,
        session,
        body=_png_bytes(shadow=True, surface_defect=True),
    )
    response = _review_session(client, token, scan_image_id=scan_image_id, visual_run_id=visual_run_id)
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["scan_image_id"] == scan_image_id
    assert data["visual_evidence_run_id"] == visual_run_id
