from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import InventoryCopy, InventoryFmvSnapshot, MarketFmvCompReference, MarketFmvSnapshot, MarketSaleMatchSuggestion, MarketSource
from app.services.market_sales import ensure_system_market_sources
from test_inventory import auth_headers, create_order, register_and_login


def _ops_headers(client: TestClient, email: str) -> dict[str, str]:
    get_settings.cache_clear()
    token = register_and_login(client, email)
    return auth_headers(token)


def _owner_headers(client: TestClient, email: str) -> dict[str, str]:
    token = register_and_login(client, email)
    return auth_headers(token)


def _source_id(session: Session, source_name: str) -> int:
    ensure_system_market_sources(session)
    row = session.exec(select(MarketSource).where(MarketSource.source_name == source_name)).first()
    assert row is not None and row.id is not None
    return int(row.id)


def _create_sale(client: TestClient, headers: dict[str, str], **overrides):
    payload = {
        "market_source_id": overrides.pop("market_source_id"),
        "source_listing_id": overrides.pop("source_listing_id", "listing-1"),
        "listing_type": overrides.pop("listing_type", "auction"),
        "raw_title": overrides.pop("raw_title", "Invincible"),
        "raw_issue": overrides.pop("raw_issue", "1"),
        "raw_publisher": overrides.pop("raw_publisher", "Image"),
        "raw_variant": overrides.pop("raw_variant", "Cover A"),
        "raw_grade": overrides.pop("raw_grade", None),
        "raw_cert_number": overrides.pop("raw_cert_number", None),
        "sale_price": overrides.pop("sale_price", "100.00"),
        "shipping_price": overrides.pop("shipping_price", "0.00"),
        "total_price": overrides.pop("total_price", "100.00"),
        "currency_code": overrides.pop("currency_code", "USD"),
        "sale_date": overrides.pop("sale_date", date.today().isoformat()),
        "seller_name": overrides.pop("seller_name", "Seller One"),
        "buyer_name": overrides.pop("buyer_name", "Buyer One"),
        "is_graded": overrides.pop("is_graded", False),
        "grading_company": overrides.pop("grading_company", None),
        "is_signed": overrides.pop("is_signed", False),
        "source_url": overrides.pop("source_url", "https://example.com/listing-1"),
        "source_metadata_json": overrides.pop("source_metadata_json", {}),
        "images": overrides.pop("images", []),
    }
    payload.update(overrides)
    response = client.post("/ops/market-sales", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _seed_match_suggestion(
    session: Session,
    *,
    sale_id: int,
    suggested_identity_key: str,
    canonical_issue_id: int = 101,
    review_state: str = "approved",
    confidence_bucket: str = "very_high",
    deterministic_score: float = 0.97,
) -> MarketSaleMatchSuggestion:
    now = datetime.now(timezone.utc)
    row = MarketSaleMatchSuggestion(
        market_sale_record_id=sale_id,
        canonical_issue_id=canonical_issue_id,
        canonical_series_id=None,
        canonical_publisher_id=None,
        suggested_identity_key=suggested_identity_key,
        suggestion_type="exact_identity_key",
        confidence_bucket=confidence_bucket,
        deterministic_score=deterministic_score,
        confidence_version="market-sale-match-suggestion-v1",
        evidence_json={"seeded_for_test": True, "metadata_identity_key": suggested_identity_key},
        review_state=review_state,
        reviewed_by_user_id=None,
        reviewed_at=now if review_state != "pending" else None,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _generate(client: TestClient, headers: dict[str, str]):
    response = client.post("/ops/market-fmv/generate", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_market_fmv_generates_raw_and_graded_snapshots_with_both_methods(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-market-fmv-separation@example.com")
    headers = _ops_headers(client, "ops-market-fmv-separation@example.com")
    source_id = _source_id(session, "eBay")
    identity_key = "Image|Invincible|1|Cover A"

    raw_one = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="fmv-raw-1",
        sale_price="100.00",
        total_price="100.00",
        sale_date=(date.today() - timedelta(days=21)).isoformat(),
    )
    raw_two = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="fmv-raw-2",
        sale_price="140.00",
        total_price="140.00",
        sale_date=(date.today() - timedelta(days=7)).isoformat(),
    )
    graded_one = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="fmv-graded-1",
        sale_price="200.00",
        total_price="200.00",
        sale_date=(date.today() - timedelta(days=10)).isoformat(),
        is_graded=True,
        grading_company="CGC",
        raw_grade="CGC 9.8",
    )
    graded_two = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="fmv-graded-2",
        sale_price="220.00",
        total_price="220.00",
        sale_date=(date.today() - timedelta(days=3)).isoformat(),
        is_graded=True,
        grading_company="CGC",
        raw_grade="CGC 9.8",
    )
    for sale_id in (raw_one["id"], raw_two["id"], graded_one["id"], graded_two["id"]):
        _seed_match_suggestion(session, sale_id=sale_id, suggested_identity_key=identity_key)

    payload = _generate(client, headers)
    assert payload["snapshot_count"] >= 6

    raw_list = client.get("/ops/market-fmv?snapshot_scope=raw", headers=headers)
    assert raw_list.status_code == 200, raw_list.text
    raw_items = raw_list.json()["items"]
    raw_items = [row for row in raw_items if row["metadata_identity_key"] == identity_key]
    assert [row["valuation_method"] for row in raw_items] == ["median_recent_sales", "weighted_recent_sales"]
    assert all(row["comp_count"] == 2 for row in raw_items)

    graded_scope_list = client.get("/ops/market-fmv?snapshot_scope=graded_by_grade", headers=headers)
    assert graded_scope_list.status_code == 200, graded_scope_list.text
    graded_scope_items = [row for row in graded_scope_list.json()["items"] if row["metadata_identity_key"] == identity_key]
    assert graded_scope_items
    normalized_grade = str(graded_scope_items[0]["normalized_grade"])
    graded_grade_list = client.get(
        f"/ops/market-fmv?snapshot_scope=graded_by_grade&grading_company=CGC&normalized_grade={normalized_grade}",
        headers=headers,
    )
    assert graded_grade_list.status_code == 200, graded_grade_list.text
    graded_items = [row for row in graded_grade_list.json()["items"] if row["metadata_identity_key"] == identity_key]
    assert [row["valuation_method"] for row in graded_items] == ["median_recent_sales", "weighted_recent_sales"]
    assert all(row["comp_count"] == 2 for row in graded_items)

    raw_detail = client.get(f"/ops/market-fmv/{raw_items[0]['id']}", headers=headers)
    assert raw_detail.status_code == 200, raw_detail.text
    assert {ref["market_sale_record_id"] for ref in raw_detail.json()["comp_references"] if ref["excluded_reason"] is None} == {
        raw_one["id"],
        raw_two["id"],
    }


