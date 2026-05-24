from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import DuplicateCandidateReview, InventoryCopy
from app.services.duplicate_ownership_intelligence import (
    _component_group_key,
    classify_duplicate_ownership,
)


def register_and_login(client: TestClient, email: str) -> str:
    client.post(
        "/auth/register",
        json={"email": email, "password": "supersecret123"},
    )
    response = client.post(
        "/auth/login",
        json={"email": email, "password": "supersecret123"},
    )
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def build_order_payload(*, quantity: int = 2) -> dict:
    return {
        "retailer": "Whatnot",
        "order_date": "2026-05-19",
        "source_type": "manual",
        "shipping_amount": 0.00,
        "tax_amount": 0.00,
        "items": [
            {
                "title": "Invincible",
                "publisher": "Image",
                "issue_number": "1",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": quantity,
                "raw_item_price": 7.65,
            }
        ],
    }


def test_classify_preorder_plus_owned() -> None:
    assert (
        classify_duplicate_ownership(
            preorder_and_in_hand=True,
            graded_and_raw=False,
            pending_dup_review_touch=False,
            duplicate_scan_exact=False,
            human_dup_scan_pair=False,
            human_same_cover=False,
            touches_dup_cluster=False,
            overlaps_probable_cluster_only=False,
            raw_members=2,
            canonical_duplicate_scan_hint=False,
        )
        == "preorder_plus_owned"
    )


def test_classify_graded_plus_raw() -> None:
    assert (
        classify_duplicate_ownership(
            preorder_and_in_hand=False,
            graded_and_raw=True,
            pending_dup_review_touch=False,
            duplicate_scan_exact=False,
            human_dup_scan_pair=False,
            human_same_cover=False,
            touches_dup_cluster=False,
            overlaps_probable_cluster_only=False,
            raw_members=1,
            canonical_duplicate_scan_hint=False,
        )
        == "graded_plus_raw"
    )


def test_classify_duplicate_scan_only_exact_scan() -> None:
    assert (
        classify_duplicate_ownership(
            preorder_and_in_hand=False,
            graded_and_raw=False,
            pending_dup_review_touch=False,
            duplicate_scan_exact=True,
            human_dup_scan_pair=False,
            human_same_cover=False,
            touches_dup_cluster=True,
            overlaps_probable_cluster_only=False,
            raw_members=2,
            canonical_duplicate_scan_hint=False,
        )
        == "duplicate_scan_only"
    )


def test_classify_duplicate_scan_only_human_dup_pair() -> None:
    assert (
        classify_duplicate_ownership(
            preorder_and_in_hand=False,
            graded_and_raw=False,
            pending_dup_review_touch=False,
            duplicate_scan_exact=False,
            human_dup_scan_pair=True,
            human_same_cover=False,
            touches_dup_cluster=False,
            overlaps_probable_cluster_only=False,
            raw_members=2,
            canonical_duplicate_scan_hint=False,
        )
        == "duplicate_scan_only"
    )


def test_classify_probable_accidental_raw_heavy_with_cluster_touch() -> None:
    assert (
        classify_duplicate_ownership(
            preorder_and_in_hand=False,
            graded_and_raw=False,
            pending_dup_review_touch=False,
            duplicate_scan_exact=False,
            human_dup_scan_pair=False,
            human_same_cover=False,
            touches_dup_cluster=True,
            overlaps_probable_cluster_only=False,
            raw_members=3,
            canonical_duplicate_scan_hint=False,
        )
        == "probable_accidental_duplicate"
    )


def test_group_key_is_deterministic_for_sorted_ids() -> None:
    key_a = _component_group_key([3, 1, 2])
    key_b = _component_group_key([1, 2, 3])
    assert key_a == key_b
    assert key_a.startswith("own_dup:")


def test_owner_preorder_plus_owned_http(client: TestClient) -> None:
    token = register_and_login(client, "dup-own-preorder@example.com")
    assert client.post("/orders", json=build_order_payload(quantity=2), headers=auth_headers(token)).status_code == 201
    listing = client.get("/inventory?page=1&page_size=10", headers=auth_headers(token)).json()
    assert listing["total"] == 2
    ids_sorted = sorted(row["inventory_copy_id"] for row in listing["items"])
    lower_id, higher_id = ids_sorted[0], ids_sorted[1]

    patch_preorder = client.patch(
        f"/inventory/{lower_id}",
        headers=auth_headers(token),
        json={"release_status": "not_released_yet", "order_status": "ordered"},
    )
    patch_received = client.patch(
        f"/inventory/{higher_id}",
        headers=auth_headers(token),
        json={"release_status": "released", "order_status": "received"},
    )
    assert patch_preorder.status_code == 200
    assert patch_received.status_code == 200

    dup_resp = client.get("/duplicate-ownership", headers=auth_headers(token))
    assert dup_resp.status_code == 200
    body = dup_resp.json()
    assert body["summary"]["total_groups"] == 1
    assert body["summary"]["preorder_plus_owned_groups"] == 1
    assert body["groups"][0]["classification"] == "preorder_plus_owned"


