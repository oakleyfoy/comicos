from __future__ import annotations

import io
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.core.config import get_settings
from test_inventory import auth_headers, register_and_login


def _png_bytes(
    *,
    size: tuple[int, int] = (120, 180),
    color: tuple[int, int, int] = (80, 120, 220),
    border: int = 0,
    dpi: tuple[int, int] = (300, 300),
) -> bytes:
    image = Image.new("RGB", size, (255, 255, 255) if border else color)
    if border:
        draw = ImageDraw.Draw(image)
        draw.rectangle((border, border, size[0] - border - 1, size[1] - border - 1), fill=color)
    buf = io.BytesIO()
    image.save(buf, format="PNG", dpi=dpi)
    return buf.getvalue()


def _upload(
    client: TestClient,
    token: str,
    *,
    payload: dict,
    files: list[tuple[str, bytes, str]],
):
    multipart = [("files", (name, body, mime)) for name, body, mime in files]
    return client.post(
        "/api/v1/scan-ingestion/upload",
        headers=auth_headers(token),
        data={"payload": json.dumps(payload)},
        files=multipart,
    )


def _normalize(client: TestClient, token: str, scan_image_id: int):
    return client.post(
        "/api/v1/scan-normalization/run",
        headers=auth_headers(token),
        json={"scan_image_id": scan_image_id},
    )


def test_scan_normalization_is_deterministic_and_replay_safe(client: TestClient) -> None:
    token = register_and_login(client, "scan-normalization-det@example.com")
    upload = _upload(
        client,
        token,
        payload={
            "source_type": "MANUAL_UPLOAD",
            "upload_source": "drag_drop",
            "normalized_dpi": 300,
            "create_thumbnail": True,
            "create_normalized_variant": True,
        },
        files=[("landscape.png", _png_bytes(size=(220, 140), color=(120, 80, 220), border=10), "image/png")],
    )
    assert upload.status_code == 201, upload.text
    scan_image_id = upload.json()["data"]["images"][0]["id"]

    first = _normalize(client, token, scan_image_id)
    second = _normalize(client, token, scan_image_id)
    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text

    first_data = first.json()["data"]
    second_data = second.json()["data"]
    assert first_data["id"] == second_data["id"]
    assert first_data["normalization_checksum"] == second_data["normalization_checksum"]
    assert first_data["orientation_code"] == "rotated_left"
    assert first_data["source_preview_data_url"].startswith("data:image/png;base64,")
    assert first_data["final_preview_data_url"].startswith("data:image/png;base64,")
    artifact_types = [row["artifact_type"] for row in first_data["artifacts"]]
    assert artifact_types == [
        "ROTATED",
        "CROPPED",
        "PERSPECTIVE_FIXED",
        "COLOR_NORMALIZED",
        "FINAL_NORMALIZED",
        "THUMBNAIL",
    ]

    settings = get_settings()
    final_artifact = next(row for row in first_data["artifacts"] if row["artifact_type"] == "FINAL_NORMALIZED")
    assert (settings.scan_normalization_storage_root / final_artifact["storage_path"]).exists()


def test_scan_normalization_detects_issues_and_preserves_lineage(client: TestClient) -> None:
    token = register_and_login(client, "scan-normalization-issues@example.com")
    upload = _upload(
        client,
        token,
        payload={
            "source_type": "MANUAL_UPLOAD",
            "upload_source": "drag_drop",
            "normalized_dpi": 300,
            "create_thumbnail": True,
            "create_normalized_variant": True,
        },
        files=[("low-dpi-dark.png", _png_bytes(color=(5, 5, 5), border=14, dpi=(150, 150)), "image/png")],
    )
    assert upload.status_code == 201, upload.text
    scan_image_id = upload.json()["data"]["images"][0]["id"]

    response = _normalize(client, token, scan_image_id)
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    issue_types = {row["issue_type"] for row in data["issues"]}
    assert "LOW_DPI" in issue_types
    assert any(issue in issue_types for issue in {"UNDEREXPOSED", "EXTREME_SHADOW"})
    assert data["history"][-1]["event_type"] in {"ISSUE_RECORDED", "DERIVATIVE_GENERATED"}

    issues = client.get(
        f"/api/v1/scan-normalization/issues?scan_image_id={scan_image_id}",
        headers=auth_headers(token),
    )
    assert issues.status_code == 200, issues.text
    assert issues.json()["data"]["issue_type_counts"]["LOW_DPI"] >= 1


def test_scan_normalization_owner_ops_and_failure_scoping(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "scan-normalization-ops@example.com")
    get_settings.cache_clear()

    owner_token = register_and_login(client, "scan-normalization-owner@example.com")
    peer_token = register_and_login(client, "scan-normalization-peer@example.com")
    ops_token = register_and_login(client, "scan-normalization-ops@example.com")

    upload = _upload(
        client,
        owner_token,
        payload={
            "source_type": "ZIP_IMPORT",
            "upload_source": "zip_upload",
            "normalized_dpi": 300,
            "create_thumbnail": True,
            "create_normalized_variant": True,
        },
        files=[("bad.bin", b"not-an-image", "application/octet-stream")],
    )
    assert upload.status_code == 201, upload.text
    failed_image_id = upload.json()["data"]["images"][0]["id"]

    failed_run = _normalize(client, owner_token, failed_image_id)
    assert failed_run.status_code == 200, failed_run.text
    failed_run_id = failed_run.json()["data"]["id"]
    assert failed_run.json()["data"]["normalization_status"] == "FAILED"

    forbidden = client.get(f"/api/v1/scan-normalization/runs/{failed_run_id}", headers=auth_headers(peer_token))
    assert forbidden.status_code == 404

    ops_failures = client.get("/api/v1/ops/scan-normalization/failures", headers=auth_headers(ops_token))
    assert ops_failures.status_code == 200, ops_failures.text
    assert any(int(row["id"]) == int(failed_run_id) for row in ops_failures.json()["data"]["items"])

    ops_runs = client.get("/api/v1/ops/scan-normalization/runs", headers=auth_headers(ops_token))
    assert ops_runs.status_code == 200, ops_runs.text
    assert any(int(row["id"]) == int(failed_run_id) for row in ops_runs.json()["data"]["items"])
    get_settings.cache_clear()


def test_scan_normalization_v1_envelope_shape(client: TestClient) -> None:
    token = register_and_login(client, "scan-normalization-envelope@example.com")
    response = client.get("/api/v1/scan-normalization/runs", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body.keys()) == {"data", "meta"}
    assert "pagination" in body["data"]
    assert body["meta"]["engine_versions"]["scan_normalization"] == "P40-02"