def test_market_fmv_weighted_recent_sales_differs_from_median_and_owner_identity_route(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-market-fmv-methods@example.com")
    headers = _ops_headers(client, "ops-market-fmv-methods@example.com")
    owner_headers = _owner_headers(client, "owner-market-fmv@example.com")
    source_id = _source_id(session, "Heritage Auctions")
    identity_key = "Image|Invincible|2|Cover A"

    old_sale = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="fmv-method-old",
        sale_price="10.00",
        total_price="10.00",
        sale_date=(date.today() - timedelta(days=300)).isoformat(),
    )
    recent_sale = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="fmv-method-recent",
        sale_price="100.00",
        total_price="100.00",
        sale_date=(date.today() - timedelta(days=5)).isoformat(),
    )
    for sale_id in (old_sale["id"], recent_sale["id"]):
        _seed_match_suggestion(session, sale_id=sale_id, suggested_identity_key=identity_key, canonical_issue_id=202)

    _generate(client, headers)
    response = client.get(f"/market-fmv/by-identity/{identity_key}", headers=owner_headers)
    assert response.status_code == 200, response.text
    items = [row for row in response.json()["items"] if row["snapshot_scope"] == "raw"]
    assert [row["valuation_method"] for row in items] == ["median_recent_sales", "weighted_recent_sales"]
    median_value = Decimal(next(row["estimated_fmv"] for row in items if row["valuation_method"] == "median_recent_sales"))
    weighted_value = Decimal(next(row["estimated_fmv"] for row in items if row["valuation_method"] == "weighted_recent_sales"))
    assert median_value == Decimal("55.00")
    assert weighted_value > median_value


def test_market_fmv_excludes_stale_comp_references_from_snapshot_counts(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-market-fmv-stale@example.com")
    headers = _ops_headers(client, "ops-market-fmv-stale@example.com")
    source_id = _source_id(session, "ComicLink")
    identity_key = "Image|Invincible|3|Cover A"

    fresh_sale = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="fmv-stale-fresh",
        sale_price="55.00",
        total_price="55.00",
        sale_date=(date.today() - timedelta(days=20)).isoformat(),
    )
    stale_sale = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="fmv-stale-old",
        sale_price="500.00",
        total_price="500.00",
        sale_date=(date.today() - timedelta(days=400)).isoformat(),
    )
    for sale_id in (fresh_sale["id"], stale_sale["id"]):
        _seed_match_suggestion(session, sale_id=sale_id, suggested_identity_key=identity_key, canonical_issue_id=303)

    _generate(client, headers)
    listing = client.get("/ops/market-fmv?snapshot_scope=raw", headers=headers)
    assert listing.status_code == 200, listing.text
    item = next(row for row in listing.json()["items"] if row["metadata_identity_key"] == identity_key and row["valuation_method"] == "median_recent_sales")
    assert item["comp_count"] == 1
    detail = client.get(f"/ops/market-fmv/{item['id']}", headers=headers)
    assert detail.status_code == 200, detail.text
    refs = detail.json()["comp_references"]
    assert any(ref["market_sale_record_id"] == stale_sale["id"] and ref["excluded_reason"] == "stale_comp" for ref in refs)
    assert any(ref["market_sale_record_id"] == fresh_sale["id"] and ref["excluded_reason"] is None for ref in refs)


