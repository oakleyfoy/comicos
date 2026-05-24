"""P34-01 deterministic scan-session ledger (lifecycle, ordering, statistics; no OCR/mutation pipelines)."""

from fastapi.testclient import TestClient

from app.core.config import get_settings
from test_inventory import auth_headers, create_order, register_and_login


def _sha(hex_len: str) -> str:
    return hex_len.lower()


def test_scan_session_detail_orders_items_deterministically(client: TestClient) -> None:
    token = register_and_login(client, "scan-session-order@example.com")
    hdr = auth_headers(token)
    sess = client.post("/scan-sessions", json={"session_type": "bulk_ingest"}, headers=hdr)
    assert sess.status_code == 201
    sid = sess.json()["id"]

    append = client.post(
        f"/scan-sessions/{sid}/items",
        json={
            "items": [
                {"source_filename": "c.tif"},
                {"source_filename": "a.tif"},
            ]
        },
        headers=hdr,
    )
    assert append.status_code == 200

    append2 = client.post(
        f"/scan-sessions/{sid}/items",
        json={"items": [{"source_filename": "b.tif"}]},
        headers=hdr,
    )
    assert append2.status_code == 200

    detail = client.get(f"/scan-sessions/{sid}", headers=hdr)
    assert detail.status_code == 200
    body = detail.json()
    names = [i["source_filename"] for i in body["items"]]
    assert names == ["c.tif", "a.tif", "b.tif"]

    indexes = [(i["sequence_index"], i["id"]) for i in body["items"]]
    assert indexes == sorted(indexes)


