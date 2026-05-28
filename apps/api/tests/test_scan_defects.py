from __future__ import annotations

import io
import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFilter
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import ComicIssue, ComicTitle, Publisher, Variant
from test_inventory import auth_headers, register_and_login


def _png_bytes(
    *,
    size: tuple[int, int] = (280, 400),
    border: int = 24,
    dpi: tuple[int, int] = (300, 300),
    shadow: bool = False,
    glare: bool = False,
    blur: bool = False,
    spine_stress: bool = False,
    corner_wear: bool = False,
    surface_defect: bool = False,
    structural_damage: bool = False,
) -> bytes:
    image = Image.new("RGB", size, (244, 244, 244))
    draw = ImageDraw.Draw(image)
    draw.rectangle((border, border, size[0] - border - 1, size[1] - border - 1), fill=(50, 88, 180))
    draw.rectangle((border + 12, border + 12, size[0] - border - 12, border + 54), fill=(230, 225, 110))
    if shadow:
        draw.rectangle((border, border, border + 28, size[1] - border - 1), fill=(20, 20, 28))
    if spine_stress:
        for y in (72, 148, 228, 312):
            draw.line((border + 2, y, border + 22, y), fill=(0, 0, 0), width=2)
    if corner_wear:
        b = border
        r = size[0] - border - 1
        bt = size[1] - border - 1
        draw.polygon([(b, b), (b + 14, b + 6), (b + 6, b + 14)], fill=(120, 120, 120))
        draw.polygon([(r, b), (r - 14, b + 6), (r - 6, b + 14)], fill=(120, 120, 120))
        draw.polygon([(b, bt), (b + 14, bt - 6), (b + 6, bt - 14)], fill=(120, 120, 120))
        draw.polygon([(r, bt), (r - 14, bt - 6), (r - 6, bt - 14)], fill=(120, 120, 120))
        for x in (80, 140, 200):
            draw.line((x, b, x + 10, b + 4), fill=(30, 30, 30), width=2)
        draw.line((b, 180, b + 5, 200), fill=(30, 30, 30), width=2)
    if surface_defect:
        draw.line((96, 118, 186, 142), fill=(248, 248, 248), width=3)
        draw.line((118, 238, 218, 248), fill=(28, 28, 28), width=4)
        draw.ellipse((156, 172, 220, 228), fill=(150, 128, 95))
        draw.rectangle((92, 266, 154, 308), fill=(40, 70, 120))
        draw.rectangle((174, 284, 236, 334), fill=(235, 235, 235))
    if structural_damage:
        draw.line((46, 92, 238, 122), fill=(240, 240, 240), width=5)
        draw.line((64, 212, 232, 198), fill=(24, 24, 24), width=5)
        draw.line((36, 42, 44, 356), fill=(10, 10, 10), width=3)
        draw.line((52, 78, 60, 96), fill=(8, 8, 8), width=3)
        draw.line((52, 302, 60, 322), fill=(8, 8, 8), width=3)
        draw.rectangle((228, 64, 246, 348), fill=(210, 210, 210))
    if glare:
        draw.ellipse((size[0] - 120, border + 12, size[0] - 24, border + 108), fill=(255, 255, 255))
    if blur:
        image = image.filter(ImageFilter.GaussianBlur(radius=1.8))
    buf = io.BytesIO()
    image.save(buf, format="PNG", dpi=dpi)
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


def _reconcile(client: TestClient, token: str, scan_image_id: int, ocr_run_id: int | None = None):
    body = {"scan_image_id": scan_image_id}
    if ocr_run_id is not None:
        body["ocr_run_id"] = ocr_run_id
    return client.post("/api/v1/scan-reconciliation/run", headers=auth_headers(token), json=body)


def _defect(client: TestClient, token: str, scan_image_id: int, boundary_run_id: int | None = None):
    body: dict[str, int] = {"scan_image_id": scan_image_id}
    if boundary_run_id is not None:
        body["boundary_run_id"] = boundary_run_id
    return client.post("/api/v1/scan-defects/run", headers=auth_headers(token), json=body)


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