def test_market_fmv_assigns_buckets_and_keeps_inventory_manual_fmv_unchanged(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-market-fmv-buckets@example.com")
    headers = _ops_headers(client, "ops-market-fmv-buckets@example.com")
    inventory_email = "inventory-fmv-owner@example.com"
    inventory_token = register_and_login(client, inventory_email)
    source_id = _source_id(session, "Shortboxed")
    identity_key = "Image|Invincible|4|Cover A"

    create_order(
        client,
        inventory_token,
        items=[
            {
                "title": "Invincible",
                "publisher": "Image",
                "issue_number": "4",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 5.00,
            }
        ],
    )
    copy = session.exec(select(InventoryCopy).order_by(InventoryCopy.id.desc())).first()
    assert copy is not None
    copy.current_fmv = Decimal("12.50")
    session.add(copy)
    session.commit()
    session.refresh(copy)
    before_history_count = len(session.exec(select(InventoryFmvSnapshot)).all())

    prices = ["100.00", "102.00", "98.00", "101.00"]
    day_offsets = [21, 14, 7, 3]
    sale_ids: list[int] = []
    for idx, (price, day_offset) in enumerate(zip(prices, day_offsets, strict=True), start=1):
        sale = _create_sale(
            client,
            headers,
            market_source_id=source_id,
            source_listing_id=f"fmv-bucket-{idx}",
            sale_price=price,
            total_price=price,
            sale_date=(date.today() - timedelta(days=day_offset)).isoformat(),
        )
        sale_ids.append(int(sale["id"]))
        _seed_match_suggestion(session, sale_id=int(sale["id"]), suggested_identity_key=identity_key, canonical_issue_id=404)

    _generate(client, headers)
    listing = client.get("/ops/market-fmv?snapshot_scope=raw", headers=headers)
    assert listing.status_code == 200, listing.text
    item = next(row for row in listing.json()["items"] if row["metadata_identity_key"] == identity_key and row["valuation_method"] == "median_recent_sales")
    assert item["confidence_bucket"] == "high"
    assert item["liquidity_bucket"] == "medium"
    assert item["volatility_bucket"] == "stable"
    assert item["stale_data"] is False

    assert session.get(InventoryCopy, copy.id).current_fmv == Decimal("12.50")
    assert len(session.exec(select(InventoryFmvSnapshot)).all()) == before_history_count


def test_market_fmv_uses_deterministic_ordering_and_skips_duplicate_flagged_sales(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-market-fmv-ordering@example.com")
    headers = _ops_headers(client, "ops-market-fmv-ordering@example.com")
    source_id = _source_id(session, "eBay")
    raw_identity = "Image|Invincible|5|Cover A"
    graded_identity = "Image|Invincible|5|CGC 9.8"

    raw_valid = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="fmv-order-raw-valid",
        sale_price="90.00",
        total_price="90.00",
    )
    raw_duplicate = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="fmv-order-raw-duplicate",
        sale_price="120.00",
        total_price="120.00",
    )
    graded_valid = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="fmv-order-graded-valid",
        sale_price="180.00",
        total_price="180.00",
        is_graded=True,
        grading_company="CGC",
        raw_grade="CGC 9.8",
    )
    assert client.post(f"/ops/market-sales/{raw_duplicate['id']}/flag-duplicate", headers=headers, json={"reason": "duplicate"}).status_code == 200

    _seed_match_suggestion(session, sale_id=raw_valid["id"], suggested_identity_key=raw_identity, canonical_issue_id=505)
    _seed_match_suggestion(session, sale_id=raw_duplicate["id"], suggested_identity_key=raw_identity, canonical_issue_id=505)
    _seed_match_suggestion(session, sale_id=graded_valid["id"], suggested_identity_key=graded_identity, canonical_issue_id=505)

    _generate(client, headers)

    list_response = client.get("/ops/market-fmv", headers=headers)
    assert list_response.status_code == 200, list_response.text
    items = list_response.json()["items"]
    matching = [
        row for row in items if row["metadata_identity_key"] in {raw_identity, graded_identity}
    ]
    assert [(row["snapshot_scope"], row["valuation_method"]) for row in matching[:4]] == [
        ("raw", "median_recent_sales"),
        ("raw", "weighted_recent_sales"),
        ("graded", "median_recent_sales"),
        ("graded", "weighted_recent_sales"),
    ]

    raw_snapshot = next(row for row in matching if row["metadata_identity_key"] == raw_identity and row["valuation_method"] == "median_recent_sales")
    raw_refs = client.get(f"/ops/market-fmv/{raw_snapshot['id']}", headers=headers)
    assert raw_refs.status_code == 200, raw_refs.text
    included_ids = {
        ref["market_sale_record_id"]
        for ref in raw_refs.json()["comp_references"]
        if ref["excluded_reason"] is None
    }
    assert included_ids == {raw_valid["id"]}
    assert raw_duplicate["id"] not in included_ids

    assert len(session.exec(select(MarketFmvSnapshot)).all()) >= 4
    assert len(session.exec(select(MarketFmvCompReference)).all()) >= 3
