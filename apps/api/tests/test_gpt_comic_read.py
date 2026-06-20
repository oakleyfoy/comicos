"""GPT Comic Read — clean standalone GPT vision flow (no P100 pipeline)."""

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
from app.services.gpt_comic_read_service import GptComicReadResult
from test_inventory import auth_headers, register_and_login


def _png_bytes(width: int = 400, height: int = 600) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(20, 40, 80)).save(buf, format="PNG")
    return buf.getvalue()


def _fake_result() -> GptComicReadResult:
    return GptComicReadResult(
        publisher="Marvel",
        series="Falcon",
        issue_number="1",
        issue_title="Take Flight",
        year="2017",
        cover_date="December 2017",
        variant_description="",
        barcode="",
        confidence=0.92,
        reasoning="Cover logo and trade dress match The Falcon #1.",
        model="gpt-4o",
        image_width=400,
        image_height=600,
        raw_response={"parsed": {"series": "Falcon"}, "openai_response": {"id": "x"}},
        possible_alternates=["The Falcon (2017)"],
    )


def test_gpt_comic_read_returns_gpt_fields(client: TestClient) -> None:
    token = register_and_login(client, "gpt-read-1@example.com")
    with mock.patch(
        "app.api.gpt_comic_read.read_comic_with_gpt",
        return_value=_fake_result(),
    ) as called:
        res = client.post(
            "/api/v1/gpt-comic-read",
            files={"image": ("falcon.png", _png_bytes(), "image/png")},
            headers=auth_headers(token),
        )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["publisher"] == "Marvel"
    assert body["series"] == "Falcon"
    assert body["issue_number"] == "1"
    assert body["reasoning"]
    assert body["model"] == "gpt-4o"
    assert body["image_width"] == 400
    assert body["image_height"] == 600
    assert body["possible_alternates"] == ["The Falcon (2017)"]
    assert body["raw_response"]["parsed"]["series"] == "Falcon"
    called.assert_called_once()


def test_gpt_comic_read_response_has_no_catalog_fields(client: TestClient) -> None:
    token = register_and_login(client, "gpt-read-2@example.com")
    with mock.patch(
        "app.api.gpt_comic_read.read_comic_with_gpt",
        return_value=_fake_result(),
    ):
        res = client.post(
            "/api/v1/gpt-comic-read",
            files={"image": ("falcon.png", _png_bytes(), "image/png")},
            headers=auth_headers(token),
        )
    body = res.json()
    for forbidden in (
        "catalog_issue_id",
        "candidate",
        "match_score",
        "selected_issue",
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
        "app.api.gpt_comic_read.read_comic_with_gpt",
        return_value=_fake_result(),
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


def test_gpt_comic_read_does_not_touch_catalog_or_db() -> None:
    """The service takes only image bytes and never imports P100 matching/catalog code."""
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
    res = client.post(
        "/api/v1/gpt-comic-read",
        files={"image": ("broken.png", b"not-an-image", "image/png")},
        headers=auth_headers(token),
    )
    assert res.status_code == 400
    body = res.json()
    message = body.get("detail") or body.get("error", {}).get("message", "")
    assert "valid image" in message.lower()


def test_gpt_comic_read_returns_raw_response(client: TestClient) -> None:
    token = register_and_login(client, "gpt-read-5@example.com")
    with mock.patch(
        "app.api.gpt_comic_read.read_comic_with_gpt",
        return_value=_fake_result(),
    ):
        res = client.post(
            "/api/v1/gpt-comic-read",
            files={"image": ("falcon.png", _png_bytes(), "image/png")},
            headers=auth_headers(token),
        )
    assert res.status_code == 200
    assert "raw_response" in res.json()
    assert res.json()["raw_response"]["openai_response"]["id"] == "x"
