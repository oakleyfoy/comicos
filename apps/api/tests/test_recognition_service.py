from __future__ import annotations

from datetime import date
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session

from app.models.asset_ledger import CoverImageFingerprint
from app.models.catalog_master import (
    CatalogImage,
    CatalogImageFingerprint,
    CatalogIssue,
    CatalogPublisher,
    CatalogSeries,
)
from app.models.external_catalog import ExternalCatalogIssue
from app.services.catalog_fingerprint_service import fingerprint_image_path
from app.services.cover_images import generate_perceptual_hash
from app.services.recognition.recognition_service import identify_comic_cover
from test_inventory import auth_headers, register_and_login


def _png_bytes(*, size: tuple[int, int] = (1600, 2400), color: tuple[int, int, int] = (28, 92, 180)) -> bytes:
    image = Image.new("RGB", size, color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _stub_ocr(monkeypatch: pytest.MonkeyPatch, raw_text: str) -> None:
    monkeypatch.setattr(
        "app.services.recognition.ocr_matcher._run_tesseract_ocr_with_test_compat",
        lambda image_path, timeout_seconds=None: raw_text,
    )


def _seed_issue(session: Session, *, issue_number: str, title: str, release_date: date, publisher: str = "DC Comics") -> ExternalCatalogIssue:
    issue = ExternalCatalogIssue(
        source_name="locg",
        title=f"{title} #{issue_number}",
        publisher=publisher,
        series_name=title,
        issue_number=issue_number,
        release_date=release_date,
        cover_image_url=f"https://example.com/{title.lower().replace(' ', '-')}-{issue_number}.jpg",
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)
    assert issue.id is not None
    return issue


def _seed_p97_catalog_issue(
    session: Session,
    tmp_path,
    image_bytes: bytes,
    *,
    catalog_issue_id: int = 6327,
    series_name: str = "Venom",
    issue_number: str = "1",
    publisher_name: str = "Marvel",
) -> CatalogIssue:
    publisher = CatalogPublisher(name=publisher_name, normalized_name=publisher_name.lower())
    session.add(publisher)
    session.flush()
    series = CatalogSeries(name=series_name, normalized_name=series_name.lower(), publisher_id=publisher.id)
    session.add(series)
    session.flush()
    issue = CatalogIssue(
        id=catalog_issue_id,
        series_id=series.id,
        publisher_id=publisher.id,
        issue_number=issue_number,
        normalized_issue_number=issue_number,
    )
    session.add(issue)
    session.flush()
    cover_path = tmp_path / f"catalog-{catalog_issue_id}.png"
    cover_path.write_bytes(image_bytes)
    image = CatalogImage(
        issue_id=issue.id,
        image_type="cover",
        download_status="ready",
        source="test",
        local_path=str(cover_path),
        source_url=f"https://example.com/{series_name.lower()}-{issue_number}.jpg",
    )
    session.add(image)
    session.flush()
    phash, dhash, ahash = fingerprint_image_path(cover_path)
    session.add(
        CatalogImageFingerprint(
            image_id=image.id,
            issue_id=issue.id,
            phash=phash,
            dhash=dhash,
            ahash=ahash,
        )
    )
    session.commit()
    session.refresh(issue)
    assert issue.id == catalog_issue_id
    return issue


def _seed_external_issue_166_noise(session: Session, *, title: str) -> None:
    session.add(
        ExternalCatalogIssue(
            source_name="locg",
            title=f"{title} #166",
            publisher="Marvel",
            series_name=title,
            issue_number="166",
            release_date=date(2018, 1, 1),
            cover_image_url="https://example.com/wrong-166.jpg",
        )
    )
    session.commit()


def test_recognition_catalog_fingerprint_verified_venom_6327(
    client: TestClient,
    session: Session,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image_bytes = _png_bytes(color=(120, 20, 40))
    _seed_p97_catalog_issue(session, tmp_path, image_bytes, catalog_issue_id=6327)
    _stub_ocr(monkeypatch, "Lov#166\nMARVEL")
    _seed_external_issue_166_noise(session, title="Back Issue")
    _seed_external_issue_166_noise(session, title="Blue Exorcist")

    token = register_and_login(client, "recognition-venom-catalog@example.com")
    response = client.post(
        "/api/v1/recognition/identify",
        headers=auth_headers(token),
        files={"image": ("venom-1.png", image_bytes, "image/png")},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["bucket"] == "VERIFIED"
    assert data["catalog_issue_id"] == 6327
    assert data["series"] == "Venom"
    assert data["issue_number"] == "1"
    assert data["publisher"] == "Marvel"
    assert data["confidence"] >= 0.95
    assert data["final_confidence"] >= 0.95
    assert data["catalog_fingerprint_score"] >= 0.95
    assert data["winning_source"] == "catalog_image_fingerprint"
    assert data["candidates"][0]["source"] == "CatalogIssue"
    assert data["candidates"][0]["source_id"] == 6327


def test_recognition_fingerprint_beats_wrong_ocr_issue_number(
    session: Session,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image_bytes = _png_bytes(color=(90, 45, 200))
    _seed_p97_catalog_issue(session, tmp_path, image_bytes, catalog_issue_id=6327)
    _stub_ocr(monkeypatch, "Lov#166\nMARVEL")
    _seed_external_issue_166_noise(session, title="Misread Series")

    result = identify_comic_cover(session, image_bytes=image_bytes, record_metrics=False)
    assert result.bucket == "VERIFIED"
    assert result.catalog_issue_id == 6327
    assert result.series == "Venom"
    assert result.issue_number == "1"
    assert result.confidence >= 0.95
    assert result.winning_source == "catalog_image_fingerprint"
    assert result.issue_match_confidence == 1.0


def test_recognition_identify_exact_match_and_candidate_endpoint(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image_bytes = _png_bytes(color=(40, 60, 150))
    _stub_ocr(monkeypatch, "BATMAN\nDC COMICS\n#497\nJUL 1993")
    _seed_issue(session, issue_number="497", title="Batman", release_date=date(1993, 7, 1))
    session.add(
        CoverImageFingerprint(
            cover_image_id=11,
            fingerprint_type="phash",
            fingerprint_value=generate_perceptual_hash(image_bytes),
            derivative_type="medium",
            image_width=1600,
            image_height=2400,
            image_sha256="11" * 32,
            extraction_version="test",
        )
    )
    session.commit()

    token = register_and_login(client, "recognition-exact@example.com")
    response = client.post(
        "/api/v1/recognition/identify",
        headers=auth_headers(token),
        files={"image": ("batman.png", image_bytes, "image/png")},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "success"
    assert data["bucket"] == "VERIFIED"
    assert data["series"] == "Batman"
    assert data["issue_number"] == "497"
    assert data["candidate_count"] >= 1
    assert data["candidates"][0]["series"] == "Batman"

    candidates = client.post(
        "/api/v1/recognition/candidates",
        headers=auth_headers(token),
        files={"image": ("batman.png", image_bytes, "image/png")},
    )
    assert candidates.status_code == 200, candidates.text
    assert candidates.json()[0]["series"] == "Batman"


def test_recognition_identify_ocr_only_match(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_ocr(monkeypatch, "BATMAN\nDC COMICS")
    _seed_issue(session, issue_number="498", title="Batman", release_date=date(1993, 8, 1))

    token = register_and_login(client, "recognition-ocr-only@example.com")
    response = client.post(
        "/api/v1/recognition/identify",
        headers=auth_headers(token),
        files={"image": ("batman-ocr.png", _png_bytes(color=(80, 80, 80)), "image/png")},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["series"] == "Batman"
    assert data["issue_number"] == "498"
    assert data["candidate_count"] >= 1
    assert data["candidates"][0]["series"] == "Batman"


def test_recognition_identify_no_match_returns_unknown(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_ocr(monkeypatch, "")
    token = register_and_login(client, "recognition-unknown@example.com")
    response = client.post(
        "/api/v1/recognition/identify",
        headers=auth_headers(token),
        files={"image": ("unknown.png", _png_bytes(color=(10, 10, 10)), "image/png")},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["bucket"] == "UNKNOWN"
    assert data["confidence"] < 0.70


def test_recognition_identify_degrades_when_ocr_engine_unavailable(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OCR engine errors must not 500 the endpoint; recognition should continue."""

    def _raise_ocr_unavailable(image_path, timeout_seconds=None):  # type: ignore[no-untyped-def]
        raise ValueError("Local Tesseract OCR engine is unavailable on this host.")

    monkeypatch.setattr(
        "app.services.recognition.ocr_matcher._run_tesseract_ocr_with_test_compat",
        _raise_ocr_unavailable,
    )
    token = register_and_login(client, "recognition-ocr-down@example.com")
    response = client.post(
        "/api/v1/recognition/identify",
        headers=auth_headers(token),
        files={"image": ("ocr-down.png", _png_bytes(color=(15, 15, 15)), "image/png")},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "success"
    assert data["bucket"] == "UNKNOWN"

