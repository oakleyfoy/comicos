from __future__ import annotations

from datetime import date
from io import BytesIO
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import select

from app.models import InventoryCopy
from app.services.recognition.recognition_models import RecognitionCandidateRead, RecognitionIdentifyRead
from test_inventory import auth_headers, register_and_login


def _png_bytes(color: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", (1600, 2400), color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _recognition(series: str, issue_number: str, confidence: float = 0.99) -> RecognitionIdentifyRead:
    return RecognitionIdentifyRead(
        status="success",
        bucket="VERIFIED",  # type: ignore[arg-type]
        confidence=confidence,
        series=series,
        issue_number=issue_number,
        variant="Cover A",
        publisher="DC",
        release_date=date(1993, 7, 1),
        cover_image_url="https://example.com/comic.jpg",
        candidate_count=1,
        candidates=[
            RecognitionCandidateRead(
                series=series,
                issue_number=issue_number,
                variant="Cover A",
                publisher="DC",
                release_date=date(1993, 7, 1),
                confidence=confidence,
                cover_image_url="https://example.com/comic.jpg",
                source="ExternalCatalogIssue",
                source_id=1,
            )
        ],
        metrics={},
    )


def _stub_recognition(monkeypatch: pytest.MonkeyPatch, *, key_issue_first: bool = True) -> None:
    if key_issue_first:
        responses = {
            "key.png": _recognition("Batman", "1"),
            "second.png": _recognition("Batman", "2"),
        }
    else:
        responses = {
            "first.png": _recognition("Batman", "497"),
            "second.png": _recognition("Batman", "498"),
        }

    def fake_identify(session, *, image_bytes: bytes, source_name: str = "upload"):
        return responses[source_name]

    monkeypatch.setattr("app.services.receiving.receiving_service.identify_comic_cover_read", fake_identify)


def _prepare_session(client: TestClient, headers: dict[str, str], first_name: str, second_name: str) -> tuple[int, list[int]]:
    created = client.post("/api/v1/receiving/session", headers=headers, json={})
    assert created.status_code == 200, created.text
    session_id = created.json()["id"]

    uploaded = client.post(
        f"/api/v1/receiving/session/{session_id}/upload",
        headers=headers,
        files=[
            ("images", (first_name, _png_bytes((10, 20, 30)), "image/png")),
            ("images", (second_name, _png_bytes((30, 40, 50)), "image/png")),
        ],
    )
    assert uploaded.status_code == 200, uploaded.text

    item_ids: list[int] = []
    for item in uploaded.json()["session"]["items"]:
        item_ids.append(int(item["id"]))
        confirm = client.post(
            f"/api/v1/receiving/session/{session_id}/confirm",
            headers=headers,
            json={"item_id": item["id"], "decision": "confirm", "selected_candidate_index": 0},
        )
        assert confirm.status_code == 200, confirm.text

    return session_id, item_ids


def test_equal_allocation_splits_cost_evenly(
    client: TestClient,
    session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_recognition(monkeypatch, key_issue_first=False)
    token = register_and_login(client, "alloc-equal@example.com")
    headers = auth_headers(token)
    session_id, _item_ids = _prepare_session(client, headers, "first.png", "second.png")

    assign = client.post(
        f"/api/v1/receiving/session/{session_id}/assign-purchase",
        headers=headers,
        json={
            "mode": "new",
            "source_type": "FACEBOOK",
            "purchase_date": "2026-06-09",
            "amount_paid": "20.00",
            "shipping_amount": "0.00",
            "tax_amount": "0.00",
            "allocation_method": "equal",
        },
    )
    assert assign.status_code == 200, assign.text
    completed = client.post(f"/api/v1/receiving/session/{session_id}/complete", headers=headers)
    assert completed.status_code == 200, completed.text

    copies = list(session.exec(select(InventoryCopy).where(InventoryCopy.receiving_session_id == session_id)).all())
    assert [copy.acquisition_cost for copy in sorted(copies, key=lambda row: int(row.id or 0))] == [
        Decimal("10.00"),
        Decimal("10.00"),
    ]


def test_manual_allocation_honors_explicit_amounts(
    client: TestClient,
    session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_recognition(monkeypatch, key_issue_first=False)
    token = register_and_login(client, "alloc-manual@example.com")
    headers = auth_headers(token)
    session_id, item_ids = _prepare_session(client, headers, "first.png", "second.png")

    assign = client.post(
        f"/api/v1/receiving/session/{session_id}/assign-purchase",
        headers=headers,
        json={
            "mode": "new",
            "source_type": "WHATNOT",
            "purchase_date": "2026-06-09",
            "amount_paid": "20.00",
            "shipping_amount": "0.00",
            "tax_amount": "0.00",
            "allocation_method": "manual",
            "manual_allocations": [
                {"item_id": item_ids[0], "amount": "14.00"},
                {"item_id": item_ids[1], "amount": "6.00"},
            ],
        },
    )
    assert assign.status_code == 200, assign.text
    completed = client.post(f"/api/v1/receiving/session/{session_id}/complete", headers=headers)
    assert completed.status_code == 200, completed.text

    copies = list(session.exec(select(InventoryCopy).where(InventoryCopy.receiving_session_id == session_id)).all())
    costs = [copy.acquisition_cost for copy in sorted(copies, key=lambda row: int(row.id or 0))]
    assert costs == [Decimal("14.00"), Decimal("6.00")]


def test_key_weighted_allocation_prefers_key_issue(
    client: TestClient,
    session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_recognition(monkeypatch, key_issue_first=True)
    token = register_and_login(client, "alloc-key-weighted@example.com")
    headers = auth_headers(token)
    session_id, _item_ids = _prepare_session(client, headers, "key.png", "second.png")

    assign = client.post(
        f"/api/v1/receiving/session/{session_id}/assign-purchase",
        headers=headers,
        json={
            "mode": "new",
            "source_type": "COLLECTION_BUY",
            "purchase_date": "2026-06-09",
            "amount_paid": "20.00",
            "shipping_amount": "0.00",
            "tax_amount": "0.00",
            "allocation_method": "key_weighted",
        },
    )
    assert assign.status_code == 200, assign.text
    completed = client.post(f"/api/v1/receiving/session/{session_id}/complete", headers=headers)
    assert completed.status_code == 200, completed.text

    copies = list(session.exec(select(InventoryCopy).where(InventoryCopy.receiving_session_id == session_id)).all())
    costs = [copy.acquisition_cost for copy in sorted(copies, key=lambda row: int(row.id or 0))]
    assert costs[0] > costs[1]