def _seed_canonical_issue(
    session: Session,
    *,
    publisher_name: str,
    title_name: str,
    issue_number: str,
    cover_name: str | None = None,
    release_date_value: date | None = None,
) -> int:
    publisher = session.exec(select(Publisher).where(Publisher.name == publisher_name)).first()
    if publisher is None:
        publisher = Publisher(name=publisher_name)
        session.add(publisher)
        session.flush()
    title = ComicTitle(publisher_id=int(publisher.id or 0), name=title_name)
    session.add(title)
    session.flush()
    issue = ComicIssue(
        comic_title_id=int(title.id or 0),
        issue_number=issue_number,
        release_date=release_date_value,
        cover_date=release_date_value,
    )
    session.add(issue)
    session.flush()
    session.add(Variant(comic_issue_id=int(issue.id or 0), cover_name=cover_name))
    session.commit()
    return int(issue.id or 0)


def _prepare_pipeline(
    client: TestClient,
    token: str,
    monkeypatch: pytest.MonkeyPatch,
    *,
    body: bytes,
    with_reconciliation: bool,
    session: Session | None = None,
) -> tuple[int, int, int]:
    _stub_ocr(
        monkeypatch,
        {
            "title": "AMAZ1NG SP1DER-MAN",
            "issue_number": "#1",
            "publisher": "MARVEL",
            "date": "JAN 1973",
            "generic_text": "AMAZ1NG SP1DER-MAN\n#1\nMARVEL\nJAN 1973",
        },
    )
    if with_reconciliation and session is not None:
        _seed_canonical_issue(
            session,
            publisher_name="Marvel",
            title_name="Amazing Spider-Man",
            issue_number="1",
            cover_name="Cover A",
            release_date_value=date(1973, 1, 1),
        )
    upload = _upload(client, token, body)
    assert upload.status_code == 201, upload.text
    scan_image_id = upload.json()["data"]["images"][0]["id"]
    norm = _normalize(client, token, scan_image_id)
    assert norm.status_code == 201, norm.text
    boundary = _boundary(client, token, scan_image_id)
    assert boundary.status_code == 201, boundary.text
    boundary_run_id = boundary.json()["data"]["id"]
    if with_reconciliation:
        ocr = _ocr(client, token, scan_image_id)
        assert ocr.status_code == 201, ocr.text
        recon = _reconcile(client, token, scan_image_id, ocr.json()["data"]["id"])
        assert recon.status_code in {200, 201}, recon.text
    return scan_image_id, boundary_run_id, norm.json()["data"]["id"]


