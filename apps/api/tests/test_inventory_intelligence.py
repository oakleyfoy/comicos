from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.services.inventory_intelligence import (
    classify_inventory_health,
    normalize_ownership_state,
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


def create_order(
    client: TestClient,
    token: str,
    *,
    items: list[dict],
) -> dict:
    payload = {
        "retailer": "Whatnot",
        "order_date": "2026-05-19",
        "source_type": "manual",
        "shipping_amount": 0,
        "tax_amount": 0,
        "items": items,
    }
    response = client.post("/orders", json=payload, headers=auth_headers(token))
    assert response.status_code == 201
    return response.json()


def test_normalize_ownership_priority_cancelled_then_received_ts() -> None:
    dt = datetime(2026, 1, 1, tzinfo=UTC)
    assert (
        normalize_ownership_state(release_status="released", order_status="cancelled", received_at=None)
        == "cancelled"
    )
    assert (
        normalize_ownership_state(
            release_status="released",
            order_status="received",
            received_at=None,
        )
        == "in_hand"
    )
    assert (
        normalize_ownership_state(release_status="released", order_status="ordered", received_at=dt) == "in_hand"
    )


def test_normalize_ownership_preorder_vs_ordered_pipeline() -> None:
    assert (
        normalize_ownership_state(
            release_status="not_released_yet",
            order_status="ordered",
            received_at=None,
        )
        == "preorder"
    )
    assert (
        normalize_ownership_state(
            release_status="released",
            order_status="preordered",
            received_at=None,
        )
        == "preorder"
    )
    assert (
        normalize_ownership_state(release_status="released", order_status="shipped", received_at=None)
        == "ordered_not_received"
    )


def test_classify_cancelled_always_blocked_even_with_review_signals() -> None:
    assert (
        classify_inventory_health(
            ownership="cancelled",
            has_cover_scan=True,
            preorder_miss_cal=False,
            cover_processing_failed=True,
            ocr_failed=True,
            open_conflict=True,
            pending_canonical=True,
            dup_inventory_pending=True,
            probable_dup_cluster=True,
            probable_vf_cluster=True,
            ocr_complete=False,
        )
        == "blocked"
    )


def test_classify_preorder_calendar_gap_incomplete() -> None:
    health = classify_inventory_health(
        ownership="preorder",
        has_cover_scan=False,
        preorder_miss_cal=True,
        cover_processing_failed=False,
        ocr_failed=False,
        open_conflict=False,
        pending_canonical=False,
        dup_inventory_pending=False,
        probable_dup_cluster=False,
        probable_vf_cluster=False,
        ocr_complete=False,
    )
    assert health in {"incomplete", "needs_review"}


def test_owner_intel_endpoints_aggregate(client: TestClient) -> None:
    token = register_and_login(client, "intel-roll@example.com")
    create_order(
        client,
        token,
        items=[
            {
                "title": "Echo",
                "publisher": "Image",
                "issue_number": "1",
                "cover_name": None,
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 10.00,
                "release_status": "released",
                "order_status": "received",
            },
        ],
    )

    summary = client.get("/inventory-intelligence/summary", headers=auth_headers(token)).json()
    health = client.get("/inventory-intelligence/health", headers=auth_headers(token)).json()
    breakdown = client.get("/inventory-intelligence/breakdown", headers=auth_headers(token)).json()

    assert summary["total_inventory_copies"] >= 1
    assert summary["ownership_in_hand"] >= 1
    assert isinstance(summary["cover_processing_failed_copies"], int)
    assert isinstance(summary["ocr_failed_copies"], int)
    sum_health = (
        health["healthy"] + health["needs_review"] + health["incomplete"] + health["blocked"]
    )
    assert sum_health >= 1

    dims = breakdown["by_publisher"]
    keys = ["by_publisher", "by_year", "by_release_status", "by_order_status", "by_grade_status"]
    assert all(dim in breakdown for dim in keys)
    assert breakdown["by_ownership_state"]
    assert len(dims) >= 1


def test_inventory_list_merges_intelligence_signals(client: TestClient) -> None:
    token = register_and_login(client, "intel-list-merge@example.com")
    create_order(
        client,
        token,
        items=[
            {
                "title": "Blade Runner",
                "publisher": "Titan",
                "issue_number": "12",
                "cover_name": "A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 4.50,
                "release_status": "released",
                "order_status": "received",
            },
        ],
    )
    listing = client.get("/inventory?page=1&page_size=10", headers=auth_headers(token)).json()
    assert listing["total"] == 1
    row = listing["items"][0]
    intel = row.get("inventory_intelligence")
    assert intel is not None
    assert intel["ownership_state"] == "in_hand"
    assert intel["inventory_health"] in {"healthy", "needs_review", "incomplete", "blocked"}
    assert "has_cover_scan" in intel


def test_intel_inventory_query_filters_combine_with_signals(client: TestClient) -> None:
    token = register_and_login(client, "intel-filter-health@example.com")
    create_order(
        client,
        token,
        items=[
            {
                "title": "Nova",
                "publisher": "Marvel",
                "issue_number": "1",
                "cover_name": None,
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 2,
                "raw_item_price": 3,
                "release_status": "released",
                "order_status": "received",
            },
            {
                "title": "Cancelled Book",
                "publisher": "Marvel",
                "issue_number": "2",
                "cover_name": None,
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 3,
                "release_status": "released",
                "order_status": "cancelled",
            },
        ],
    )

    unhealthy = client.get(
        "/inventory?page=1&page_size=10&intelligence_health=not_healthy",
        headers=auth_headers(token),
    ).json()
    healthy_only = client.get(
        "/inventory?page=1&page_size=10&intelligence_health=healthy",
        headers=auth_headers(token),
    ).json()
    preorder_only = client.get(
        "/inventory?page=1&page_size=10&ownership_intel=cancelled",
        headers=auth_headers(token),
    ).json()

    assert preorder_only["total"] == 1
    preorder_intel = preorder_only["items"][0]["inventory_intelligence"]
    assert preorder_intel["ownership_state"] == "cancelled"

    if healthy_only["total"] >= 1:
        assert healthy_only["items"][0]["inventory_intelligence"]["ownership_state"] == "in_hand"
        unhealthy_ids = {row["inventory_copy_id"] for row in unhealthy["items"]}
        healthy_ids = {row["inventory_copy_id"] for row in healthy_only["items"]}
        assert not unhealthy_ids & healthy_ids


def test_intel_rollups_invoke_compute_without_changing_inventory_rows(client: TestClient) -> None:
    token = register_and_login(client, "intel-http-stable@example.com")
    create_order(
        client,
        token,
        items=[
            {
                "title": "HTTP Stable Rollup",
                "publisher": "Valiant",
                "issue_number": "1",
                "cover_name": None,
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 5,
                "release_status": "released",
                "order_status": "shipped",
            },
        ],
    )

    snapshot = client.get("/inventory?page=1&page_size=10", headers=auth_headers(token)).json()

    client.get("/inventory-intelligence/summary", headers=auth_headers(token))
    client.get("/inventory-intelligence/health", headers=auth_headers(token))
    client.get("/inventory-intelligence/breakdown", headers=auth_headers(token))
    client.get("/inventory-intelligence/summary", headers=auth_headers(token))

    after_listing = client.get("/inventory?page=1&page_size=10", headers=auth_headers(token)).json()

    assert snapshot["total"] == after_listing["total"]
    keyed_before = {(row["inventory_copy_id"], row["order_status"], row["release_status"]) for row in snapshot["items"]}
    keyed_after = {
        (row["inventory_copy_id"], row["order_status"], row["release_status"]) for row in after_listing["items"]
    }
    assert keyed_before == keyed_after


def test_ops_intel_endpoints_require_admin_stub(client: TestClient) -> None:
    resp = client.get("/ops/inventory-intelligence/summary")
    assert resp.status_code in {401, 403}
