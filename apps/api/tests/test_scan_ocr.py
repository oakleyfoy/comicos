from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.core.config import get_settings
from test_inventory import auth_headers, register_and_login


def _png_bytes(*, size: tuple[int, int] = (260, 380), border: int = 26) -> bytes:
    image = Image.new("RGB", size, (244, 244, 244))
    draw = ImageDraw.Draw(image)
    draw.rectangle((border, border, size[0] - border - 1, size[1] - border - 1), fill=(60, 90, 180))
    draw.rectangle((border + 12, border + 12, size[0] - border - 12, border + 56), fill=(230, 225, 110))
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
    return client.post("/api/v1/scan-normalization/run", headers=auth_headers(token), json={"scan_image_id": scan_image_id})


def _boundary(client: TestClient, token: str, scan_image_id: int):
    return client.post("/api/v1/scan-boundary/run", headers=auth_headers(token), json={"scan_image_id": scan_image_id})


def _ocr(client: TestClient, token: str, scan_image_id: int):
    return client.post("/api/v1/scan-ocr/run", headers=auth_headers(token), json={"scan_image_id": scan_image_id})


def _stub_ocr(monkeypatch: pytest.MonkeyPatch, mapping: dict[str, str]) -> None:
    def fake_tesseract(image_path: Path, *, timeout_seconds: float | None = None) -> str:
        del timeout_seconds
        name = image_path.name.lower()
        for key, value in mapping.items():
            if key in name:
                return value
        return ""

    monkeypatch.setattr("app.services.scan_ocr._run_tesseract_ocr_with_test_compat", fake_tesseract)
    monkeypatch.setattr("app.services.scan_ocr.get_tesseract_engine_version", lambda: "tesseract-test-5.4")


def _prepare_scan_pipeline(client: TestClient, token: str) -> int:
    upload = _upload(client, token, _png_bytes())
    assert upload.status_code == 201, upload.text
    scan_image_id = upload.json()["data"]["images"][0]["id"]
    norm = _normalize(client, token, scan_image_id)
    assert norm.status_code == 201, norm.text
    boundary = _boundary(client, token, scan_image_id)
    assert boundary.status_code == 201, boundary.text
    return scan_image_id


