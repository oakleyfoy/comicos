from __future__ import annotations

import io
import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import get_settings
from test_inventory import auth_headers, register_and_login


def _png_bytes(color: tuple[int, int, int], *, dpi: tuple[int, int] = (300, 300)) -> bytes:
    image = Image.new("RGB", (120, 180), color)
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


def test_scan_ingestion_registration_is_deterministic_and_replay_safe(client: TestClient) -> None:
    token = register_and_login(client, "scan-ingest-det@example.com")
    payload = {
        "source_type": "MANUAL_UPLOAD",
        "upload_source": "drag_drop",
        "normalized_dpi": 300,
        "create_thumbnail": True,
        "create_normalized_variant": True,
    }
    first = _upload(
        client,
        token,
        payload=payload,
        files=[
            ("b.png", _png_bytes((0, 255, 0)), "image/png"),
            ("a.png", _png_bytes((255, 0, 0)), "image/png"),
        ],
    )
    assert first.status_code == 201, first.text
    second = _upload(
        client,
        token,
        payload=payload,
        files=[
            ("a.png", _png_bytes((255, 0, 0)), "image/png"),
            ("b.png", _png_bytes((0, 255, 0)), "image/png"),
        ],
    )
    assert second.status_code == 200, second.text

    first_body = first.json()["data"]
    second_body = second.json()["data"]
    assert first_body["id"] == second_body["id"]
    assert first_body["ingestion_checksum"] == second_body["ingestion_checksum"]
    assert [row["original_filename"] for row in first_body["images"]] == ["a.png", "b.png"]

    batches = client.get("/api/v1/scan-ingestion/batches", headers=auth_headers(token))
    assert batches.status_code == 200, batches.text
    assert batches.json()["data"]["items"][0]["id"] == first_body["id"]


def test_scan_ingestion_detects_duplicates_and_preserves_original_bytes(client: TestClient) -> None:
    token = register_and_login(client, "scan-ingest-dup@example.com")
    body = _png_bytes((24, 100, 220))
    resp = _upload(
        client,
        token,
        payload={
            "source_type": "MANUAL_UPLOAD",
            "upload_source": "drag_drop",
            "normalized_dpi": 300,
            "create_thumbnail": True,
            "create_normalized_variant": True,
        },
        files=[("dup-a.png", body, "image/png"), ("dup-b.png", body, "image/png")],
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["duplicate_count"] == 1
    assert data["images"][1]["is_duplicate"] is True
    assert data["images"][1]["duplicate_of_scan_image_id"] == data["images"][0]["id"]

    settings = get_settings()
    original_path = settings.scan_ingestion_storage_root / data["images"][0]["storage_path"]
    assert original_path.read_bytes() == body

    detail = client.get(f"/api/v1/scan-images/{data['images'][0]['id']}", headers=auth_headers(token))
    assert detail.status_code == 200, detail.text
    variant_types = {row["variant_type"] for row in detail.json()["data"]["variants"]}
    assert {"normalized_image", "thumbnail"} <= variant_types


def test_scan_ingestion_ops_and_owner_scoping(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "scan-ingest-ops@example.com")
    get_settings.cache_clear()

    owner_token = register_and_login(client, "scan-ingest-owner@example.com")
    peer_token = register_and_login(client, "scan-ingest-peer@example.com")
    ops_token = register_and_login(client, "scan-ingest-ops@example.com")

    resp = _upload(
        client,
        owner_token,
        payload={
            "source_type": "ZIP_IMPORT",
            "upload_source": "zip_upload",
            "normalized_dpi": 300,
            "create_thumbnail": True,
            "create_normalized_variant": True,
        },
        files=[
            ("good.png", _png_bytes((120, 20, 20)), "image/png"),
            ("bad.bin", b"not-an-image", "application/octet-stream"),
        ],
    )
    assert resp.status_code == 201, resp.text
    batch = resp.json()["data"]
    failed_image_id = next(row["id"] for row in batch["images"] if row["processing_status"] == "FAILED")

    forbidden = client.get(f"/api/v1/scan-ingestion/batches/{batch['id']}", headers=auth_headers(peer_token))
    assert forbidden.status_code == 404

    ops_batches = client.get("/api/v1/ops/scan-ingestion/batches", headers=auth_headers(ops_token))
    assert ops_batches.status_code == 200, ops_batches.text
    assert any(int(row["id"]) == int(batch["id"]) for row in ops_batches.json()["data"]["items"])

    ops_failures = client.get("/api/v1/ops/scan-ingestion/failures", headers=auth_headers(ops_token))
    assert ops_failures.status_code == 200, ops_failures.text
    assert any(int(row["id"]) == int(failed_image_id) for row in ops_failures.json()["data"]["items"])

    owner_image = client.get(f"/api/v1/scan-images/{failed_image_id}", headers=auth_headers(owner_token))
    assert owner_image.status_code == 200, owner_image.text
    get_settings.cache_clear()


def test_scan_ingestion_v1_envelope_shape(client: TestClient) -> None:
    token = register_and_login(client, "scan-ingest-envelope@example.com")
    response = client.get("/api/v1/scan-ingestion/batches", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body.keys()) == {"data", "meta"}
    assert "pagination" in body["data"]
    assert body["meta"]["engine_versions"]["scan_ingestion"] == "P40-01"
