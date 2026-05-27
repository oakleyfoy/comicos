from __future__ import annotations

import io
import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import ComicIssue, ComicTitle, Publisher, Variant
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


def _reconcile(client: TestClient, token: str, scan_image_id: int, ocr_run_id: int | None = None):
    body = {"scan_image_id": scan_image_id}
    if ocr_run_id is not None:
        body["ocr_run_id"] = ocr_run_id
    return client.post("/api/v1/scan-reconciliation/run", headers=auth_headers(token), json=body)


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


def _prepare_pipeline(client: TestClient, token: str, monkeypatch: pytest.MonkeyPatch, mapping: dict[str, str]) -> tuple[int, int]:
    _stub_ocr(monkeypatch, mapping)
    upload = _upload(client, token, _png_bytes())
    assert upload.status_code == 201, upload.text
    scan_image_id = upload.json()["data"]["images"][0]["id"]
    norm = _normalize(client, token, scan_image_id)
    assert norm.status_code == 201, norm.text
    boundary = _boundary(client, token, scan_image_id)
    assert boundary.status_code == 201, boundary.text
    ocr = _ocr(client, token, scan_image_id)
    assert ocr.status_code == 201, ocr.text
    return scan_image_id, ocr.json()["data"]["id"]


def test_scan_reconciliation_run_is_deterministic_and_confirms_match(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = register_and_login(client, "scan-recon-det@example.com")
    issue_id = _seed_canonical_issue(
        session,
        publisher_name="Marvel",
        title_name="Amazing Spider-Man",
        issue_number="1",
        cover_name="Cover A",
        release_date_value=date(1973, 1, 1),
    )
    scan_image_id, ocr_run_id = _prepare_pipeline(
        client,
        token,
        monkeypatch,
        {
            "title": "AMAZ1NG SP1DER-MAN",
            "issue_number": "#1",
            "publisher": "MARVEL",
            "date": "JAN 1973",
            "generic_text": "AMAZ1NG SP1DER-MAN\n#1\nMARVEL\nJAN 1973",
        },
    )

    first = _reconcile(client, token, scan_image_id, ocr_run_id)
    second = _reconcile(client, token, scan_image_id, ocr_run_id)
    assert first.status_code == 201, first.text
    assert second.status_code == 200, second.text
    first_data = first.json()["data"]
    second_data = second.json()["data"]
    assert first_data["id"] == second_data["id"]
    assert first_data["reconciliation_checksum"] == second_data["reconciliation_checksum"]
    assert first_data["decision"]["decision_status"] == "MATCH_CONFIRMED"
    assert first_data["selected_candidate"]["canonical_comic_id"] == issue_id


def test_scan_reconciliation_candidate_ordering_and_ambiguity_are_stable(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = register_and_login(client, "scan-recon-ambiguous@example.com")
    _seed_canonical_issue(session, publisher_name="DC", title_name="Batman", issue_number="1", cover_name="Cover A", release_date_value=date(1988, 9, 1))
    _seed_canonical_issue(session, publisher_name="DC", title_name="Batman", issue_number="1", cover_name="Cover B", release_date_value=date(1988, 9, 1))
    scan_image_id, ocr_run_id = _prepare_pipeline(
        client,
        token,
        monkeypatch,
        {
            "title": "BATMAN",
            "issue_number": "#1",
            "publisher": "DC",
            "date": "SEP 1988",
            "generic_text": "BATMAN\nDC\n#1",
        },
    )

    response = _reconcile(client, token, scan_image_id, ocr_run_id)
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["decision"]["decision_status"] == "MULTIPLE_HIGH_CONFIDENCE_MATCHES"
    assert [row["candidate_rank"] for row in data["candidates"]] == sorted(row["candidate_rank"] for row in data["candidates"])
    variant_descriptions = [row["variant_description"] for row in data["candidates"][:2]]
    assert variant_descriptions == sorted(variant_descriptions)


def test_scan_reconciliation_no_match_found_is_preserved(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = register_and_login(client, "scan-recon-nomatch@example.com")
    _seed_canonical_issue(session, publisher_name="Image", title_name="Saga", issue_number="55", cover_name="Cover A", release_date_value=date(2024, 1, 1))
    scan_image_id, ocr_run_id = _prepare_pipeline(
        client,
        token,
        monkeypatch,
        {
            "title": "UNKNOWN HERO",
            "issue_number": "#777",
            "publisher": "NOWHERE",
            "generic_text": "UNKNOWN HERO\n#777",
        },
    )
    response = _reconcile(client, token, scan_image_id, ocr_run_id)
    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["decision"]["decision_status"] == "NO_MATCH_FOUND"
    issue_types = {row["issue_type"] for row in data["issues"]}
    assert "NO_MATCH_FOUND" in issue_types


def test_scan_reconciliation_preserves_immutable_upstream_artifacts(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = register_and_login(client, "scan-recon-immutable@example.com")
    _seed_canonical_issue(session, publisher_name="Marvel", title_name="X-Men", issue_number="12", cover_name="Cover A", release_date_value=date(1984, 6, 1))
    _stub_ocr(
        monkeypatch,
        {
            "title": "X-MEN",
            "issue_number": "#12",
            "publisher": "MARVEL",
            "generic_text": "X-MEN\n#12\nMARVEL",
        },
    )
    upload = _upload(client, token, _png_bytes(border=30))
    scan_image_id = upload.json()["data"]["images"][0]["id"]
    norm = _normalize(client, token, scan_image_id)
    norm_data = norm.json()["data"]
    final_artifact = next(row for row in norm_data["artifacts"] if row["artifact_type"] == "FINAL_NORMALIZED")
    settings = get_settings()
    source_path = settings.scan_normalization_storage_root / final_artifact["storage_path"]
    before = source_path.read_bytes()
    _boundary(client, token, scan_image_id)
    ocr = _ocr(client, token, scan_image_id)
    response = _reconcile(client, token, scan_image_id, ocr.json()["data"]["id"])
    assert response.status_code == 201, response.text
    after = source_path.read_bytes()
    assert before == after


def test_scan_reconciliation_owner_ops_scoping(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "scan-recon-ops@example.com")
    get_settings.cache_clear()
    _seed_canonical_issue(session, publisher_name="Image", title_name="Invincible", issue_number="1", cover_name="Cover A", release_date_value=date(2003, 1, 1))

    owner = register_and_login(client, "scan-recon-owner@example.com")
    peer = register_and_login(client, "scan-recon-peer@example.com")
    ops = register_and_login(client, "scan-recon-ops@example.com")
    scan_image_id, ocr_run_id = _prepare_pipeline(
        client,
        owner,
        monkeypatch,
        {
            "title": "INVINCIBLE",
            "issue_number": "#1",
            "publisher": "IMAGE",
            "generic_text": "INVINCIBLE\n#1\nIMAGE",
        },
    )
    run = _reconcile(client, owner, scan_image_id, ocr_run_id)
    run_id = run.json()["data"]["id"]

    assert client.get(f"/api/v1/scan-reconciliation/runs/{run_id}", headers=auth_headers(peer)).status_code == 404
    ops_runs = client.get("/api/v1/ops/scan-reconciliation/runs", headers=auth_headers(ops))
    assert ops_runs.status_code == 200, ops_runs.text
    assert any(int(row["id"]) == int(run_id) for row in ops_runs.json()["data"]["items"])
    get_settings.cache_clear()


def test_scan_reconciliation_v1_envelope_shape(client: TestClient) -> None:
    token = register_and_login(client, "scan-recon-envelope@example.com")
    response = client.get("/api/v1/scan-reconciliation/runs", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body.keys()) == {"data", "meta"}
    assert "pagination" in body["data"]
    assert body["meta"]["engine_versions"]["scan_reconciliation"] == "P40-05"
