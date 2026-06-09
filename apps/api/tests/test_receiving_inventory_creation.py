from __future__ import annotations

from datetime import date
from io import BytesIO
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import select

from app.models import InventoryCopy, Order, User
from app.services.recognition.recognition_models import RecognitionCandidateRead, RecognitionIdentifyRead
from test_inventory import auth_headers, register_and_login


def _png_bytes(color: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", (1600, 2400), color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _recognition(
    *,
    bucket: str,
    confidence: float,
    series: str,
    issue_number: str,
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
        cover_image_url="https://example.com/batman.jpg",
        candidate_count=1,
        candidates=[
            RecognitionCandidateRead(
                series=series,
                issue_number=issue_number,
                variant="Cover A",
                publisher="DC",
                release_date=date(1993, 7, 1),
                confidence=confidence,
                cover_image_url="https://example.com/batman.jpg",
                source="ExternalCatalogIssue",
                source_id=1,
            )
        ],
        metrics={},
    )


def _stub_recognition(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = {
        "batman-497.png": _recognition(bucket="VERIFIED", confidence=0.99, series="Batman", issue_number="497"),
        "spawn-1.png": _recognition(bucket="VERIFIED", confidence=0.98, series="Spawn", issue_number="1"),
        "review.png": _recognition(bucket="REVIEW", confidence=0.81, series="Venom", issue_number="3"),
        "unknown.png": _recognition(bucket="UNKNOWN", confidence=0.41, series="Unknown", issue_number=""),
    }

    def fake_identify(session, *, image_bytes: bytes, source_name: str = "upload"):
        return responses[source_name]

    monkeypatch.setattr("app.services.receiving.receiving_service.identify_comic_cover_read", fake_identify)


def _create_confirmed_session(client: TestClient, headers: dict[str, str]) -> int:
    created = client.post("/api/v1/receiving/session", headers=headers, json={})
    assert created.status_code == 200, created.text
    session_id = created.json()["id"]

    uploaded = client.post(
        f"/api/v1/receiving/session/{session_id}/upload",
        headers=headers,
        files=[
            ("images", ("batman-497.png", _png_bytes((10, 20, 30)), "image/png")),
            ("images", ("spawn-1.png", _png_bytes((20, 30, 40)), "image/png")),
            ("images", ("review.png", _png_bytes((30, 40, 50)), "image/png")),
            ("images", ("unknown.png", _png_bytes((40, 50, 60)), "image/png")),
        ],
    )
    assert uploaded.status_code == 200, uploaded.text
    session = uploaded.json()["session"]

    for item in session["items"]:
        if item["status"] == "VERIFIED":
            confirm = client.post(
                f"/api/v1/receiving/session/{session_id}/confirm",
                headers=headers,
                json={"item_id": item["id"], "decision": "confirm", "selected_candidate_index": 0},
            )
            assert confirm.status_code == 200, confirm.text

    return session_id


def test_receiving_completion_creates_inventory_and_skips_unresolved(
    client: TestClient,
    session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_recognition(monkeypatch)
    token = register_and_login(client, "receiving-complete@example.com")
    headers = auth_headers(token)

    session_id = _create_confirmed_session(client, headers)

    assign = client.post(
        f"/api/v1/receiving/session/{session_id}/assign-purchase",
        headers=headers,
        json={
            "mode": "new",
            "source_type": "FACEBOOK",
            "purchase_label": "Facebook Lot",
            "seller_name": "Private Seller",
            "purchase_date": "2026-06-09",
            "amount_paid": "20.00",
            "shipping_amount": "5.00",
            "tax_amount": "0.00",
            "allocation_method": "equal",
            "manual_allocations": [],
        },
    )
    assert assign.status_code == 200, assign.text

    completed = client.post(f"/api/v1/receiving/session/{session_id}/complete", headers=headers)
    assert completed.status_code == 200, completed.text
    payload = completed.json()
    assert payload["confirmed_inventory_count"] == 2
    assert len(payload["inventory_copy_ids"]) == 2
    assert payload["top_additions"][:2] == ["Batman #497", "Spawn #1"]
    assert payload["session"]["status"] == "COMPLETED"
    assert payload["session"]["inventory_created_count"] == 2
    assert payload["session"]["purchase_source_type"] == "FACEBOOK"

    copies = list(session.exec(select(InventoryCopy).where(InventoryCopy.receiving_session_id == session_id)).all())
    assert len(copies) == 2
    assert all(copy.received_via == "RECEIVING_STATION" for copy in copies)
    assert {copy.acquisition_cost for copy in copies} == {Decimal("12.50")}

    refreshed = client.get(f"/api/v1/receiving/session/{session_id}/summary", headers=headers)
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["session"]["inventory_created_count"] == 2
    assert refreshed.json()["confirmed_inventory_count"] == 2


def test_receiving_existing_purchase_assignment_links_existing_order(
    client: TestClient,
    session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_recognition(monkeypatch)
    token = register_and_login(client, "receiving-existing@example.com")
    headers = auth_headers(token)

    created = client.post("/api/v1/receiving/session", headers=headers, json={})
    assert created.status_code == 200, created.text
    session_id = created.json()["id"]
    uploaded = client.post(
        f"/api/v1/receiving/session/{session_id}/upload",
        headers=headers,
        files=[("images", ("batman-497.png", _png_bytes((10, 20, 30)), "image/png"))],
    )
    assert uploaded.status_code == 200, uploaded.text
    item_id = uploaded.json()["session"]["items"][0]["id"]
    confirm = client.post(
        f"/api/v1/receiving/session/{session_id}/confirm",
        headers=headers,
        json={"item_id": item_id, "decision": "confirm", "selected_candidate_index": 0},
    )
    assert confirm.status_code == 200, confirm.text

    user = session.exec(select(User).where(User.email == "receiving-existing@example.com")).one()
    order = Order(
        user_id=int(user.id),
        retailer="Convention Haul",
        order_date=date(2026, 6, 1),
        source_type="CONVENTION",
        shipping_amount=Decimal("0.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("0.00"),
    )
    session.add(order)
    session.commit()
    session.refresh(order)

    assign = client.post(
        f"/api/v1/receiving/session/{session_id}/assign-purchase",
        headers=headers,
        json={
            "mode": "existing",
            "existing_order_id": order.id,
            "source_type": "CONVENTION",
            "seller_name": "Dealer",
            "amount_paid": "15.00",
            "shipping_amount": "0.00",
            "tax_amount": "0.00",
            "allocation_method": "equal",
        },
    )
    assert assign.status_code == 200, assign.text

    completed = client.post(f"/api/v1/receiving/session/{session_id}/complete", headers=headers)
    assert completed.status_code == 200, completed.text
    assert completed.json()["order_id"] == order.id

    session.expire_all()
    refreshed_order = session.exec(select(Order).where(Order.id == order.id)).one()
    assert refreshed_order is not None
    assert refreshed_order.total_amount == Decimal("15.00")
    inventory = list(session.exec(select(InventoryCopy).where(InventoryCopy.receiving_session_id == session_id)).all())
    assert len(inventory) == 1
    assert inventory[0].received_via == "RECEIVING_STATION"