def test_owner_graded_plus_raw_http(client: TestClient) -> None:
    token = register_and_login(client, "dup-own-grade@example.com")
    assert client.post("/orders", json=build_order_payload(quantity=2), headers=auth_headers(token)).status_code == 201
    listing = client.get("/inventory?page=1&page_size=10", headers=auth_headers(token)).json()
    ids_sorted = sorted(row["inventory_copy_id"] for row in listing["items"])
    patch_a = client.patch(
        f"/inventory/{ids_sorted[0]}",
        headers=auth_headers(token),
        json={"grade_status": "raw"},
    )
    patch_b = client.patch(
        f"/inventory/{ids_sorted[1]}",
        headers=auth_headers(token),
        json={"grade_status": "graded"},
    )
    assert patch_a.status_code == 200 and patch_b.status_code == 200

    dup_resp = client.get("/duplicate-ownership", headers=auth_headers(token))
    assert dup_resp.status_code == 200
    body = dup_resp.json()
    assert body["summary"]["total_groups"] == 1
    assert body["summary"]["graded_plus_raw_groups"] == 1
    assert body["groups"][0]["classification"] == "graded_plus_raw"


def test_unresolved_duplicate_when_pending_inventory_review_http(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "dup-own-review@example.com")
    assert client.post("/orders", json=build_order_payload(quantity=2), headers=auth_headers(token)).status_code == 201
    identity_key = session.exec(select(InventoryCopy.metadata_identity_key)).first()
    assert identity_key
    key = str(identity_key)
    session.add(DuplicateCandidateReview(metadata_identity_key=key, review_status="pending"))
    session.commit()

    dup_resp = client.get("/duplicate-ownership", headers=auth_headers(token))
    assert dup_resp.status_code == 200
    body = dup_resp.json()
    assert body["summary"]["unresolved_duplicate_groups"] == 1
    assert body["groups"][0]["classification"] == "unresolved_duplicate"


def test_inventory_list_includes_duplicate_ownership_attachment(client: TestClient) -> None:
    token = register_and_login(client, "dup-own-attach@example.com")
    assert client.post("/orders", json=build_order_payload(quantity=2), headers=auth_headers(token)).status_code == 201
    listing = client.get("/inventory?page=1&page_size=10", headers=auth_headers(token)).json()
    for row in listing["items"]:
        attach = row.get("duplicate_ownership")
        assert attach is not None
        assert attach["group_key"].startswith("own_dup:")
        assert isinstance(attach["sibling_inventory_copy_ids"], list)


def test_duplicate_intel_http_is_idempotent_on_inventory_metadata(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "dup-own-idem@example.com")
    assert client.post("/orders", json=build_order_payload(quantity=2), headers=auth_headers(token)).status_code == 201
    before = {
        (int(c.id), c.metadata_identity_key, c.grade_status)
        for c in session.exec(select(InventoryCopy)).all()
    }
    assert client.get("/duplicate-ownership", headers=auth_headers(token)).status_code == 200
    after = {
        (int(c.id), c.metadata_identity_key, c.grade_status)
        for c in session.exec(select(InventoryCopy)).all()
    }
    assert before == after


def test_duplicate_ownership_detail_round_trip(client: TestClient) -> None:
    token = register_and_login(client, "dup-own-detail@example.com")
    assert client.post("/orders", json=build_order_payload(quantity=2), headers=auth_headers(token)).status_code == 201
    listing = client.get("/duplicate-ownership", headers=auth_headers(token)).json()
    group_key = listing["groups"][0]["group_key"]
    detail = client.get(f"/duplicate-ownership/{group_key}", headers=auth_headers(token))
    assert detail.status_code == 200
    assert detail.json()["group_key"] == group_key


def test_ops_duplicate_ownership_requires_admin(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-dup-owner@example.com")
    from app.core.config import get_settings

    get_settings.cache_clear()
    token = register_and_login(client, "ops-dup-owner@example.com")
    resp = client.get("/ops/duplicate-ownership", headers=auth_headers(token))
    assert resp.status_code == 200
    assert "summary" in resp.json()
    get_settings.cache_clear()
