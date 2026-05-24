from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import CanonicalIssueLinkSuggestion, ComicIssue, CoverImage, InventoryCopy, Variant
from app.services.run_detection import parse_issue_number_for_run_detection


def register_and_login(client: TestClient, email: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "supersecret123"})
    response = client.post("/auth/login", json={"email": email, "password": "supersecret123"})
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_order(
    client: TestClient,
    token: str,
    *,
    title: str,
    issue_number: str,
    release_status: str = "released",
    order_status: str = "received",
    release_date: str | None = None,
) -> dict:
    item: dict[str, object] = {
        "title": title,
        "publisher": "Image",
        "issue_number": issue_number,
        "cover_name": "Cover A",
        "printing": None,
        "ratio": None,
        "variant_type": None,
        "cover_artist": None,
        "quantity": 1,
        "raw_item_price": 4.99,
        "release_status": release_status,
        "order_status": order_status,
    }
    if release_date is not None:
        item["release_date"] = release_date
    response = client.post(
        "/orders",
        json={
            "retailer": "Whatnot",
            "order_date": "2026-05-21",
            "source_type": "manual",
            "shipping_amount": 0,
            "tax_amount": 0,
            "items": [item],
        },
        headers=auth_headers(token),
    )
    assert response.status_code == 201
    return response.json()


def latest_inventory_id(session: Session) -> int:
    latest = session.exec(select(InventoryCopy.id).order_by(InventoryCopy.id.desc())).first()
    assert latest is not None
    return int(latest)


def issue_for_inventory(session: Session, inventory_copy_id: int) -> ComicIssue:
    issue = session.exec(
        select(ComicIssue)
        .join(Variant, Variant.comic_issue_id == ComicIssue.id)
        .join(InventoryCopy, InventoryCopy.variant_id == Variant.id)
        .where(InventoryCopy.id == inventory_copy_id)
    ).one()
    return issue
def add_pending_canonical_suggestion(session: Session, *, inventory_copy_id: int) -> None:
    inventory_copy = session.get(InventoryCopy, inventory_copy_id)
    assert inventory_copy is not None
    cover = CoverImage(
        inventory_copy_id=inventory_copy_id,
        canonical_series_id=inventory_copy.canonical_series_id,
        source_type="inventory",
        storage_path=f"tests/{inventory_copy_id}.jpg",
        mime_type="image/jpeg",
        sha256_hash=("a" * 63) + str(inventory_copy_id % 10),
        processing_status="processed",
        matching_status="ready",
    )
    session.add(cover)
    session.flush()
    session.add(
        CanonicalIssueLinkSuggestion(
            cover_image_id=int(cover.id),
            inventory_copy_id=inventory_copy_id,
            canonical_series_id=inventory_copy.canonical_series_id,
            suggestion_type="issue_number_reconciliation",
            confidence_bucket="low",
            deterministic_score=0.4,
            evidence_json={"source": "test"},
        )
    )
    session.commit()


def test_deterministic_issue_sorting_handles_integer_decimal_suffix_and_annual() -> None:
    values = ["10", "2", "Annual 1", "1A", "1.5", "1"]
    ordered = [item.display_value for item in sorted((parse_issue_number_for_run_detection(v) for v in values), key=lambda row: row.sortable_key)]
    assert ordered == ["1", "1.5", "2", "10", "1A", "Annual 1"]


def test_consecutive_issue_gap_detection(client: TestClient) -> None:
    token_a = register_and_login(client, "run-gap-a@example.com")
    token_b = register_and_login(client, "run-gap-b@example.com")
    create_order(client, token_a, title="Gap Saga", issue_number="1")
    create_order(client, token_a, title="Gap Saga", issue_number="3")
    create_order(client, token_b, title="Gap Saga", issue_number="2")

    response = client.get("/run-detection", headers=auth_headers(token_a))
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["confirmed_missing_rows"] == 1
    assert body["series_groups"][0]["series_status"] == "incomplete_limited_series"
    assert body["series_groups"][0]["missing_issues"][0]["issue_number"] == "2"
    assert body["series_groups"][0]["missing_issues"][0]["classification"] == "confirmed_missing"


def test_decimal_issue_ordering_detection(client: TestClient, session: Session) -> None:
    token_a = register_and_login(client, "run-dec-a@example.com")
    token_b = register_and_login(client, "run-dec-b@example.com")
    create_order(client, token_a, title="Decimal Saga", issue_number="1")
    create_order(client, token_a, title="Decimal Saga", issue_number="2")
    create_order(client, token_b, title="Decimal Saga", issue_number="15")

    decimal_inventory_id = latest_inventory_id(session)
    issue = issue_for_inventory(session, decimal_inventory_id)
    issue.issue_number = "1.5"
    session.add(issue)
    session.commit()

    response = client.get("/missing-issues", headers=auth_headers(token_a))
    assert response.status_code == 200
    items = response.json()["items"]
    assert any(item["issue_number"] == "1.5" and item["classification"] == "confirmed_missing" for item in items)


def test_annual_isolation_does_not_create_mainline_gap(client: TestClient, session: Session) -> None:
    token_a = register_and_login(client, "run-annual-a@example.com")
    token_b = register_and_login(client, "run-annual-b@example.com")
    create_order(client, token_a, title="Annual Saga", issue_number="1")
    create_order(client, token_a, title="Annual Saga", issue_number="2")
    create_order(client, token_b, title="Annual Saga", issue_number="Annual 1")

    annual_copy_id = latest_inventory_id(session)
    annual_issue = issue_for_inventory(session, annual_copy_id)
    annual_issue.issue_number = "Annual 1"
    session.add(annual_issue)
    session.commit()

    response = client.get("/missing-issues", headers=auth_headers(token_a))
    assert response.status_code == 200
    assert all(item["issue_number"] != "Annual 1" for item in response.json()["items"])


