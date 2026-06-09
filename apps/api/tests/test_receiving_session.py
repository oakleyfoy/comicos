from __future__ import annotations

from datetime import date
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session

from app.services.recognition.recognition_models import RecognitionCandidateRead, RecognitionIdentifyRead
from test_inventory import auth_headers, register_and_login


def _png_bytes(color: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", (1600, 2400), color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _recognition_result(
    *,
    bucket: str,
    confidence: float,
    series: str,
    issue_number: str,
    candidates: list[RecognitionCandidateRead] | None = None,
) -> RecognitionIdentifyRead:
    return RecognitionIdentifyRead(
        status="success",
        bucket=bucket,  # type: ignore[arg-type]
        confidence=confidence,
        series=series,
        issue_number=issue_number,
        variant="Cover A",
        publisher="DC",
        release_date=date(1993, 7, 1),
        cover_image_url="https://example.com/batman-497.jpg",
        candidate_count=len(candidates or []),
        candidates=candidates or [],
        metrics={},
    )


def _stub_recognition(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = {
        "verified.png": _recognition_result(
            bucket="VERIFIED",
            confidence=0.99,
            series="Batman",
            issue_number="497",
            candidates=[
                RecognitionCandidateRead(
                    series="Batman",
                    issue_number="497",
                    variant="Cover A",
                    publisher="DC",
                    release_date="1993-07-01",
                    confidence=0.99,
                    cover_image_url="https://example.com/batman-497.jpg",
                    source="ExternalCatalogIssue",
                    source_id=1,
                )
            ],
        ),
        "review.png": _recognition_result(
            bucket="REVIEW",
            confidence=0.83,
            series="Batman",
            issue_number="498",
            candidates=[
                RecognitionCandidateRead(
                    series="Batman",
                    issue_number="498",
                    variant="Cover A",
                    publisher="DC",
                    release_date="1993-08-01",
                    confidence=0.83,
                    cover_image_url="https://example.com/batman-498.jpg",
                    source="ExternalCatalogIssue",
                    source_id=2,
                ),
                RecognitionCandidateRead(
                    series="Batman",
                    issue_number="499",
                    variant="Cover A",
                    publisher="DC",
                    release_date="1993-09-01",
                    confidence=0.61,
                    cover_image_url="https://example.com/batman-499.jpg",
                    source="ExternalCatalogIssue",
                    source_id=3,
                ),
            ],
        ),
        "unknown.png": _recognition_result(
            bucket="UNKNOWN",
            confidence=0.42,
            series="Unknown",
            issue_number="",
            candidates=[],
        ),
    }

    def fake_identify(session, *, image_bytes: bytes, source_name: str = "upload"):
        if source_name not in responses:
            raise AssertionError(f"unexpected source_name: {source_name}")
        return responses[source_name]

    monkeypatch.setattr("app.services.receiving.receiving_service.identify_comic_cover_read", fake_identify)


def test_receiving_session_lifecycle_confirm_and_skip(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_recognition(monkeypatch)
    token = register_and_login(client, "receiving-session@example.com")
    headers = auth_headers(token)

    created = client.post("/api/v1/receiving/session", headers=headers, json={})
    assert created.status_code == 200, created.text
    session_id = created.json()["id"]

    uploaded = client.post(
        f"/api/v1/receiving/session/{session_id}/upload",
        headers=headers,
        files=[
            ("images", ("verified.png", _png_bytes((10, 20, 30)), "image/png")),
            ("images", ("review.png", _png_bytes((30, 40, 50)), "image/png")),
            ("images", ("unknown.png", _png_bytes((50, 60, 70)), "image/png")),
        ],
    )
    assert uploaded.status_code == 200, uploaded.text
    payload = uploaded.json()
    assert payload["uploaded_count"] == 3
    session = payload["session"]
    assert session["total_items"] == 3
    assert session["verified_items"] == 1
    assert session["review_items"] == 1
    assert session["unknown_items"] == 1
    assert [item["status"] for item in session["items"]] == ["VERIFIED", "REVIEW", "UNKNOWN"]

    review_item_id = next(item["id"] for item in session["items"] if item["status"] == "REVIEW")
    confirm = client.post(
        f"/api/v1/receiving/session/{session_id}/confirm",
        headers=headers,
        json={"item_id": review_item_id, "decision": "wrong_match", "selected_candidate_index": 1},
    )
    assert confirm.status_code == 200, confirm.text
    confirm_payload = confirm.json()
    assert confirm_payload["item"]["status"] == "CONFIRMED"
    assert confirm_payload["item"]["selected_candidate_index"] == 1
    assert confirm_payload["session"]["confirmed_items"] == 1
    assert confirm_payload["session"]["review_items"] == 0

    unknown_item_id = next(item["id"] for item in confirm_payload["session"]["items"] if item["status"] == "UNKNOWN")
    skipped = client.post(
        f"/api/v1/receiving/session/{session_id}/skip",
        headers=headers,
        json={"item_id": unknown_item_id, "reason": "later"},
    )
    assert skipped.status_code == 200, skipped.text
    skipped_payload = skipped.json()
    assert skipped_payload["item"]["status"] == "SKIPPED"
    assert skipped_payload["session"]["skipped_items"] == 1
    assert skipped_payload["session"]["confirmed_items"] == 1

