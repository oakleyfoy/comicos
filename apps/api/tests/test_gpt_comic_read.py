"""GPT Comic Read — GPT vision + barcode verification (no P100 photo-import pipeline)."""

from __future__ import annotations

import io
from unittest import mock

from PIL import Image
from sqlmodel import Session, select
from fastapi.testclient import TestClient

from app.models.photo_import import (
    PhotoImportCandidate,
    PhotoImportDetectedBook,
    PhotoImportSession,
)
from test_inventory import auth_headers, register_and_login


def _png_bytes(width: int = 400, height: int = 600) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(20, 40, 80)).save(buf, format="PNG")
    return buf.getvalue()


def _enriched_payload() -> dict:
    return {
        "gpt_read": {
            "publisher": "Marvel",
            "series": "Falcon",
            "issue_number": "1",
            "issue_title": "Take Flight",
            "year": "2017",
            "cover_date": "December 2017",
            "variant_description": "",
            "barcode": "",
            "confidence": 0.92,
            "reasoning": "Cover logo and trade dress match The Falcon #1.",
            "possible_alternates": ["The Falcon (2017)"],
            "raw_response": {"parsed": {"series": "Falcon"}, "openai_response": {"id": "x"}},
            "model": "gpt-4o",
            "image_width": 400,
            "image_height": 600,
        },
        "catalog_match": {
            "matched": False,
            "catalog_issue_id": None,
            "method": "none",
            "confidence": None,
            "series": None,
            "issue_number": None,
            "publisher": None,
            "cover_image_url": None,
            "alternates": [],
        },
        "barcode_read": {
            "barcode": None,
            "barcode_type": None,
            "confidence": 0.0,
            "method": "none",
            "crop_used": None,
            "error": None,
        },
        "comicvine_barcode_match": {
            "matched": False,
            "source": "comicvine",
            "comicvine_issue_id": None,
            "series": None,
            "issue_number": None,
            "publisher": None,
            "cover_date": None,
            "name": None,
            "image_url": None,
            "raw": None,
        },
        "final_match_source": "gpt_only",
    }


def test_gpt_comic_read_returns_nested_gpt_fields(client: TestClient) -> None:
    token = register_and_login(client, "gpt-read-1@example.com")
    with mock.patch(
        "app.api.gpt_comic_read.run_gpt_comic_read_enriched",
        return_value=_enriched_payload(),
    ) as called:
        res = client.post(
            "/api/v1/gpt-comic-read",
            files={"image": ("falcon.png", _png_bytes(), "image/png")},
            headers=auth_headers(token),
        )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["gpt_read"]["publisher"] == "Marvel"
    assert body["gpt_read"]["series"] == "Falcon"
    assert body["gpt_read"]["issue_number"] == "1"
    assert body["gpt_read"]["model"] == "gpt-4o"
    assert body["barcode_read"]["method"] == "none"
    assert body["final_match_source"] == "gpt_only"
    called.assert_called_once()


def test_gpt_comic_read_response_has_no_photo_import_fields(client: TestClient) -> None:
    token = register_and_login(client, "gpt-read-2@example.com")
    with mock.patch(
        "app.api.gpt_comic_read.run_gpt_comic_read_enriched",
        return_value=_enriched_payload(),
    ):
        res = client.post(
            "/api/v1/gpt-comic-read",
            files={"image": ("falcon.png", _png_bytes(), "image/png")},
            headers=auth_headers(token),
        )
    body = res.json()
    for forbidden in (
        "candidate",
        "verification",
        "fingerprint",
        "cover_similarity",
        "inventory",
    ):
        assert forbidden not in body


def test_gpt_comic_read_creates_no_photo_import_rows(client: TestClient) -> None:
    from app.db.session import get_engine

    token = register_and_login(client, "gpt-read-3@example.com")
    with mock.patch(
        "app.api.gpt_comic_read.run_gpt_comic_read_enriched",
        return_value=_enriched_payload(),
    ):
        res = client.post(
            "/api/v1/gpt-comic-read",
            files={"image": ("falcon.png", _png_bytes(), "image/png")},
            headers=auth_headers(token),
        )
    assert res.status_code == 200
    with Session(get_engine()) as db:
        assert db.exec(select(PhotoImportSession)).first() is None
        assert db.exec(select(PhotoImportDetectedBook)).first() is None
        assert db.exec(select(PhotoImportCandidate)).first() is None


def test_gpt_comic_read_service_still_gpt_only() -> None:
    """Core GPT service takes only image bytes and never imports P100 matching/catalog code."""
    import inspect

    import app.services.gpt_comic_read_service as svc

    sig = inspect.signature(svc.read_comic_with_gpt)
    assert list(sig.parameters)[0] == "image_bytes"
    assert "session" not in sig.parameters

    import_lines = [
        line.strip()
        for line in inspect.getsource(svc).splitlines()
        if line.strip().startswith(("import ", "from "))
    ]
    blob = " ".join(import_lines).lower()
    for forbidden in ("catalog", "candidate", "fingerprint", "photo_import", "inventory", "detection"):
        assert forbidden not in blob, f"service must not import {forbidden} modules"


def test_gpt_comic_read_handles_invalid_image(client: TestClient) -> None:
    token = register_and_login(client, "gpt-read-4@example.com")
    from app.services.gpt_comic_read_service import GptComicReadImageError

    with mock.patch(
        "app.api.gpt_comic_read.run_gpt_comic_read_enriched",
        side_effect=GptComicReadImageError("Uploaded file is not a valid image"),
    ):
        res = client.post(
            "/api/v1/gpt-comic-read",
            files={"image": ("broken.png", b"not-an-image", "image/png")},
            headers=auth_headers(token),
        )
    assert res.status_code == 400
    body = res.json()
    message = body.get("detail") or body.get("error", {}).get("message", "")
    assert "valid image" in message.lower()
