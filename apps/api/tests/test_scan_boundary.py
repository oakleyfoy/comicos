from __future__ import annotations

import io
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.core.config import get_settings
from test_inventory import auth_headers, register_and_login


def _png_bytes(*, size: tuple[int, int] = (180, 260), border: int = 18) -> bytes:
    image = Image.new("RGB", size, (240, 240, 240))
    draw = ImageDraw.Draw(image)
    draw.rectangle((border, border, size[0] - border - 1, size[1] - border - 1), fill=(90, 120, 200))
    buf = io.BytesIO()
    image.save(buf, format="PNG", dpi=(300, 300))
    return buf.getvalue()


def _upload(client: TestClient, token: str, body: bytes):
    return client.post(
        "/api/v1/scan-ingestion/upload",
        headers=auth_headers(token),
        data={
            "payload": json.dumps(
                {
                    "source_type": "MANUAL_UPLOAD",
                    "upload_source": "drag_drop",
                    "normalized_dpi": 300,
                    "create_thumbnail": True,
                    "create_normalized_variant": True,
                }
            )
        },
        files=[("files", ("cover.png", body, "image/png"))],
    )


def _normalize(client: TestClient, token: str, scan_image_id: int):
    return client.post(
        "/api/v1/scan-normalization/run",
        headers=auth_headers(token),
        json={"scan_image_id": scan_image_id},
    )


def _boundary(client: TestClient, token: str, scan_image_id: int):
    return client.post(
        "/api/v1/scan-boundary/run",
        headers=auth_headers(token),
        json={"scan_image_id": scan_image_id},
    )


def test_scan_boundary_run_is_deterministic_and_replay_safe(client: TestClient) -> None:
    token = register_and_login(client, "scan-boundary-det@example.com")
    upload = _upload(client, token, _png_bytes())
    assert upload.status_code == 201, upload.text
    scan_image_id = upload.json()["data"]["images"][0]["id"]
    norm = _normalize(client, token, scan_image_id)
    assert norm.status_code == 201, norm.text

    first = _boundary(client, token, scan_image_id)
    second = _boundary(client, token, scan_image_id)
    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text
    first_data = first.json()["data"]
    second_data = second.json()["data"]
    assert first_data["id"] == second_data["id"]
    assert first_data["boundary_checksum"] == second_data["boundary_checksum"]
    artifact_types = sorted(row["artifact_type"] for row in first_data["artifacts"])
    assert artifact_types == [
        "BACKGROUND_MASK",
        "BOUNDARY_OVERLAY",
        "COVER_BOX_PREVIEW",
        "GEOMETRY_MANIFEST",
    ]
    assert first_data["geometry"]["cover_coverage_ratio"] > 0


def test_scan_boundary_preserves_immutable_normalized_source(client: TestClient) -> None:
    token = register_and_login(client, "scan-boundary-immutable@example.com")
    upload = _upload(client, token, _png_bytes(border=22))
    scan_image_id = upload.json()["data"]["images"][0]["id"]
    norm = _normalize(client, token, scan_image_id)
    norm_data = norm.json()["data"]
    final_artifact = next(row for row in norm_data["artifacts"] if row["artifact_type"] == "FINAL_NORMALIZED")
    settings = get_settings()
    source_path = settings.scan_normalization_storage_root / final_artifact["storage_path"]
    before = source_path.read_bytes()

    boundary = _boundary(client, token, scan_image_id)
    assert boundary.status_code == 201, boundary.text
    after = source_path.read_bytes()
    assert before == after


def test_scan_boundary_issue_detection_and_lineage(client: TestClient) -> None:
    token = register_and_login(client, "scan-boundary-issues@example.com")
    upload = _upload(client, token, _png_bytes(size=(400, 400), border=80))
    scan_image_id = upload.json()["data"]["images"][0]["id"]
    _normalize(client, token, scan_image_id)
    response = _boundary(client, token, scan_image_id)
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    issue_types = {row["issue_type"] for row in data["issues"]}
    assert "EXCESSIVE_BACKGROUND" in issue_types or "PARTIAL_COVER_VISIBLE" in issue_types
    assert data["history"][0]["event_type"] == "RUN_STARTED"
    assert data["original_scan_checksum"]
    assert data["normalized_source_checksum"]


def test_scan_boundary_owner_ops_scoping(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "scan-boundary-ops@example.com")
    get_settings.cache_clear()

    owner = register_and_login(client, "scan-boundary-owner@example.com")
    peer = register_and_login(client, "scan-boundary-peer@example.com")
    ops = register_and_login(client, "scan-boundary-ops@example.com")

    upload = _upload(client, owner, _png_bytes())
    scan_image_id = upload.json()["data"]["images"][0]["id"]
    _normalize(client, owner, scan_image_id)
    run = _boundary(client, owner, scan_image_id)
    run_id = run.json()["data"]["id"]

    assert client.get(f"/api/v1/scan-boundary/runs/{run_id}", headers=auth_headers(peer)).status_code == 404

    ops_runs = client.get("/api/v1/ops/scan-boundary/runs", headers=auth_headers(ops))
    assert ops_runs.status_code == 200, ops_runs.text
    assert any(int(row["id"]) == int(run_id) for row in ops_runs.json()["data"]["items"])

    list_runs = client.get("/api/v1/scan-boundary/runs", headers=auth_headers(owner))
    assert list_runs.status_code == 200
    ids = [row["id"] for row in list_runs.json()["data"]["items"]]
    assert ids == sorted(ids, reverse=True)
    get_settings.cache_clear()


def test_scan_boundary_v1_envelope_shape(client: TestClient) -> None:
    token = register_and_login(client, "scan-boundary-envelope@example.com")
    response = client.get("/api/v1/scan-boundary/runs", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body.keys()) == {"data", "meta"}
    assert "pagination" in body["data"]
    assert body["meta"]["engine_versions"]["scan_boundary"] == "P40-03"