def test_scan_defect_run_is_deterministic_and_preserves_full_lineage(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = register_and_login(client, "scan-defect-det@example.com")
    scan_image_id, boundary_run_id, _ = _prepare_pipeline(
        client,
        token,
        monkeypatch,
        body=_png_bytes(shadow=True, glare=True),
        with_reconciliation=True,
        session=session,
    )

    first = _defect(client, token, scan_image_id, boundary_run_id)
    second = _defect(client, token, scan_image_id, boundary_run_id)
    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text
    first_data = first.json()["data"]
    second_data = second.json()["data"]
    assert first_data["id"] == second_data["id"]
    assert first_data["defect_checksum"] == second_data["defect_checksum"]
    assert first_data["ocr_checksum"] is not None
    assert first_data["reconciliation_checksum"] is not None
    artifact_types = {row["artifact_type"] for row in first_data["artifacts"]}
    assert artifact_types == {
        "DEFECT_REGION_MAP",
        "QUALITY_GATE_REPORT",
        "BASELINE_EVIDENCE_OVERLAY",
        "DEFECT_DEBUG_PREVIEW",
        "DEFECT_MANIFEST",
    }
    assert len(first_data["evidence"]) >= 4


def test_scan_defect_condition_regions_are_stable_and_ordered(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    token = register_and_login(client, "scan-defect-regions@example.com")
    scan_image_id, boundary_run_id, _ = _prepare_pipeline(
        client,
        token,
        monkeypatch,
        body=_png_bytes(),
        with_reconciliation=False,
    )

    response = _defect(client, token, scan_image_id, boundary_run_id)
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert [row["region_type"] for row in data["regions"]] == [
        "FULL_COVER",
        "SPINE_REGION",
        "TOP_EDGE",
        "BOTTOM_EDGE",
        "LEFT_EDGE",
        "RIGHT_EDGE",
        "TOP_LEFT_CORNER",
        "TOP_RIGHT_CORNER",
        "BOTTOM_LEFT_CORNER",
        "BOTTOM_RIGHT_CORNER",
        "CENTER_SURFACE",
        "TITLE_AREA",
        "PRICE_BOX_AREA",
    ]


def test_scan_defect_quality_gates_and_evidence_are_recorded(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    token = register_and_login(client, "scan-defect-quality@example.com")
    scan_image_id, boundary_run_id, _ = _prepare_pipeline(
        client,
        token,
        monkeypatch,
        body=_png_bytes(dpi=(150, 150), shadow=True, blur=True),
        with_reconciliation=False,
    )

    response = _defect(client, token, scan_image_id, boundary_run_id)
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    issue_types = {row["issue_type"] for row in data["issues"]}
    assert "LOW_DPI" in issue_types
    assert "QUALITY_GATE_FAILED" in issue_types
    assert any(row["evidence_category"] in {"EDGE_ANOMALY", "SPINE_ANOMALY", "SURFACE_ANOMALY"} for row in data["evidence"])


def test_scan_defect_preserves_immutable_normalized_source(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    token = register_and_login(client, "scan-defect-immutable@example.com")
    upload = _upload(client, token, _png_bytes(shadow=True))
    scan_image_id = upload.json()["data"]["images"][0]["id"]
    norm = _normalize(client, token, scan_image_id)
    assert norm.status_code == 201, norm.text
    boundary = _boundary(client, token, scan_image_id)
    assert boundary.status_code == 201, boundary.text
    norm_data = norm.json()["data"]
    final_artifact = next(row for row in norm_data["artifacts"] if row["artifact_type"] == "FINAL_NORMALIZED")
    settings = get_settings()
    source_path = settings.scan_normalization_storage_root / final_artifact["storage_path"]
    before = source_path.read_bytes()

    defect = _defect(client, token, scan_image_id, boundary.json()["data"]["id"])
    assert defect.status_code == 201, defect.text
    after = source_path.read_bytes()
    assert before == after


def test_scan_defect_owner_ops_scoping_and_quality_gate_ops_route(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "scan-defect-ops@example.com")
    get_settings.cache_clear()

    owner = register_and_login(client, "scan-defect-owner@example.com")
    peer = register_and_login(client, "scan-defect-peer@example.com")
    ops = register_and_login(client, "scan-defect-ops@example.com")
    scan_image_id, boundary_run_id, _ = _prepare_pipeline(
        client,
        owner,
        monkeypatch,
        body=_png_bytes(dpi=(150, 150), shadow=True),
        with_reconciliation=True,
        session=session,
    )
    run = _defect(client, owner, scan_image_id, boundary_run_id)
    assert run.status_code == 201, run.text
    run_id = run.json()["data"]["id"]

    assert client.get(f"/api/v1/scan-defects/runs/{run_id}", headers=auth_headers(peer)).status_code == 404
    ops_runs = client.get("/api/v1/ops/scan-defects/runs", headers=auth_headers(ops))
    assert ops_runs.status_code == 200, ops_runs.text
    assert any(int(row["id"]) == int(run_id) for row in ops_runs.json()["data"]["items"])
    quality_gates = client.get("/api/v1/ops/scan-defects/quality-gates", headers=auth_headers(ops))
    assert quality_gates.status_code == 200, quality_gates.text
    assert any(row["issue_type"] == "LOW_DPI" for row in quality_gates.json()["data"]["items"])
    get_settings.cache_clear()


def test_scan_defect_v1_envelope_shape(client: TestClient) -> None:
    token = register_and_login(client, "scan-defect-envelope@example.com")
    response = client.get("/api/v1/scan-defects/runs", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body.keys()) == {"data", "meta"}
    assert "pagination" in body["data"]
    assert body["meta"]["engine_versions"]["scan_defects"] == "P40-06"
