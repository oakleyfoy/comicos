from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import (
    CatalogImage,
    CatalogIssue,
    CatalogPublisher,
    CatalogSeries,
    InventoryCopy,
    User,
)
from app.services.acquisition.acquisition_service import backfill_legacy_inventory
from test_inventory import auth_headers, create_order, register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def _seed_catalog(session: Session) -> dict[str, int]:
    """Seed a publisher/series with one single-cover issue (#1) and a multi-cover (#2)."""
    publisher = CatalogPublisher(name="Marvel", normalized_name="marvel")
    session.add(publisher)
    session.flush()
    series = CatalogSeries(
        publisher_id=publisher.id, name="Amazing Spider-Man", normalized_name="amazing spider-man", start_year=2018
    )
    session.add(series)
    session.flush()

    issue1 = CatalogIssue(
        series_id=series.id, publisher_id=publisher.id, issue_number="1", normalized_issue_number="1"
    )
    issue2a = CatalogIssue(
        series_id=series.id, publisher_id=publisher.id, issue_number="2", normalized_issue_number="2", title="Cover A"
    )
    issue2b = CatalogIssue(
        series_id=series.id, publisher_id=publisher.id, issue_number="2", normalized_issue_number="2", title="Variant Cover B"
    )
    issue3 = CatalogIssue(
        series_id=series.id, publisher_id=publisher.id, issue_number="3", normalized_issue_number="3"
    )
    issue4 = CatalogIssue(
        series_id=series.id, publisher_id=publisher.id, issue_number="4", normalized_issue_number="4"
    )
    session.add_all([issue1, issue2a, issue2b, issue3, issue4])
    session.flush()
    session.add(
        CatalogImage(issue_id=issue1.id, source_url="https://img/1.jpg", image_type="cover", source="test")
    )
    session.commit()
    return {
        "publisher_id": int(publisher.id),
        "series_id": int(series.id),
        "issue1": int(issue1.id),
        "issue2a": int(issue2a.id),
        "issue2b": int(issue2b.id),
        "issue3": int(issue3.id),
        "issue4": int(issue4.id),
    }


