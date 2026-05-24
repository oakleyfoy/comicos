"""P34-03 high-resolution deterministic review ledger (attachment + linkage; never auto OCR / primary swaps)."""

from __future__ import annotations

import io
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session, func, select

from app.core.config import get_settings
from app.models import CoverImage, CoverImageOcrQualityAnalysis, CoverImageOcrResult, HighResReviewRequest
from test_inventory import auth_headers, create_order, register_and_login
from test_scan_session_ingest import _post_ingest


def _png() -> bytes:
    img = Image.new("RGB", (30, 40), (1, 2, 3))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _cover_rows(session: Session) -> int:
    stmt = select(func.count()).select_from(CoverImage)  # type: ignore[arg-type]
    return int(session.exec(stmt).one())


def _ocr_rows(session: Session) -> int:
    stmt = select(func.count()).select_from(CoverImageOcrResult)  # type: ignore[arg-type]
    return int(session.exec(stmt).one())


def test_create_from_inventory_anchor(client: TestClient) -> None:
    token = register_and_login(client, "hres-inv-only@example.com")
    hdr = auth_headers(token)
    create_order(client, token)
    inv_copy_id = client.get("/inventory", headers=hdr).json()["items"][0]["inventory_copy_id"]
    rsp = client.post(
        "/high-res-review-requests",
        headers=hdr,
        json={
            "inventory_copy_id": inv_copy_id,
            "request_reason": "manual_review",
            "priority": "medium",
            "notes": "epson escalation",
            "source_inventory_risk_type": "needs_scan",
        },
    )
    assert rsp.status_code == 200


def test_create_from_cover_then_attach_primary_unchanged_and_metadata_stable(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "hres-cover-attach@example.com")
    hdr = auth_headers(token)
    create_order(client, token)
    inv_copy_id = client.get("/inventory", headers=hdr).json()["items"][0]["inventory_copy_id"]

    before_detail = client.get(f"/inventory/{inv_copy_id}", headers=hdr).json()
    before_title = before_detail["title"]
    cov_count_before = len(before_detail["cover_images"])

    up = client.post(
        f"/inventory/{inv_copy_id}/cover-images",
        headers=hdr,
        files={"file": ("bulk.png", _png(), "image/png")},
    )
    assert up.status_code == 200
    cover_id = up.json()["id"]

    assert (
        client.post(
            f"/inventory/{inv_copy_id}/cover-images/{cover_id}/primary",
            headers=hdr,
        ).status_code
        == 200
    )

    refreshed = client.get(f"/inventory/{inv_copy_id}", headers=hdr).json()
    primary_id_after_upload = next((c["id"] for c in refreshed["cover_images"] if c["is_primary"]), None)
    assert primary_id_after_upload == cover_id

    create = client.post(
        "/high-res-review-requests",
        headers=hdr,
        json={"source_cover_image_id": cover_id, "request_reason": "low_quality_scan", "priority": "high"},
    )
    assert create.status_code == 200
    req_id = create.json()["id"]

    high_png = Image.new("RGB", (160, 200), (200, 10, 10))
    hbuf = io.BytesIO()
    high_png.save(hbuf, format="PNG")
    hi = hbuf.getvalue()

    ocr_before = _ocr_rows(session)

    att = client.post(
        f"/high-res-review-requests/{req_id}/attach-scan",
        headers=hdr,
        files={"file": ("epson.tif", hi, "image/png")},
        data={"source_filename": "desk_scan_001.tif"},
    )
    assert att.status_code == 200

    detail = client.get(f"/inventory/{inv_copy_id}", headers=hdr).json()
    assert detail["title"] == before_title
    primary_final = next((c["id"] for c in detail["cover_images"] if c["is_primary"]), None)
    assert primary_final == cover_id

    assert len(detail["cover_images"]) >= cov_count_before + 1
    assert _ocr_rows(session) == ocr_before

    hr = session.get(HighResReviewRequest, req_id)
    assert hr is not None
    assert hr.high_res_cover_image_id is not None
    assert int(hr.high_res_cover_image_id) != int(cover_id)


def test_corrupt_attachment_rejected_before_side_effects(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "hres-bad-scan@example.com")
    hdr = auth_headers(token)
    create_order(client, token)
    inv_copy_id = client.get("/inventory", headers=hdr).json()["items"][0]["inventory_copy_id"]
    rsp = client.post(
        "/high-res-review-requests",
        headers=hdr,
        json={"inventory_copy_id": inv_copy_id, "request_reason": "rescan_required"},
    )
    assert rsp.status_code == 200
    req_id = rsp.json()["id"]
    before_cov = _cover_rows(session)
    att = client.post(
        f"/high-res-review-requests/{req_id}/attach-scan",
        headers=hdr,
        files={"file": ("bad.tif", b"NOT-A-IMAGE-FILE", "image/png")},
    )
    assert att.status_code == 400
    assert _cover_rows(session) == before_cov


