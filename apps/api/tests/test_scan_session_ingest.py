"""P34-02 deterministic Fujitsu-style batch ingest (multipart scans → session items; no OCR / no inferred inventory)."""

from __future__ import annotations

import io
import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import CoverImage, CoverImageOcrResult
from test_inventory import auth_headers, create_order, register_and_login


def _png_bytes(rgb: tuple[int, int, int] = (10, 20, 30), *, size: tuple[int, int] = (42, 64)) -> bytes:
    img = Image.new("RGB", size, rgb)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _post_ingest(
    client: TestClient,
    hdr: dict[str, str],
    session_id: int,
    file_payloads: list[tuple[str, bytes]],
    manifest_items: list[dict[str, Any]],
) -> Any:
    files = [
        ("files", (fname, blob, "image/png"))
        for fname, blob in file_payloads
    ]
    data = {"manifest": json.dumps({"items": manifest_items})}
    return client.post(
        f"/scan-sessions/{session_id}/ingest-files",
        headers=hdr,
        files=files,
        data=data,
    )


def _count_cover_images(session: Session) -> int:
    return len(session.exec(select(CoverImage)).all())


def test_ingest_valid_png_sets_imported_and_dimensions(client: TestClient) -> None:
    token = register_and_login(client, "fuj.ingest-valid@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={"session_type": "bulk_ingest"}, headers=hdr).json()["id"]
    png = _png_bytes()
    rsp = _post_ingest(client, hdr, sid, [("cover.png", png)], [{}])
    assert rsp.status_code == 200

    lst = client.get(f"/scan-sessions/{sid}/items", headers=hdr).json()
    assert lst["statistics"]["total_scans"] == 1
    assert lst["statistics"]["failures"] == 0
    row = lst["items"][0]
    assert row["ingest_status"] == "imported"
    assert row["image_width"] == 42
    assert row["image_height"] == 64
    assert row["image_sha256"] and len(row["image_sha256"]) == 64
    assert row["cover_image_id"] is None


def test_ingest_corrupt_then_valid_keeps_batch(client: TestClient) -> None:
    token = register_and_login(client, "fuj.ingest-mix@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={"session_type": "bulk_ingest"}, headers=hdr).json()["id"]
    good = _png_bytes()
    rsp = _post_ingest(
        client,
        hdr,
        sid,
        [("bad.tif", b"NOT-A-REAL-IMAGE"), ("fixed.png", good)],
        [{}, {}],
    )
    assert rsp.status_code == 200

    lst = client.get(f"/scan-sessions/{sid}/items", headers=hdr).json()
    seqs = [r["sequence_index"] for r in lst["items"]]
    assert seqs == sorted(seqs)
    assert lst["statistics"]["failures"] == 1

    failures = [r for r in lst["items"] if r["ingest_status"] == "failed"]
    assert len(failures) == 1
    imported = [r for r in lst["items"] if r["ingest_status"] == "imported"]
    assert len(imported) == 1


def test_deterministic_sequence_explicit_indices(client: TestClient) -> None:
    token = register_and_login(client, "fuj.ingest-seq@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={"session_type": "bulk_ingest"}, headers=hdr).json()["id"]
    a = _png_bytes((1, 0, 0), size=(11, 12))
    b = _png_bytes((0, 1, 0), size=(13, 14))
    rsp = _post_ingest(
        client,
        hdr,
        sid,
        [("first.tif", a), ("second.tif", b)],
        [{"sequence_index": 5}, {"sequence_index": 2}],
    )
    assert rsp.status_code == 200
    lst = client.get(f"/scan-sessions/{sid}/items", headers=hdr).json()
    indexes = {(r["source_filename"], r["sequence_index"]) for r in lst["items"]}
    assert ("first.tif", 5) in indexes
    assert ("second.tif", 2) in indexes


def test_auto_sequence_allocated_in_feeder_order(client: TestClient) -> None:
    token = register_and_login(client, "fuj.ingest-auto-seq@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={"session_type": "bulk_ingest"}, headers=hdr).json()["id"]
    rsp = _post_ingest(
        client,
        hdr,
        sid,
        [
            ("a.png", _png_bytes((1, 1, 1))),
            ("b.png", _png_bytes((2, 2, 2))),
        ],
        [{}, {}],
    )
    assert rsp.status_code == 200
    lst = client.get(f"/scan-sessions/{sid}/items", headers=hdr).json()
    lookup = {r["source_filename"]: r["sequence_index"] for r in lst["items"]}
    assert lookup["a.png"] == 0
    assert lookup["b.png"] == 1


def test_duplicate_source_filename_rollups_when_hashes_differ(client: TestClient) -> None:
    token = register_and_login(client, "fuj.ingest-dupname@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={"session_type": "bulk_ingest"}, headers=hdr).json()["id"]
    rsp = _post_ingest(
        client,
        hdr,
        sid,
        [
            ("slot1.tif", _png_bytes((255, 0, 0))),
            ("slot2.tif", _png_bytes((0, 255, 0))),
        ],
        [
            {"source_filename": "FEED.tif"},
            {"source_filename": "FEED.tif"},
        ],
    )
    assert rsp.status_code == 200
    lst = client.get(f"/scan-sessions/{sid}/items", headers=hdr).json()
    assert lst["statistics"]["duplicate_filename_groups"] >= 1
    assert lst["statistics"]["duplicate_filename_excess_rows"] >= 1


def test_duplicate_sha256_same_source_filename_skips_second_ingest(client: TestClient) -> None:
    token = register_and_login(client, "fuj.ingest-dup-hash@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={"session_type": "bulk_ingest"}, headers=hdr).json()["id"]
    png = _png_bytes()
    r1 = _post_ingest(client, hdr, sid, [("one.tif", png)], [{"source_filename": "dup.tif"}])
    assert r1.status_code == 200

    lst1 = client.get(f"/scan-sessions/{sid}/items", headers=hdr).json()
    assert lst1["statistics"]["total_scans"] == 1

    r2 = _post_ingest(client, hdr, sid, [("ignored-name.tif", png)], [{"source_filename": "dup.tif"}])
    assert r2.status_code == 200
    lst2 = client.get(f"/scan-sessions/{sid}/items", headers=hdr).json()
    assert lst2["statistics"]["total_scans"] == 1


def test_duplicate_bytes_different_normalized_filename_creates_second_row(client: TestClient) -> None:
    token = register_and_login(client, "fuj.ingest-dupbytes-two-names@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={"session_type": "bulk_ingest"}, headers=hdr).json()["id"]
    png = _png_bytes()
    r1 = _post_ingest(client, hdr, sid, [("a.tif", png)], [{}])
    assert r1.status_code == 200
    r2 = _post_ingest(client, hdr, sid, [("b.tif", png)], [{}])
    assert r2.status_code == 200
    lst = client.get(f"/scan-sessions/{sid}/items", headers=hdr).json()
    imported = [r for r in lst["items"] if r["ingest_status"] == "imported"]
    assert len(imported) == 2
    hashes = {r["image_sha256"] for r in imported}
    assert len(hashes) == 1


def test_explicit_inventory_manifest_attaches_cover_image(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "fuj.ingest-inv-cover@example.com")
    hdr = auth_headers(token)
    create_order(client, token)
    inv_copy_id = client.get("/inventory", headers=hdr).json()["items"][0]["inventory_copy_id"]
    before_cover_count = _count_cover_images(session)

    sid = client.post("/scan-sessions", json={"session_type": "bulk_ingest"}, headers=hdr).json()["id"]
    png = _png_bytes()

    rsp = _post_ingest(
        client,
        hdr,
        sid,
        [("scan.tif", png)],
        [{"inventory_copy_id": inv_copy_id, "source_filename": "explicit.tif"}],
    )
    assert rsp.status_code == 200

    lst = client.get(f"/scan-sessions/{sid}/items", headers=hdr).json()
    row = lst["items"][0]
    assert row["inventory_copy_id"] == inv_copy_id
    assert row["cover_image_id"] is not None
    assert row["cover_image_id"] >= 1
    assert _count_cover_images(session) == before_cover_count + 1

    rerun = _post_ingest(
        client,
        hdr,
        sid,
        [("scan.tif", png)],
        [{"inventory_copy_id": inv_copy_id, "source_filename": "explicit.tif"}],
    )
    assert rerun.status_code == 200
    assert _count_cover_images(session) == before_cover_count + 1


def test_no_manifest_inventory_inventory_copy_none(client: TestClient) -> None:
    token = register_and_login(client, "fuj.ingest-no-inv@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={"session_type": "bulk_ingest"}, headers=hdr).json()["id"]

    rsp = _post_ingest(client, hdr, sid, [("solo.png", _png_bytes())], [{}])
    assert rsp.status_code == 200
    lst = client.get(f"/scan-sessions/{sid}/items", headers=hdr).json()
    assert lst["items"][0]["inventory_copy_id"] is None


def test_inventory_book_metadata_stable_after_ingest(client: TestClient) -> None:
    token = register_and_login(client, "fuj.ingest-meta@example.com")
    hdr = auth_headers(token)
    create_order(client, token)

    invent = client.get("/inventory", headers=hdr).json()
    copy_id = invent["items"][0]["inventory_copy_id"]
    before_title = invent["items"][0]["title"]

    sid = client.post("/scan-sessions", json={"session_type": "bulk_ingest"}, headers=hdr).json()["id"]
    assert (
        _post_ingest(
            client,
            hdr,
            sid,
            [("note.png", _png_bytes())],
            [{}],
        ).status_code
        == 200
    )
    assert (
        _post_ingest(
            client,
            hdr,
            sid,
            [("linked.tif", _png_bytes((9, 9, 9)))],
            [{"inventory_copy_id": copy_id}],
        ).status_code
        == 200
    )

    after = client.get(f"/inventory/{copy_id}", headers=hdr).json()
    assert after["title"] == before_title


def test_cover_created_with_inventory_keeps_processing_pending_without_ocr_enqueue(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "fuj.ingest-pending-cover@example.com")
    hdr = auth_headers(token)
    create_order(client, token)
    inv_copy_id = client.get("/inventory", headers=hdr).json()["items"][0]["inventory_copy_id"]

    sid = client.post("/scan-sessions", json={"session_type": "bulk_ingest"}, headers=hdr).json()["id"]
    rsp = _post_ingest(
        client,
        hdr,
        sid,
        [("ocr-off.tif", _png_bytes())],
        [{"inventory_copy_id": inv_copy_id}],
    )
    assert rsp.status_code == 200
    cid = rsp.json()["items"][0]["cover_image_id"]

    cov = session.get(CoverImage, int(cid))
    assert cov is not None
    assert cov.processing_status == "pending"
    assert (
        len(
            session.exec(
                select(CoverImageOcrResult).where(CoverImageOcrResult.cover_image_id == int(cid))
            ).all()
        )
        == 0
    )


def test_sequence_index_collision_records_failed_audit_row(client: TestClient) -> None:
    token = register_and_login(client, "fuj.ingest-seq-hit@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={"session_type": "bulk_ingest"}, headers=hdr).json()["id"]
    a = _png_bytes((255, 0, 128))
    b = _png_bytes((128, 0, 255))

    rsp = _post_ingest(
        client,
        hdr,
        sid,
        [("i1.tif", a), ("i2.tif", b)],
        [{"sequence_index": 0}, {"sequence_index": 0}],
    )
    assert rsp.status_code == 200

    lst = sorted(
        client.get(f"/scan-sessions/{sid}/items", headers=hdr).json()["items"],
        key=lambda r: int(r["id"]),
    )
    statuses = {(r["ingest_status"], r["sequence_index"]) for r in lst}
    assert ("imported", 0) in statuses
    fail = next(r for r in lst if r["ingest_status"] == "failed")
    assert "sequence_index 0 already occupied" in (fail["ingest_error"] or "")


def test_completed_session_blocks_multipart_ingest(client: TestClient) -> None:
    token = register_and_login(client, "fuj.ingest-term@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={"session_type": "bulk_ingest"}, headers=hdr).json()["id"]
    assert client.post(f"/scan-sessions/{sid}/start", headers=hdr).status_code == 200
    assert client.post(f"/scan-sessions/{sid}/complete", headers=hdr).status_code == 200

    blocked = _post_ingest(client, hdr, sid, [("late.png", _png_bytes())], [{}])
    assert blocked.status_code == 400


def test_ops_lists_items_without_owner_filter(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-fuj-ingest@example.com")
    get_settings.cache_clear()

    owner_tok = register_and_login(client, "owner-fuj-ingest@example.com")
    hdr_owner = auth_headers(owner_tok)
    sid = client.post("/scan-sessions", json={"session_type": "bulk_ingest"}, headers=hdr_owner).json()["id"]

    assert _post_ingest(client, hdr_owner, sid, [("ops.png", _png_bytes())], [{}]).status_code == 200

    ops_token = register_and_login(client, "ops-fuj-ingest@example.com")
    lst = client.get(
        f"/ops/scan-sessions/{sid}/items",
        headers=auth_headers(ops_token),
    )
    assert lst.status_code == 200
    body = lst.json()
    assert body["scan_session_id"] == sid
    assert body["statistics"]["total_scans"] == 1