def _create_acq(client: TestClient, token: str, **overrides) -> dict:
    payload = {
        "acquisition_type": "FACEBOOK",
        "purchase_date": "2026-06-01",
        "seller_name": "Jane Seller",
        "total_paid": "120.00",
        "shipping_paid": "0.00",
        "tax_paid": "0.00",
        "expected_book_count": 40,
    }
    payload.update(overrides)
    resp = client.post("/api/v1/acquisitions", headers=auth_headers(token), json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_create_acquisition(client: TestClient) -> None:
    token = register_and_login(client, "acq-create@example.com")
    body = _create_acq(client, token)
    assert body["status"] == "OPEN"
    assert body["acquisition_type"] == "FACEBOOK"
    assert Decimal(body["total_cost"]) == Decimal("120.00")
    assert body["item_count"] == 0


def test_update_acquisition(client: TestClient) -> None:
    token = register_and_login(client, "acq-update@example.com")
    body = _create_acq(client, token)
    resp = client.patch(
        f"/api/v1/acquisitions/{body['id']}",
        headers=auth_headers(token),
        json={"seller_name": "New Seller", "total_paid": "150.00"},
    )
    assert resp.status_code == 200, resp.text
    updated = resp.json()
    assert updated["seller_name"] == "New Seller"
    assert Decimal(updated["total_cost"]) == Decimal("150.00")


def test_negative_money_rejected(client: TestClient) -> None:
    token = register_and_login(client, "acq-neg@example.com")
    resp = client.post(
        "/api/v1/acquisitions",
        headers=auth_headers(token),
        json={"acquisition_type": "EBAY", "total_paid": "-5.00"},
    )
    assert resp.status_code == 400


def test_list_own_acquisitions_only(client: TestClient) -> None:
    token_a = register_and_login(client, "acq-owner-a@example.com")
    token_b = register_and_login(client, "acq-owner-b@example.com")
    _create_acq(client, token_a)
    _create_acq(client, token_b)
    resp = client.get("/api/v1/acquisitions", headers=auth_headers(token_a))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1


def test_cannot_access_other_users_acquisition(client: TestClient) -> None:
    token_a = register_and_login(client, "acq-x-a@example.com")
    token_b = register_and_login(client, "acq-x-b@example.com")
    body = _create_acq(client, token_a)
    resp = client.get(f"/api/v1/acquisitions/{body['id']}", headers=auth_headers(token_b))
    assert resp.status_code == 404


def test_add_books_requires_existing_acquisition(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "acq-add-404@example.com")
    ids = _seed_catalog(session)
    resp = client.post(
        "/api/v1/acquisitions/999999/items",
        headers=auth_headers(token),
        json={"items": [{"catalog_issue_id": ids["issue1"], "quantity": 1}]},
    )
    assert resp.status_code == 404


def test_added_books_carry_acquisition_id(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "acq-add@example.com")
    ids = _seed_catalog(session)
    body = _create_acq(client, token)
    resp = client.post(
        f"/api/v1/acquisitions/{body['id']}/items",
        headers=auth_headers(token),
        json={"items": [{"catalog_issue_id": ids["issue1"], "quantity": 1}]},
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()
    assert result["created_count"] == 1
    copy_id = result["results"][0]["inventory_copy_ids"][0]
    copy = session.get(InventoryCopy, copy_id)
    assert copy is not None
    assert copy.acquisition_id == body["id"]
    assert copy.catalog_issue_id == ids["issue1"]


def test_duplicate_issue_prompts_then_quantity(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "acq-dup@example.com")
    ids = _seed_catalog(session)
    body = _create_acq(client, token)
    url = f"/api/v1/acquisitions/{body['id']}/items"
    client.post(url, headers=auth_headers(token), json={"items": [{"catalog_issue_id": ids["issue1"]}]})
    # Second add without force => prompt, no new copy
    resp = client.post(url, headers=auth_headers(token), json={"items": [{"catalog_issue_id": ids["issue1"]}]})
    data = resp.json()
    assert data["created_count"] == 0
    assert ids["issue1"] in data["duplicate_catalog_issue_ids"]
    # Force duplicate => extra copy
    resp2 = client.post(
        url,
        headers=auth_headers(token),
        json={"items": [{"catalog_issue_id": ids["issue1"]}], "force_duplicate": True},
    )
    assert resp2.json()["created_count"] == 1
    count = len(
        session.exec(
            select(InventoryCopy).where(InventoryCopy.catalog_issue_id == ids["issue1"])
        ).all()
    )
    assert count == 2


def test_even_cost_allocation(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "acq-alloc@example.com")
    ids = _seed_catalog(session)
    body = _create_acq(client, token, total_paid="120.00")
    url = f"/api/v1/acquisitions/{body['id']}/items"
    client.post(
        url,
        headers=auth_headers(token),
        json={
            "items": [
                {"catalog_issue_id": ids["issue1"]},
                {"catalog_issue_id": ids["issue2a"]},
                {"catalog_issue_id": ids["issue3"]},
                {"catalog_issue_id": ids["issue4"]},
            ]
        },
    )
    resp = client.post(
        f"/api/v1/acquisitions/{body['id']}/allocate",
        headers=auth_headers(token),
        json={"mode": "EVEN"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["fully_allocated"] is True
    assert Decimal(data["allocated_total"]) == Decimal("120.00")
    assert all(Decimal(item["cost_basis"]) == Decimal("30.00") for item in data["items"])


def test_complete_blocks_edits(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "acq-complete@example.com")
    ids = _seed_catalog(session)
    body = _create_acq(client, token)
    client.post(f"/api/v1/acquisitions/{body['id']}/complete", headers=auth_headers(token))
    # editing non-status fields blocked
    resp = client.patch(
        f"/api/v1/acquisitions/{body['id']}",
        headers=auth_headers(token),
        json={"seller_name": "Nope"},
    )
    assert resp.status_code == 409
    # adding items blocked
    resp2 = client.post(
        f"/api/v1/acquisitions/{body['id']}/items",
        headers=auth_headers(token),
        json={"items": [{"catalog_issue_id": ids["issue1"]}]},
    )
    assert resp2.status_code == 409


def test_legacy_backfill(client: TestClient, session: Session) -> None:
    email = "acq-legacy@example.com"
    token = register_and_login(client, email)
    create_order(client, token)  # creates inventory copies with no acquisition
    owner_id = _owner_id(session, email)
    orphans = session.exec(
        select(InventoryCopy).where(
            InventoryCopy.user_id == owner_id, InventoryCopy.acquisition_id.is_(None)
        )
    ).all()
    assert len(orphans) > 0
    legacy = backfill_legacy_inventory(session, owner_user_id=owner_id)
    assert legacy is not None
    assert legacy.seller_name == "Legacy / Unknown Source"
    remaining = session.exec(
        select(InventoryCopy).where(
            InventoryCopy.user_id == owner_id, InventoryCopy.acquisition_id.is_(None)
        )
    ).all()
    assert len(remaining) == 0


def test_issue_grid_single_vs_multi(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "acq-grid@example.com")
    ids = _seed_catalog(session)
    resp = client.get(
        f"/api/v1/acquisitions/catalog/series/{ids['series_id']}/issues",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    tiles = {t["normalized_issue_number"]: t for t in resp.json()["tiles"]}
    assert tiles["1"]["has_variants"] is False
    assert tiles["1"]["catalog_issue_id"] == ids["issue1"]
    assert tiles["1"]["cover_image_url"] == "https://img/1.jpg"
    assert tiles["2"]["has_variants"] is True
    assert tiles["2"]["catalog_issue_id"] is None
    assert tiles["2"]["cover_count"] >= 2


def test_variant_picker_lists_covers(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "acq-variant@example.com")
    ids = _seed_catalog(session)
    resp = client.get(
        f"/api/v1/acquisitions/catalog/series/{ids['series_id']}/issue-number/2/variants",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    options = resp.json()["options"]
    assert len(options) == 2
    # Cover A sorts before variant
    assert options[0]["sort_rank"] <= options[1]["sort_rank"]


def test_bulk_range_adds_single_cover_defers_multi(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "acq-bulk@example.com")
    ids = _seed_catalog(session)
    body = _create_acq(client, token)
    resp = client.post(
        f"/api/v1/acquisitions/{body['id']}/items/bulk-range",
        headers=auth_headers(token),
        json={"series_id": ids["series_id"], "start_issue": 1, "end_issue": 4, "variant_resolution": "review"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # #1, #3, #4 are single-cover (added); #2 multi -> needs variant
    assert data["added_count"] == 3
    assert any(n["issue_number"] == "2" for n in data["needs_variant"])


def test_inventory_detail_links_back_to_acquisition(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "acq-detail@example.com")
    ids = _seed_catalog(session)
    body = _create_acq(client, token)
    add = client.post(
        f"/api/v1/acquisitions/{body['id']}/items",
        headers=auth_headers(token),
        json={"items": [{"catalog_issue_id": ids["issue1"]}]},
    ).json()
    copy_id = add["results"][0]["inventory_copy_ids"][0]
    resp = client.get(f"/inventory/{copy_id}", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    detail = resp.json()
    assert detail["acquisition_id"] == body["id"]
    assert detail["acquisition_type"] == "FACEBOOK"
    assert detail["acquisition_seller_name"] == "Jane Seller"


def test_needs_review_queue(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "acq-review@example.com")
    ids = _seed_catalog(session)
    body = _create_acq(client, token)
    client.post(
        f"/api/v1/acquisitions/{body['id']}/items/generic",
        headers=auth_headers(token),
        json={"series_id": ids["series_id"], "issue_number": "7", "quantity": 1},
    )
    resp = client.get("/api/v1/acquisitions/needs-review", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["total"] == 1


def test_create_placeholder_item(client: TestClient) -> None:
    token = register_and_login(client, "acq-ph-create@example.com")
    body = _create_acq(client, token)
    resp = client.post(
        f"/api/v1/acquisitions/{body['id']}/placeholder-items",
        headers=auth_headers(token),
        json={
            "title": "Uncanny X-Men",
            "issue_number": "221",
            "publisher": "Marvel",
            "quantity": 1,
            "notes": "no match in catalog",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["created_count"] == 1

    items = client.get(f"/api/v1/acquisitions/{body['id']}/items", headers=auth_headers(token)).json()
    assert items["total"] == 1
    item = items["items"][0]
    assert item["is_placeholder"] is True
    assert item["catalog_status"] == "PLACEHOLDER"
    assert item["catalog_issue_id"] is None
    assert item["series"] == "Uncanny X-Men"
    assert item["issue_number"] == "221"
    assert item["publisher"] == "Marvel"


def test_placeholder_requires_title(client: TestClient) -> None:
    token = register_and_login(client, "acq-ph-title@example.com")
    body = _create_acq(client, token)
    resp = client.post(
        f"/api/v1/acquisitions/{body['id']}/placeholder-items",
        headers=auth_headers(token),
        json={"title": "   ", "quantity": 1},
    )
    assert resp.status_code == 400


def test_placeholder_participates_in_cost_allocation(client: TestClient) -> None:
    token = register_and_login(client, "acq-ph-alloc@example.com")
    body = _create_acq(client, token, total_paid="350.22")
    client.post(
        f"/api/v1/acquisitions/{body['id']}/placeholder-items",
        headers=auth_headers(token),
        json={"title": "Uncanny X-Men", "issue_number": "221", "publisher": "Marvel", "quantity": 1},
    )
    alloc = client.post(
        f"/api/v1/acquisitions/{body['id']}/allocate",
        headers=auth_headers(token),
        json={"mode": "EVEN"},
    )
    assert alloc.status_code == 200, alloc.text
    data = alloc.json()
    assert Decimal(data["allocated_total"]) == Decimal("350.22")
    assert data["fully_allocated"] is True

    items = client.get(f"/api/v1/acquisitions/{body['id']}/items", headers=auth_headers(token)).json()
    assert Decimal(items["items"][0]["cost_basis"]) == Decimal("350.22")


def test_placeholder_and_catalog_mix_allocates(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "acq-ph-mix@example.com")
    ids = _seed_catalog(session)
    body = _create_acq(client, token, total_paid="100.00")
    client.post(
        f"/api/v1/acquisitions/{body['id']}/items",
        headers=auth_headers(token),
        json={"items": [{"catalog_issue_id": ids["issue1"], "quantity": 1}]},
    )
    client.post(
        f"/api/v1/acquisitions/{body['id']}/placeholder-items",
        headers=auth_headers(token),
        json={"title": "Missing Book", "issue_number": "1", "quantity": 1},
    )
    alloc = client.post(
        f"/api/v1/acquisitions/{body['id']}/allocate",
        headers=auth_headers(token),
        json={"mode": "EVEN"},
    )
    assert alloc.status_code == 200, alloc.text
    data = alloc.json()
    assert Decimal(data["allocated_total"]) == Decimal("100.00")
    assert data["fully_allocated"] is True
    items = client.get(f"/api/v1/acquisitions/{body['id']}/items", headers=auth_headers(token)).json()
    assert items["total"] == 2
    bases = sorted(Decimal(i["cost_basis"]) for i in items["items"])
    assert bases == [Decimal("50.00"), Decimal("50.00")]


def test_complete_acquisition_with_placeholder(client: TestClient) -> None:
    token = register_and_login(client, "acq-ph-complete@example.com")
    body = _create_acq(client, token)
    client.post(
        f"/api/v1/acquisitions/{body['id']}/placeholder-items",
        headers=auth_headers(token),
        json={"title": "Placeholder Only", "issue_number": "1", "quantity": 2},
    )
    resp = client.post(f"/api/v1/acquisitions/{body['id']}/complete", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "COMPLETE"
    assert resp.json()["item_count"] == 2


def test_delete_empty_acquisition(client: TestClient) -> None:
    token = register_and_login(client, "acq-del-empty@example.com")
    body = _create_acq(client, token)
    resp = client.delete(f"/api/v1/acquisitions/{body['id']}", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    assert resp.json()["deleted_inventory_count"] == 0
    assert client.get(f"/api/v1/acquisitions/{body['id']}", headers=auth_headers(token)).status_code == 404


def test_delete_acquisition_with_books_requires_confirm(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "acq-del-books@example.com")
    ids = _seed_catalog(session)
    body = _create_acq(client, token)
    add = client.post(
        f"/api/v1/acquisitions/{body['id']}/items",
        headers=auth_headers(token),
        json={"items": [{"catalog_issue_id": ids["issue1"], "quantity": 1}]},
    )
    copy_id = add.json()["results"][0]["inventory_copy_ids"][0]

    blocked = client.delete(f"/api/v1/acquisitions/{body['id']}", headers=auth_headers(token))
    assert blocked.status_code == 409

    ok = client.delete(
        f"/api/v1/acquisitions/{body['id']}?delete_inventory=true", headers=auth_headers(token)
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["deleted_inventory_count"] == 1
    assert session.get(InventoryCopy, copy_id) is None


def test_cannot_delete_other_users_acquisition(client: TestClient) -> None:
    token_a = register_and_login(client, "acq-del-a@example.com")
    token_b = register_and_login(client, "acq-del-b@example.com")
    body = _create_acq(client, token_a)
    resp = client.delete(f"/api/v1/acquisitions/{body['id']}", headers=auth_headers(token_b))
    assert resp.status_code == 404


def test_delete_acquisition_with_placeholders(client: TestClient) -> None:
    token = register_and_login(client, "acq-del-ph@example.com")
    body = _create_acq(client, token)
    add = client.post(
        f"/api/v1/acquisitions/{body['id']}/placeholder-items",
        headers=auth_headers(token),
        json={"title": "Placeholder Only", "issue_number": "1", "quantity": 2},
    )
    assert add.status_code == 200, add.text
    resp = client.delete(
        f"/api/v1/acquisitions/{body['id']}?delete_inventory=true",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["deleted_inventory_count"] == 2