def test_complete_and_cancel_flows(client: TestClient) -> None:
    token = register_and_login(client, "hres-life@example.com")
    hdr = auth_headers(token)
    create_order(client, token)
    inv_copy_id = client.get("/inventory", headers=hdr).json()["items"][0]["inventory_copy_id"]

    pend = client.post(
        "/high-res-review-requests",
        headers=hdr,
        json={"inventory_copy_id": inv_copy_id, "request_reason": "manual_review"},
    )
    assert pend.status_code == 200
    rid = pend.json()["id"]
    deny_complete = client.post(f"/high-res-review-requests/{rid}/complete", headers=hdr)
    assert deny_complete.status_code == 400

    png = _png()
    assert (
        client.post(
            f"/high-res-review-requests/{rid}/attach-scan",
            headers=hdr,
            files={"file": ("ok.tif", png, "image/png")},
        ).status_code
        == 200
    )

    linked = client.get(f"/high-res-review-requests/{rid}", headers=hdr).json()
    assert linked["status"] == "linked"

    done = client.post(f"/high-res-review-requests/{rid}/complete", headers=hdr)
    assert done.status_code == 200
    assert done.json()["status"] == "review_complete"

    rsp2 = client.post(
        "/high-res-review-requests",
        headers=hdr,
        json={"inventory_copy_id": inv_copy_id, "request_reason": "manual_review"},
    )
    assert rsp2.status_code == 200
    rid2 = rsp2.json()["id"]

    canceled = client.post(f"/high-res-review-requests/{rid2}/cancel", headers=hdr)
    assert canceled.status_code == 200
    assert canceled.json()["status"] == "cancelled"


def test_owner_scoping_for_detail(client: TestClient) -> None:
    alice = register_and_login(client, "hres-alice@example.com")
    bob = register_and_login(client, "hres-bob@example.com")
    ah = auth_headers(alice)
    bh = auth_headers(bob)
    create_order(client, alice)
    inv_copy_id = client.get("/inventory", headers=ah).json()["items"][0]["inventory_copy_id"]

    rsp = client.post(
        "/high-res-review-requests",
        headers=ah,
        json={"inventory_copy_id": inv_copy_id, "request_reason": "manual_review"},
    )
    assert rsp.status_code == 200
    rid = rsp.json()["id"]
    leaking = client.get(f"/high-res-review-requests/{rid}", headers=bh)
    assert leaking.status_code == 404


def test_ops_visibility(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "hres-ops@example.com")
    get_settings.cache_clear()

    owner_token = register_and_login(client, "hres-own@example.com")
    hdr = auth_headers(owner_token)
    create_order(client, owner_token)
    inv_copy_id = client.get("/inventory", headers=hdr).json()["items"][0]["inventory_copy_id"]
    cre = client.post(
        "/high-res-review-requests",
        headers=hdr,
        json={"inventory_copy_id": inv_copy_id, "request_reason": "manual_review"},
    )
    assert cre.status_code == 200
    rid = cre.json()["id"]

    ops_token = register_and_login(client, "hres-ops@example.com")
    oh = auth_headers(ops_token)
    lst = client.get("/ops/high-res-review-requests", headers=oh)
    assert lst.status_code == 200
    assert any(r["id"] == rid for r in lst.json()["requests"])

    stats = client.get("/ops/high-res-review-requests/stats", headers=oh)
    assert stats.status_code == 200
    assert isinstance(stats.json()["by_status"], dict)

    detail = client.get(f"/ops/high-res-review-requests/{rid}", headers=oh)
    assert detail.status_code == 200


def test_create_from_ocr_quality_anchor(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "hres-qa@example.com")
    hdr = auth_headers(token)
    create_order(client, token)
    inv_copy_id = client.get("/inventory", headers=hdr).json()["items"][0]["inventory_copy_id"]
    cov_up = client.post(
        f"/inventory/{inv_copy_id}/cover-images",
        headers=hdr,
        files={"file": ("qa.png", _png(), "image/png")},
    )
    assert cov_up.status_code == 200
    cov_id = cov_up.json()["id"]

    qa = CoverImageOcrQualityAnalysis(
        cover_image_id=cov_id,
        source_ocr_result_id=None,
        quality_type="low_resolution",
        deterministic_score=0.2,
        severity="critical",
        detail_json={"t": True},
        extraction_version="p34-03-tests",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(qa)
    session.commit()
    session.refresh(qa)

    rsp = client.post(
        "/high-res-review-requests",
        headers=hdr,
        json={"source_ocr_quality_analysis_id": int(qa.id or 0), "request_reason": "failed_ocr"},
    )
    assert rsp.status_code == 200
    assert rsp.json()["source_cover_scan"]["id"] == cov_id


def test_create_from_scan_session_item_anchor(client: TestClient) -> None:
    token = register_and_login(client, "hres-sess-it@example.com")
    hdr = auth_headers(token)
    create_order(client, token)
    inv_copy_id = client.get("/inventory", headers=hdr).json()["items"][0]["inventory_copy_id"]

    sid = client.post("/scan-sessions", json={"session_type": "bulk_ingest"}, headers=hdr).json()["id"]
    assert (
        _post_ingest(
            client,
            hdr,
            sid,
            [("feeder.tif", _png())],
            [{"inventory_copy_id": inv_copy_id, "source_filename": "x.tif"}],
        ).status_code
        == 200
    )
    item_id = client.get(f"/scan-sessions/{sid}/items", headers=hdr).json()["items"][0]["id"]

    rsp = client.post(
        "/high-res-review-requests",
        headers=hdr,
        json={"source_scan_session_item_id": item_id, "request_reason": "manual_review"},
    )
    assert rsp.status_code == 200