def test_mini_series_completion(client: TestClient) -> None:
    token = register_and_login(client, "run-complete@example.com")
    create_order(client, token, title="Mini Complete", issue_number="1")
    create_order(client, token, title="Mini Complete", issue_number="2")
    create_order(client, token, title="Mini Complete", issue_number="3")

    response = client.get("/run-detection", headers=auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["complete_limited_series_groups"] >= 1
    assert body["series_groups"][0]["series_status"] == "complete_limited_series"


def test_preorder_future_issue_handling(client: TestClient) -> None:
    token = register_and_login(client, "run-preorder@example.com")
    create_order(client, token, title="Preorder Saga", issue_number="1", order_status="received")
    create_order(client, token, title="Preorder Saga", issue_number="2", order_status="received")
    create_order(
        client,
        token,
        title="Preorder Saga",
        issue_number="3",
        release_status="not_released_yet",
        order_status="preordered",
        release_date="2026-12-15",
    )

    response = client.get("/run-detection", headers=auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["preorder_pending_rows"] == 1
    assert body["series_groups"][0]["series_status"] == "probable_ongoing_series"
    pending = [item for item in body["series_groups"][0]["missing_issues"] if item["classification"] == "preorder_pending"]
    assert pending and pending[0]["issue_number"] == "3"


def test_unreleased_future_issue_handling(client: TestClient, session: Session) -> None:
    token_a = register_and_login(client, "run-future-a@example.com")
    token_b = register_and_login(client, "run-future-b@example.com")
    create_order(client, token_a, title="Future Saga", issue_number="1")
    create_order(
        client,
        token_b,
        title="Future Saga",
        issue_number="2",
        release_status="not_released_yet",
        order_status="preordered",
        release_date="2026-12-15",
    )

    future_copy_id = latest_inventory_id(session)
    future_issue = issue_for_inventory(session, future_copy_id)
    future_issue.release_date = date(2026, 12, 15)
    session.add(future_issue)
    session.commit()

    response = client.get("/missing-issues", headers=auth_headers(token_a))
    assert response.status_code == 200
    assert any(
        item["issue_number"] == "2" and item["classification"] == "unreleased_future_issue"
        for item in response.json()["items"]
    )


def test_unresolved_identity_gaps(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "run-unresolved@example.com")
    create_order(client, token, title="Identity Saga", issue_number="1")
    inventory_id = latest_inventory_id(session)
    add_pending_canonical_suggestion(session, inventory_copy_id=inventory_id)

    response = client.get("/missing-issues", headers=auth_headers(token))
    assert response.status_code == 200
    assert any(item["classification"] == "unresolved_identity_gap" for item in response.json()["items"])


def test_run_detection_attachment_and_detail_round_trip(client: TestClient) -> None:
    token_a = register_and_login(client, "run-detail-a@example.com")
    token_b = register_and_login(client, "run-detail-b@example.com")
    create_order(client, token_a, title="Detail Saga", issue_number="1")
    create_order(client, token_a, title="Detail Saga", issue_number="3")
    create_order(client, token_b, title="Detail Saga", issue_number="2")

    inventory = client.get("/inventory?page=1&page_size=10", headers=auth_headers(token_a))
    assert inventory.status_code == 200
    attach = inventory.json()["items"][0]["run_detection"]
    assert attach is not None
    assert attach["series_key"].startswith("Image|Detail Saga")

    detail = client.get(f"/run-detection/{attach['series_key']}", headers=auth_headers(token_a))
    assert detail.status_code == 200
    assert detail.json()["series_key"] == attach["series_key"]


def test_run_detection_no_metadata_mutation(client: TestClient, session: Session) -> None:
    token_a = register_and_login(client, "run-idem-a@example.com")
    token_b = register_and_login(client, "run-idem-b@example.com")
    create_order(client, token_a, title="Idem Saga", issue_number="1")
    create_order(client, token_a, title="Idem Saga", issue_number="3")
    create_order(client, token_b, title="Idem Saga", issue_number="2")

    before = {
        int(row.id): (row.metadata_identity_key, row.canonical_series_id, row.release_date, row.release_status)
        for row in session.exec(select(InventoryCopy)).all()
        if row.id is not None
    }
    assert client.get("/run-detection", headers=auth_headers(token_a)).status_code == 200
    assert client.get("/missing-issues", headers=auth_headers(token_a)).status_code == 200
    after = {
        int(row.id): (row.metadata_identity_key, row.canonical_series_id, row.release_date, row.release_status)
        for row in session.exec(select(InventoryCopy)).all()
        if row.id is not None
    }
    assert before == after


def test_ops_run_detection_endpoint(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "run-ops@example.com")
    from app.core.config import get_settings

    get_settings.cache_clear()
    token = register_and_login(client, "run-ops@example.com")
    create_order(client, token, title="Ops Saga", issue_number="1")

    response = client.get("/ops/run-detection", headers=auth_headers(token))
    assert response.status_code == 200
    assert "summary" in response.json()
    get_settings.cache_clear()
