from __future__ import annotations

from datetime import date
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.services.recognition.recognition_models import RecognitionCandidateRead, RecognitionIdentifyRead
from test_inventory import auth_headers, register_and_login


def _png_bytes(color: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", (1600, 2400), color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _recognition(
    bucket: str,
    confidence: float,
    *,
    issue_number: str,
    score: float | None = None,
) -> RecognitionIdentifyRead:
    candidate = RecognitionCandidateRead(
        series="Batman",
        issue_number=issue_number,
        variant="Cover A",
        publisher="DC",
        release_date=date(1993, 7, 1),
        confidence=score if score is not None else confidence,
        cover_image_url="https://example.com/batman.jpg",
        source="ExternalCatalogIssue",
        source_id=1,
    )
    return RecognitionIdentifyRead(
        status="success",
        bucket=bucket,  # type: ignore[arg-type]
        confidence=confidence,
        series="Batman",
        issue_number=issue_number,
        variant="Cover A",
        publisher="DC",
        release_date=date(1993, 7, 1),
        cover_image_url="https://example.com/batman.jpg",
        candidate_count=1,
        candidates=[candidate],
        metrics={},
    )


def test_receiving_queue_assignment_and_history_order(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = {
        "verified.png": _recognition("VERIFIED", 0.98, issue_number="497"),
        "review.png": _recognition("REVIEW", 0.83, issue_number="498"),
        "unknown.png": _recognition("UNKNOWN", 0.44, issue_number=""),
    }

    def fake_identify(session, *, image_bytes: bytes, source_name: str = "upload"):
        return responses[source_name]

    monkeypatch.setattr("app.services.receiving.receiving_service.identify_comic_cover_read", fake_identify)

    token = register_and_login(client, "receiving-workflow@example.com")
    headers = auth_headers(token)

    created = client.post("/api/v1/receiving/session", headers=headers, json={})
    assert created.status_code == 200, created.text
    session_id = created.json()["id"]

    uploaded = client.post(
        f"/api/v1/receiving/session/{session_id}/upload",
        headers=headers,
        files=[
            ("images", ("verified.png", _png_bytes((1, 2, 3)), "image/png")),
            ("images", ("review.png", _png_bytes((4, 5, 6)), "image/png")),
            ("images", ("unknown.png", _png_bytes((7, 8, 9)), "image/png")),
        ],
    )
    assert uploaded.status_code == 200, uploaded.text
    session = uploaded.json()["session"]
    assert [item["sequence_index"] for item in session["items"]] == [0, 1, 2]
    assert session["verified_items"] == 1
    assert session["review_items"] == 1
    assert session["unknown_items"] == 1
    assert session["confirmed_items"] == 0
    assert session["skipped_items"] == 0
    assert [item["recognition_bucket"] for item in session["items"]] == ["VERIFIED", "REVIEW", "UNKNOWN"]

    detail = client.get(f"/api/v1/receiving/session/{session_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["items"][0]["source_filename"] == "verified.png"
    assert detail.json()["items"][1]["source_filename"] == "review.png"
    assert detail.json()["items"][2]["source_filename"] == "unknown.png"

