from __future__ import annotations

from datetime import date
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session, select

from app.models.catalog_master import CatalogImage, CatalogIssue, CatalogPublisher, CatalogSeries
from app.models.receiving import RecognitionCorrectionEvent
from app.services.catalog_ingestion_service import normalize_issue_number
from app.services.recognition.recognition_models import RecognitionCandidateRead, RecognitionIdentifyRead
from test_inventory import auth_headers, register_and_login


def _png_bytes(color: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", (1600, 2400), color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _seed_venom_catalog(session: Session, *, count: int = 8) -> dict[str, int]:
    publisher = CatalogPublisher(name="Marvel", normalized_name="marvel")
    session.add(publisher)
    session.flush()
    series = CatalogSeries(name="Venom", normalized_name="venom", publisher_id=publisher.id)
    session.add(series)
    session.flush()
    issue_ids: dict[str, int] = {}
    for number in range(1, count + 1):
        issue = CatalogIssue(
            series_id=series.id,
            publisher_id=publisher.id,
            issue_number=str(number),
            normalized_issue_number=normalize_issue_number(str(number)),
        )
        session.add(issue)
        session.flush()
        session.add(
            CatalogImage(
                issue_id=issue.id,
                image_type="cover",
                source_url=f"https://example.com/venom-{number}.jpg",
                source="comicvine",
            )
        )
        issue_ids[str(number)] = int(issue.id)
    session.commit()
    return issue_ids


def _stub_review_venom_7(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_identify(session, *, image_bytes: bytes, source_name: str = "upload"):
        return RecognitionIdentifyRead(
            status="success",
            bucket="REVIEW",
            confidence=0.88,
            series="Venom",
            issue_number="7",
            variant=None,
            publisher="Marvel",
            release_date=date(2018, 11, 1),
            cover_image_url="https://example.com/venom-7.jpg",
            catalog_issue_id=999,
            winning_source="catalog_image_fingerprint",
            candidate_count=1,
            candidates=[
                RecognitionCandidateRead(
                    series="Venom",
                    issue_number="7",
                    publisher="Marvel",
                    confidence=0.88,
                    cover_image_url="https://example.com/venom-7.jpg",
                    source="CatalogIssue",
                    source_id=999,
                )
            ],
            metrics={},
        )

    monkeypatch.setattr("app.services.receiving.receiving_service.identify_comic_cover_read", fake_identify)


def _upload_review_item(client: TestClient, headers: dict[str, str]) -> tuple[int, int]:
    created = client.post("/api/v1/receiving/session", headers=headers, json={})
    assert created.status_code == 200, created.text
    session_id = created.json()["id"]
    uploaded = client.post(
        f"/api/v1/receiving/session/{session_id}/upload",
        headers=headers,
        files=[("images", ("review.png", _png_bytes((30, 40, 50)), "image/png"))],
    )
    assert uploaded.status_code == 200, uploaded.text
    item_id = uploaded.json()["session"]["items"][0]["id"]
    return session_id, item_id


def test_correction_updates_item_and_preserves_original(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    issue_ids = _seed_venom_catalog(session)
    _stub_review_venom_7(monkeypatch)
    token = register_and_login(client, "correct-venom@example.com")
    headers = auth_headers(token)

    session_id, item_id = _upload_review_item(client, headers)

    corrected = client.post(
        f"/api/v1/receiving/session/{session_id}/items/{item_id}/correct",
        headers=headers,
        json={"catalog_issue_id": issue_ids["1"], "reason": "wrong_issue_number"},
    )
    assert corrected.status_code == 200, corrected.text
    item = corrected.json()["item"]
    assert item["user_corrected"] is True
    assert item["corrected_catalog_issue_id"] == issue_ids["1"]
    assert item["correction_reason"] == "wrong_issue_number"
    # Original recognition preserved
    assert item["original_recognition_snapshot_json"]["issue_number"] == "7"
    # Corrected snapshot returned + points at chosen issue
    assert item["corrected_recognition_snapshot_json"]["issue_number"] == "1"
    assert item["corrected_recognition_snapshot_json"]["catalog_issue_id"] == issue_ids["1"]
    assert item["selected_candidate_json"]["issue_number"] == "1"


def test_correction_then_confirm_stores_corrected_issue(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    issue_ids = _seed_venom_catalog(session)
    _stub_review_venom_7(monkeypatch)
    token = register_and_login(client, "correct-confirm@example.com")
    headers = auth_headers(token)

    session_id, item_id = _upload_review_item(client, headers)
    corrected = client.post(
        f"/api/v1/receiving/session/{session_id}/items/{item_id}/correct",
        headers=headers,
        json={"catalog_issue_id": issue_ids["1"], "reason": "wrong_issue_number"},
    )
    selected_index = corrected.json()["item"]["selected_candidate_index"]

    confirmed = client.post(
        f"/api/v1/receiving/session/{session_id}/confirm",
        headers=headers,
        json={"item_id": item_id, "decision": "confirm", "selected_candidate_index": selected_index},
    )
    assert confirmed.status_code == 200, confirmed.text
    confirmed_item = confirmed.json()["item"]
    assert confirmed_item["status"] == "CONFIRMED"
    assert confirmed_item["selected_candidate_json"]["issue_number"] == "1"


def test_correction_records_event(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    issue_ids = _seed_venom_catalog(session)
    _stub_review_venom_7(monkeypatch)
    token = register_and_login(client, "correct-event@example.com")
    headers = auth_headers(token)

    session_id, item_id = _upload_review_item(client, headers)
    client.post(
        f"/api/v1/receiving/session/{session_id}/items/{item_id}/correct",
        headers=headers,
        json={"catalog_issue_id": issue_ids["1"], "reason": "wrong_issue_number"},
    )

    events = session.exec(
        select(RecognitionCorrectionEvent).where(
            RecognitionCorrectionEvent.receiving_session_item_id == item_id
        )
    ).all()
    assert len(events) == 1
    event = events[0]
    assert event.corrected_catalog_issue_id == issue_ids["1"]
    assert event.original_source == "catalog_image_fingerprint"
    assert event.correction_reason == "wrong_issue_number"
    assert event.captured_image_sha256 is not None


def test_correction_rejects_finalized_item(
    client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    issue_ids = _seed_venom_catalog(session)
    _stub_review_venom_7(monkeypatch)
    token = register_and_login(client, "correct-final@example.com")
    headers = auth_headers(token)

    session_id, item_id = _upload_review_item(client, headers)
    client.post(
        f"/api/v1/receiving/session/{session_id}/skip",
        headers=headers,
        json={"item_id": item_id, "reason": "later"},
    )

    rejected = client.post(
        f"/api/v1/receiving/session/{session_id}/items/{item_id}/correct",
        headers=headers,
        json={"catalog_issue_id": issue_ids["1"]},
    )
    assert rejected.status_code == 409, rejected.text
