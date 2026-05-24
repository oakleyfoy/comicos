from __future__ import annotations

import io
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session, select

from app.models import (
    CoverImage,
    CoverImageOcrQualityAnalysis,
    CoverRelationshipConflict,
    HighResReviewRequest,
    InventoryCopy,
    QueueRoutingRecommendation,
)
import app.tasks.queue as tasks_queue_module
import app.services.high_res_review_requests as high_res_review_requests_module
from test_inventory import auth_headers, create_order, register_and_login


def _png_bytes(*, size: tuple[int, int] = (800, 1200)) -> bytes:
    img = Image.new("RGB", size, (30, 80, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _create_cover(client: TestClient, headers: dict[str, str], inventory_copy_id: int, *, size: tuple[int, int]) -> int:
    rsp = client.post(
        f"/inventory/{inventory_copy_id}/cover-images",
        headers=headers,
        files={"file": ("cover.png", _png_bytes(size=size), "image/png")},
    )
    assert rsp.status_code == 200
    return int(rsp.json()["id"])


def _create_session_item(
    client: TestClient,
    headers: dict[str, str],
    session_id: int,
    *,
    source_filename: str = "scan.png",
    image_sha256: str = "a" * 64,
    image_width: int | None = 800,
    image_height: int | None = 1200,
    inventory_copy_id: int | None = None,
    cover_image_id: int | None = None,
) -> int:
    payload: dict[str, object] = {
        "items": [
            {
                "source_filename": source_filename,
                "image_sha256": image_sha256,
                "image_width": image_width,
                "image_height": image_height,
            }
        ]
    }
    if inventory_copy_id is not None:
        payload["items"][0]["inventory_copy_id"] = inventory_copy_id  # type: ignore[index]
    if cover_image_id is not None:
        payload["items"][0]["cover_image_id"] = cover_image_id  # type: ignore[index]
    rsp = client.post(f"/scan-sessions/{session_id}/items", json=payload, headers=headers)
    assert rsp.status_code == 200
    return int(rsp.json()["items"][0]["id"])


def test_queue_routing_recommend_ocr_and_generate_persists(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "routing-ocr@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={}, headers=hdr).json()["id"]
    _create_session_item(client, hdr, sid, source_filename="ocr.png", image_sha256="1" * 64)

    routed = client.get(f"/scan-sessions/{sid}/routing", headers=hdr)
    assert routed.status_code == 200
    body = routed.json()
    assert body["persisted_run"] is False
    assert body["items"][0]["recommendation_type"] == "recommend_ocr"
    assert body["items"][0]["routing_status"] == "open"

    generated = client.post(f"/scan-sessions/{sid}/generate-routing", headers=hdr)
    assert generated.status_code == 200
    assert generated.json()["persisted_run"] is True

    persisted = session.exec(select(QueueRoutingRecommendation).where(QueueRoutingRecommendation.scan_session_item_id.is_not(None))).all()
    assert len(persisted) == 1
    assert persisted[0].recommendation_type == "recommend_ocr"


def test_queue_routing_high_res_review_for_quality_signal(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "routing-highres@example.com")
    hdr = auth_headers(token)
    create_order(client, token)
    inv_copy_id = client.get("/inventory", headers=hdr).json()["items"][0]["inventory_copy_id"]
    cover_id = _create_cover(client, hdr, inv_copy_id, size=(1200, 1600))

    now = datetime.now(timezone.utc)
    session.add(
        CoverImageOcrQualityAnalysis(
            cover_image_id=cover_id,
            source_ocr_result_id=None,
            quality_type="overall_quality",
            deterministic_score=0.07,
            severity="critical",
            detail_json={"signal": "too_soft"},
            extraction_version="routing-tests",
            created_at=now,
            updated_at=now,
        ),
    )
    session.commit()

    sid = client.post("/scan-sessions", json={}, headers=hdr).json()["id"]
    _create_session_item(
        client,
        hdr,
        sid,
        source_filename="highres.png",
        image_sha256="2" * 64,
        inventory_copy_id=inv_copy_id,
        cover_image_id=cover_id,
        image_width=1200,
        image_height=1600,
    )

    routed = client.get(f"/scan-sessions/{sid}/routing", headers=hdr).json()["items"][0]
    assert routed["recommendation_type"] == "recommend_high_res_review"
    assert routed["routing_status"] == "open"
    assert "needs_high_res_review" in routed["evidence_json"]["reasons"]


def test_queue_routing_manual_review_for_conflict(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "routing-manual@example.com")
    hdr = auth_headers(token)
    create_order(client, token)
    inv_copy_id = client.get("/inventory", headers=hdr).json()["items"][0]["inventory_copy_id"]
    cover_id = _create_cover(client, hdr, inv_copy_id, size=(1200, 1600))

    sid = client.post("/scan-sessions", json={}, headers=hdr).json()["id"]
    _create_session_item(
        client,
        hdr,
        sid,
        source_filename="manual.png",
        image_sha256="3" * 64,
        inventory_copy_id=inv_copy_id,
        cover_image_id=cover_id,
        image_width=1200,
        image_height=1600,
    )

    now = datetime.now(timezone.utc)
    session.add(
        CoverRelationshipConflict(
            conflict_type="duplicate_scan_conflict",
            severity="high",
            source_cover_image_id=cover_id,
            related_cover_image_id=cover_id,
            conflict_key=f"routing-manual:{cover_id}",
            status="open",
            evidence_json={"kind": "open_conflict"},
            created_at=now,
            updated_at=now,
        ),
    )
    session.commit()

    routed = client.get(f"/scan-sessions/{sid}/routing", headers=hdr).json()["items"][0]
    assert routed["recommendation_type"] == "recommend_manual_review"
    assert "unresolved_relationship_conflict" in routed["evidence_json"]["reasons"]


def test_queue_routing_hold_for_open_review_request(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "routing-rescan@example.com")
    hdr = auth_headers(token)
    create_order(client, token)
    inv_copy_id = client.get("/inventory", headers=hdr).json()["items"][0]["inventory_copy_id"]
    inv_copy = session.exec(select(InventoryCopy).where(InventoryCopy.id == inv_copy_id)).one()
    cover_id = _create_cover(client, hdr, inv_copy_id, size=(800, 1200))

    now = datetime.now(timezone.utc)
    session.add(
        HighResReviewRequest(
            owner_user_id=int(inv_copy.user_id or 1),
            inventory_copy_id=inv_copy_id,
            source_cover_image_id=cover_id,
            source_scan_session_item_id=None,
            source_ocr_quality_analysis_id=None,
            source_inventory_risk_type=None,
            source_action_center_category=None,
            attach_scan_session_id=None,
            attach_scan_session_item_id=None,
            high_res_cover_image_id=None,
            request_reason="low_quality_scan",
            status="pending",
            priority="high",
            notes=None,
            created_at=now,
            updated_at=now,
            completed_at=None,
        ),
    )
    session.commit()

    sid = client.post("/scan-sessions", json={}, headers=hdr).json()["id"]
    item_id = _create_session_item(
        client,
        hdr,
        sid,
        source_filename="rescan.png",
        image_sha256="4" * 64,
        inventory_copy_id=inv_copy_id,
        cover_image_id=cover_id,
        image_width=800,
        image_height=1200,
    )
    client.post(f"/scan-sessions/{sid}/start", headers=hdr)
    client.patch(
        f"/scan-sessions/{sid}/items/{item_id}",
        json={"ingest_status": "failed", "ingest_error": "cannot identify image format"},
        headers=hdr,
    )

    routed = client.get(f"/scan-sessions/{sid}/routing", headers=hdr).json()["items"][0]
    assert routed["recommendation_type"] == "recommend_hold"
    assert "review_request_open" in routed["evidence_json"]["reasons"]


def test_queue_routing_rescan_for_corrupt_item(client: TestClient) -> None:
    token = register_and_login(client, "routing-corrupt@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={}, headers=hdr).json()["id"]
    item_id = _create_session_item(client, hdr, sid, source_filename="corrupt.png", image_sha256="7" * 64)
    client.post(f"/scan-sessions/{sid}/start", headers=hdr)
    client.patch(
        f"/scan-sessions/{sid}/items/{item_id}",
        json={"ingest_status": "failed", "ingest_error": "cannot identify image format"},
        headers=hdr,
    )

    routed = client.get(f"/scan-sessions/{sid}/routing", headers=hdr).json()["items"][0]
    assert routed["recommendation_type"] == "recommend_rescan"
    assert "corrupt_image" in routed["evidence_json"]["reasons"]


def test_queue_routing_hold_for_duplicate_scan(client: TestClient) -> None:
    token = register_and_login(client, "routing-dup@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={}, headers=hdr).json()["id"]
    client.post(
        f"/scan-sessions/{sid}/items",
        json={
            "items": [
                {"source_filename": "dup-a.png", "image_sha256": "d" * 64},
                {"source_filename": "dup-b.png", "image_sha256": "d" * 64},
            ],
        },
        headers=hdr,
    )

    routed = client.get(f"/scan-sessions/{sid}/routing", headers=hdr).json()["items"]
    assert [row["recommendation_type"] for row in routed] == ["recommend_hold", "recommend_hold"]
    assert all("duplicate_scan" in row["evidence_json"]["reasons"] for row in routed)


def test_queue_routing_already_processed_no_action(client: TestClient) -> None:
    token = register_and_login(client, "routing-done@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={}, headers=hdr).json()["id"]
    item_id = _create_session_item(client, hdr, sid, source_filename="done.png", image_sha256="e" * 64)
    client.post(f"/scan-sessions/{sid}/start", headers=hdr)
    client.patch(f"/scan-sessions/{sid}/items/{item_id}", json={"ingest_status": "imported"}, headers=hdr)
    client.patch(f"/scan-sessions/{sid}/items/{item_id}", json={"ingest_status": "queued_for_ocr"}, headers=hdr)
    client.patch(f"/scan-sessions/{sid}/items/{item_id}", json={"ingest_status": "ocr_complete"}, headers=hdr)

    routed = client.get(f"/scan-sessions/{sid}/routing", headers=hdr).json()["items"][0]
    assert routed["recommendation_type"] == "recommend_no_action"
    assert "already_ocr_processed" in routed["evidence_json"]["reasons"]


def test_queue_routing_acknowledge_and_dismiss(client: TestClient) -> None:
    token = register_and_login(client, "routing-status@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={}, headers=hdr).json()["id"]
    client.post(
        f"/scan-sessions/{sid}/items",
        json={
            "items": [
                {"source_filename": "status-a.png", "image_sha256": "f" * 64},
                {"source_filename": "status-b.png", "image_sha256": "0" * 64},
            ],
        },
        headers=hdr,
    )

    generated = client.post(f"/scan-sessions/{sid}/generate-routing", headers=hdr).json()["items"]
    first_id = int(generated[0]["id"])
    second_id = int(generated[1]["id"])

    ack = client.post(f"/scan-routing-recommendations/{first_id}/acknowledge", headers=hdr)
    assert ack.status_code == 200
    dis = client.post(f"/scan-routing-recommendations/{second_id}/dismiss", headers=hdr)
    assert dis.status_code == 200

    refreshed = client.get(f"/scan-sessions/{sid}/routing", headers=hdr).json()["items"]
    assert {row["routing_status"] for row in refreshed} == {"acknowledged", "dismissed"}


def test_queue_routing_no_automatic_enqueue_or_metadata_mutation(
    monkeypatch: pytest.MonkeyPatch, client: TestClient, session: Session
) -> None:
    called: list[str] = []

    def boom(*_args, **_kwargs):  # pragma: no cover - must not trigger
        called.append("boom")
        raise AssertionError("Unexpected automatic side effect")

    monkeypatch.setattr(tasks_queue_module, "enqueue_cover_image_ocr_job", boom)
    monkeypatch.setattr(tasks_queue_module, "enqueue_cover_image_process_job", boom)
    monkeypatch.setattr(high_res_review_requests_module, "create_high_res_review_request", boom)

    token = register_and_login(client, "routing-safe@example.com")
    hdr = auth_headers(token)
    create_order(client, token)
    rows_before = {r.id: (r.metadata_identity_key, r.order_status) for r in session.exec(select(InventoryCopy)).all()}
    cov_rows_before = session.exec(select(CoverImage)).all()
    link_rows_before = session.exec(select(CoverRelationshipConflict)).all()

    sid = client.post("/scan-sessions", json={}, headers=hdr).json()["id"]
    _create_session_item(client, hdr, sid, source_filename="safe.png", image_sha256="1" * 64)
    rsp = client.post(f"/scan-sessions/{sid}/generate-routing", headers=hdr)
    assert rsp.status_code == 200
    assert called == []

    rows_after = {r.id: (r.metadata_identity_key, r.order_status) for r in session.exec(select(InventoryCopy)).all()}
    cov_rows_after = session.exec(select(CoverImage)).all()
    link_rows_after = session.exec(select(CoverRelationshipConflict)).all()
    assert rows_before == rows_after
    assert len(cov_rows_before) == len(cov_rows_after)
    assert len(link_rows_before) == len(link_rows_after)