def test_scan_session_lifecycle_transitions(client: TestClient) -> None:
    token = register_and_login(client, "scan-session-life@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={"session_type": "manual_upload"}, headers=hdr).json()["id"]

    assert client.post(f"/scan-sessions/{sid}/pause", headers=hdr).status_code == 400

    start = client.post(f"/scan-sessions/{sid}/start", headers=hdr)
    assert start.status_code == 200
    assert start.json()["status"] == "active"

    paused = client.post(f"/scan-sessions/{sid}/pause", headers=hdr)
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"

    restarted = client.post(f"/scan-sessions/{sid}/start", headers=hdr)
    assert restarted.status_code == 200
    assert restarted.json()["status"] == "active"

    complete = client.post(f"/scan-sessions/{sid}/complete", headers=hdr)
    assert complete.status_code == 200
    assert complete.json()["status"] == "completed"


def test_complete_maps_to_completed_with_errors_when_any_failed_item(client: TestClient) -> None:
    token = register_and_login(client, "scan-session-errs@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={}, headers=hdr).json()["id"]
    append = client.post(
        f"/scan-sessions/{sid}/items",
        json={"items": [{"source_filename": "bad.tif"}]},
        headers=hdr,
    )
    assert append.status_code == 200
    item_id = append.json()["items"][0]["id"]

    client.post(f"/scan-sessions/{sid}/start", headers=hdr)
    patch = client.patch(
        f"/scan-sessions/{sid}/items/{item_id}",
        json={"ingest_status": "failed", "ingest_error": "read error"},
        headers=hdr,
    )
    assert patch.status_code == 200

    done = client.post(f"/scan-sessions/{sid}/complete", headers=hdr)
    assert done.status_code == 200
    assert done.json()["status"] == "completed_with_errors"


def test_cancel_blocks_append_but_preserves_items(client: TestClient) -> None:
    token = register_and_login(client, "scan-session-cancel@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={}, headers=hdr).json()["id"]
    client.post(
        f"/scan-sessions/{sid}/items",
        json={"items": [{"source_filename": "keep.tif"}]},
        headers=hdr,
    )

    canceled = client.post(f"/scan-sessions/{sid}/cancel", headers=hdr)
    assert canceled.status_code == 200
    assert canceled.json()["status"] == "cancelled"

    blocked = client.post(
        f"/scan-sessions/{sid}/items",
        json={"items": [{"source_filename": "later.tif"}]},
        headers=hdr,
    )
    assert blocked.status_code == 400

    detail = client.get(f"/scan-sessions/{sid}", headers=hdr)
    assert detail.status_code == 200
    assert len(detail.json()["items"]) == 1


def test_statistics_duplicate_filename_and_hash_rollups(client: TestClient) -> None:
    token = register_and_login(client, "scan-session-dup@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={}, headers=hdr).json()["id"]
    h = _sha("a" * 64)

    payload = {
        "items": [
            {"source_filename": "same.tif", "image_width": 100, "image_height": 200, "image_sha256": h},
            {"source_filename": "same.tif", "image_width": 300, "image_height": 400, "image_sha256": h},
            {"source_filename": "unique.tif", "image_sha256": _sha("b" * 64)},
        ]
    }

    rsp = client.post(f"/scan-sessions/{sid}/items", json=payload, headers=hdr)
    assert rsp.status_code == 200
    stats = rsp.json()["statistics"]
    assert stats["duplicate_filename_groups"] == 1
    assert stats["duplicate_filename_excess_rows"] == 1
    assert stats["duplicate_image_hash_groups"] == 1
    assert stats["duplicate_image_hash_excess_rows"] == 1
    assert stats["average_image_width"] > 180
    assert stats["average_image_height"] > 280


def test_invalid_ingest_transition_rejected(client: TestClient) -> None:
    token = register_and_login(client, "scan-session-badtrans@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={}, headers=hdr).json()["id"]
    item_id = (
        client.post(
            f"/scan-sessions/{sid}/items",
            json={"items": [{"source_filename": "one.tif"}]},
            headers=hdr,
        )
        .json()
        .get("items", [{}])[0]
        .get("id")
    )

    deny = client.patch(
        f"/scan-sessions/{sid}/items/{item_id}",
        json={"ingest_status": "ocr_complete"},
        headers=hdr,
    )
    assert deny.status_code == 400


def test_inventory_book_metadata_stable_across_scan_session_writes(client: TestClient) -> None:
    token = register_and_login(client, "scan-session-meta@example.com")
    hdr = auth_headers(token)
    create_order(client, token)
    inventory = client.get("/inventory", headers=hdr).json()
    inv_copy_id = inventory["items"][0]["inventory_copy_id"]

    before_title = inventory["items"][0]["title"]

    sid = client.post("/scan-sessions", json={}, headers=hdr).json()["id"]
    client.post(
        f"/scan-sessions/{sid}/items",
        json={"items": [{"inventory_copy_id": inv_copy_id, "source_filename": "x.tif"}]},
        headers=hdr,
    )
    client.post(f"/scan-sessions/{sid}/start", headers=hdr)
    detail = client.get(f"/inventory/{inv_copy_id}", headers=hdr)
    assert detail.status_code == 200
    assert detail.json()["title"] == before_title


def test_ops_scan_sessions_cross_owner(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-scan@example.com")
    get_settings.cache_clear()

    alice = register_and_login(client, "alice-scan@example.com")
    bob = register_and_login(client, "bob-scan@example.com")
    alice_hdr = auth_headers(alice)
    bob_hdr = auth_headers(bob)

    alice_sid = client.post("/scan-sessions", json={}, headers=alice_hdr).json()["id"]
    bob_sid = client.post("/scan-sessions", json={}, headers=bob_hdr).json()["id"]

    ops_token = register_and_login(client, "ops-scan@example.com")
    ops_hdr = auth_headers(ops_token)

    lst = client.get("/ops/scan-sessions?limit=100", headers=ops_hdr).json()
    ids = [s["id"] for s in lst["sessions"]]
    assert alice_sid in ids
    assert bob_sid in ids


def test_owner_sessions_isolated(client: TestClient) -> None:
    a = register_and_login(client, "owner-a-scan@example.com")
    b = register_and_login(client, "owner-b-scan@example.com")

    theirs = client.post("/scan-sessions", json={}, headers=auth_headers(b)).json()
    steal = client.get(f"/scan-sessions/{theirs['id']}", headers=auth_headers(a))
    assert steal.status_code == 404


def test_originating_scan_surface_on_inventory_detail_when_linked(client: TestClient) -> None:
    token = register_and_login(client, "scan-orig-inventory@example.com")
    hdr = auth_headers(token)
    create_order(client, token)

    inventory = client.get("/inventory", headers=hdr).json()
    ic = inventory["items"][0]["inventory_copy_id"]

    sid = client.post("/scan-sessions", json={"session_type": "bulk_ingest"}, headers=hdr).json()["id"]
    client.post(
        f"/scan-sessions/{sid}/items",
        json={"items": [{"inventory_copy_id": ic, "source_filename": "cov.tif"}]},
        headers=hdr,
    )

    detail = client.get(f"/inventory/{ic}", headers=hdr)
    assert detail.status_code == 200
    origin = detail.json().get("originating_scan_session")
    assert origin is not None
    assert origin["scan_session_id"] == sid
    assert origin["session_type"] == "bulk_ingest"


def test_rerun_safe_append_keeps_prior_failed_history(client: TestClient) -> None:
    token = register_and_login(client, "scan-rerun@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={}, headers=hdr).json()["id"]

    client.post(
        f"/scan-sessions/{sid}/items",
        json={"items": [{"source_filename": "dead.tif"}, {"source_filename": "later.tif"}]},
        headers=hdr,
    )

    detail1 = client.get(f"/scan-sessions/{sid}", headers=hdr).json()
    assert len(detail1["items"]) == 2

    bad_id = detail1["items"][0]["id"]
    ok_row = detail1["items"][1]

    client.post(f"/scan-sessions/{sid}/start", headers=hdr)
    client.patch(
        f"/scan-sessions/{sid}/items/{bad_id}",
        json={"ingest_status": "failed", "ingest_error": "timeout"},
        headers=hdr,
    )

    rer = client.post(
        f"/scan-sessions/{sid}/items",
        json={"items": [{"source_filename": "recovery.tif"}]},
        headers=hdr,
    )
    assert rer.status_code == 200

    refreshed = rer.json()
    assert len(refreshed["items"]) == 3
    assert refreshed["failed_items"] == 1
    statuses = {(i["id"], i["ingest_status"], i.get("ingest_error")) for i in refreshed["items"]}
    assert (bad_id, "failed", "timeout") in statuses
    assert refreshed["statistics"]["failures"] == 1
    assert any(i["id"] == ok_row["id"] and i["ingest_status"] == "pending" for i in refreshed["items"])


def test_ops_can_fetch_any_session_detail(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-detail@example.com")
    get_settings.cache_clear()

    owner_token = register_and_login(client, "owner-detail-scan@example.com")
    hdr = auth_headers(owner_token)
    sid = client.post("/scan-sessions", json={}, headers=hdr).json()["id"]
    ops_token = register_and_login(client, "ops-detail@example.com")
    body = client.get(f"/ops/scan-sessions/{sid}", headers=auth_headers(ops_token)).json()
    assert body["id"] == sid