def test_scan_ocr_run_is_deterministic_and_replay_safe(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    token = register_and_login(client, "scan-ocr-det@example.com")
    _stub_ocr(
        monkeypatch,
        {
            "title": "AMAZ1NG SP1DER-MAN",
            "issue_number": "#1",
            "publisher": "MARVEL",
            "date": "JAN 1973",
            "price_box": "$0.20",
            "logo": "MARVEL",
            "generic_text": "AMAZ1NG SP1DER-MAN\nMARVEL\n#1\nJAN 1973\n$0.20",
        },
    )
    scan_image_id = _prepare_scan_pipeline(client, token)

    first = _ocr(client, token, scan_image_id)
    second = _ocr(client, token, scan_image_id)
    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text

    first_data = first.json()["data"]
    second_data = second.json()["data"]
    assert first_data["id"] == second_data["id"]
    assert first_data["ocr_checksum"] == second_data["ocr_checksum"]
    assert sorted(row["artifact_type"] for row in first_data["artifacts"]) == [
        "OCR_DEBUG_PREVIEW",
        "OCR_MANIFEST",
        "OCR_OVERLAY",
        "OCR_REGION_MAP",
        "OCR_TEXT_EXPORT",
    ]
    title_candidates = [row for row in first_data["candidates"] if row["candidate_type"] == "TITLE"]
    assert title_candidates
    assert title_candidates[0]["normalized_candidate_value"] == "Amazing Spider-Man"
    assert first_data["boundary_checksum"]
    assert first_data["normalization_checksum"]


def test_scan_ocr_preserves_immutable_normalized_source(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    token = register_and_login(client, "scan-ocr-immutable@example.com")
    _stub_ocr(monkeypatch, {"generic_text": "GENERIC"})
    upload = _upload(client, token, _png_bytes(border=30))
    scan_image_id = upload.json()["data"]["images"][0]["id"]
    norm = _normalize(client, token, scan_image_id)
    norm_data = norm.json()["data"]
    final_artifact = next(row for row in norm_data["artifacts"] if row["artifact_type"] == "FINAL_NORMALIZED")
    settings = get_settings()
    source_path = settings.scan_normalization_storage_root / final_artifact["storage_path"]
    before = source_path.read_bytes()

    _boundary(client, token, scan_image_id)
    response = _ocr(client, token, scan_image_id)
    assert response.status_code == 201, response.text
    after = source_path.read_bytes()
    assert before == after


def test_scan_ocr_candidate_generation_and_issue_detection(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    token = register_and_login(client, "scan-ocr-candidates@example.com")
    _stub_ocr(
        monkeypatch,
        {
            "title": "BATMAN",
            "issue_number": "#12",
            "publisher": "DC COMICS",
            "date": "SEP 1988",
            "price_box": "$1.25",
            "generic_text": "BATMAN\nDC COMICS\n#12\nSEP 1988\n$1.25",
        },
    )
    scan_image_id = _prepare_scan_pipeline(client, token)
    response = _ocr(client, token, scan_image_id)
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    by_type = {row["candidate_type"] for row in data["candidates"]}
    assert {"TITLE", "ISSUE_NUMBER", "PUBLISHER", "DATE", "PRICE"}.issubset(by_type)
    assert data["confidence_summary"]["candidate_count"] >= 5
    assert data["history"][0]["event_type"] == "RUN_STARTED"


def test_scan_ocr_missing_text_surfaces_deterministic_issues(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    token = register_and_login(client, "scan-ocr-issues@example.com")
    _stub_ocr(monkeypatch, {"generic_text": ""})
    scan_image_id = _prepare_scan_pipeline(client, token)
    response = _ocr(client, token, scan_image_id)
    assert response.status_code == 201, response.text
    issue_types = {row["issue_type"] for row in response.json()["data"]["issues"]}
    assert "NO_TITLE_DETECTED" in issue_types
    assert "NO_ISSUE_NUMBER_DETECTED" in issue_types


def test_scan_ocr_owner_ops_scoping(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "scan-ocr-ops@example.com")
    get_settings.cache_clear()
    _stub_ocr(monkeypatch, {"generic_text": "SCOPED OCR"})

    owner = register_and_login(client, "scan-ocr-owner@example.com")
    peer = register_and_login(client, "scan-ocr-peer@example.com")
    ops = register_and_login(client, "scan-ocr-ops@example.com")

    scan_image_id = _prepare_scan_pipeline(client, owner)
    run = _ocr(client, owner, scan_image_id)
    run_id = run.json()["data"]["id"]

    assert client.get(f"/api/v1/scan-ocr/runs/{run_id}", headers=auth_headers(peer)).status_code == 404

    ops_runs = client.get("/api/v1/ops/scan-ocr/runs", headers=auth_headers(ops))
    assert ops_runs.status_code == 200, ops_runs.text
    assert any(int(row["id"]) == int(run_id) for row in ops_runs.json()["data"]["items"])

    list_runs = client.get("/api/v1/scan-ocr/runs", headers=auth_headers(owner))
    assert list_runs.status_code == 200
    ids = [row["id"] for row in list_runs.json()["data"]["items"]]
    assert ids == sorted(ids, reverse=True)
    get_settings.cache_clear()


def test_scan_ocr_v1_envelope_shape(client: TestClient) -> None:
    token = register_and_login(client, "scan-ocr-envelope@example.com")
    response = client.get("/api/v1/scan-ocr/runs", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body.keys()) == {"data", "meta"}
    assert "pagination" in body["data"]
    assert body["meta"]["engine_versions"]["scan_ocr"] == "P40-04"
