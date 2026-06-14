from __future__ import annotations

import concurrent.futures
from datetime import date
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.services.recognition.recognition_models import RecognitionCandidateRead, RecognitionIdentifyRead
from test_inventory import auth_headers, register_and_login


def _png_bytes(color: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", (640, 960), color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _stub_recognition(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_identify(session, *, image_bytes: bytes, source_name: str = "upload"):
        return RecognitionIdentifyRead(
            status="success",
            bucket="UNKNOWN",
            confidence=0.02,
            series="Unknown",
            issue_number="",
            variant=None,
            publisher=None,
            release_date=date(1993, 7, 1),
            cover_image_url=None,
            candidate_count=0,
            candidates=[],
            metrics={},
        )

    monkeypatch.setattr("app.services.receiving.receiving_service.identify_comic_cover_read", fake_identify)


def _upload_once(
    client: TestClient,
    *,
    headers: dict[str, str],
    session_id: int,
    fingerprint: str,
    body: bytes,
) -> tuple[int, int | None]:
    response = client.post(
        f"/api/v1/receiving/session/{session_id}/upload",
        headers=headers,
        data={
            "capture_source": "WEBCAM",
            "frame_fingerprint": fingerprint,
            "stable_frame_count": "3",
            "frame_sequence_index": "0",
        },
        files=[("images", ("frame.png", body, "image/png"))],
    )
    uploaded_count = None
    if response.status_code == 200:
        uploaded_count = int(response.json().get("uploaded_count", 0))
    return response.status_code, uploaded_count


def test_concurrent_receiving_uploads_do_not_500_and_sequence_indexes_are_unique(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_recognition(monkeypatch)
    token = register_and_login(client, "receiving-upload-race@example.com")
    headers = auth_headers(token)

    created = client.post(
        "/api/v1/receiving/session",
        headers=headers,
        json={"capture_source": "WEBCAM"},
    )
    assert created.status_code == 200, created.text
    session_id = int(created.json()["id"])
    body = _png_bytes((12, 34, 56))

    def worker(index: int) -> tuple[int, int | None]:
        thread_client = TestClient(client.app)
        return _upload_once(
            thread_client,
            headers=headers,
            session_id=session_id,
            fingerprint=f"fingerprint-{index}",
            body=body,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(worker, range(8)))

    statuses = [status for status, _uploaded in results]
    assert all(status != 500 for status in statuses), statuses
    assert any(status == 200 for status in statuses)

    detail = client.get(f"/api/v1/receiving/session/{session_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    items = detail.json()["items"]
    sequence_indexes = [int(item["sequence_index"]) for item in items]
    assert sequence_indexes == sorted(sequence_indexes)
    assert len(sequence_indexes) == len(set(sequence_indexes))
    assert sequence_indexes == list(range(len(sequence_indexes)))
    success_count = sum(1 for status in statuses if status == 200)
    assert success_count == len(sequence_indexes)
