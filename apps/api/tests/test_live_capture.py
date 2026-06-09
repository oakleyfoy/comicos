from __future__ import annotations

from datetime import date
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from test_inventory import auth_headers, register_and_login


def _png_bytes(color: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", (1200, 1800), color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _stub_recognition(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.recognition.recognition_models import RecognitionCandidateRead, RecognitionIdentifyRead

    def fake_identify(session, *, image_bytes: bytes, source_name: str = "upload"):
        return RecognitionIdentifyRead(
            status="success",
            bucket="VERIFIED",
            confidence=0.98,
            series="Batman",
            issue_number="497",
            variant="Cover A",
            publisher="DC",
            release_date=date(1993, 7, 1),
            cover_image_url="https://example.com/batman.jpg",
            candidate_count=1,
            candidates=[
                RecognitionCandidateRead(
                    series="Batman",
                    issue_number="497",
                    variant="Cover A",
                    publisher="DC",
                    release_date=date(1993, 7, 1),
                    confidence=0.98,
                    cover_image_url="https://example.com/batman.jpg",
                    source="ExternalCatalogIssue",
                    source_id=1,
                )
            ],
            metrics={},
        )

    monkeypatch.setattr("app.services.receiving.receiving_service.identify_comic_cover_read", fake_identify)


def test_live_capture_uploads_track_source_and_suppress_duplicates(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_recognition(monkeypatch)
    token = register_and_login(client, "live-capture@example.com")
    headers = auth_headers(token)

    created = client.post(
        "/api/v1/receiving/session",
        headers=headers,
        json={"capture_source": "WEBCAM", "notes": "Live capture"},
    )
    assert created.status_code == 200, created.text
    session_id = created.json()["id"]
    assert created.json()["capture_source"] == "WEBCAM"

    first = client.post(
        f"/api/v1/receiving/session/{session_id}/upload",
        headers=headers,
        data={"capture_source": "WEBCAM", "frame_fingerprint": "stable-fingerprint", "stable_frame_count": "3"},
        files=[("images", ("frame.png", _png_bytes((10, 20, 30)), "image/png"))],
    )
    assert first.status_code == 200, first.text
    assert first.json()["uploaded_count"] == 1
    item = first.json()["session"]["items"][0]
    assert item["capture_source"] == "WEBCAM"
    assert item["frame_fingerprint"] == "stable-fingerprint"
    assert item["stable_frame_count"] == 3

    second = client.post(
        f"/api/v1/receiving/session/{session_id}/upload",
        headers=headers,
        data={"capture_source": "WEBCAM", "frame_fingerprint": "stable-fingerprint", "stable_frame_count": "3"},
        files=[("images", ("frame.png", _png_bytes((10, 20, 30)), "image/png"))],
    )
    assert second.status_code == 200, second.text
    assert second.json()["uploaded_count"] == 0
    assert len(second.json()["session"]["items"]) == 1

