from __future__ import annotations

from urllib import request as urllib_request

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import MarketSaleNormalizationIssue, MarketSaleRecord, MarketSource, MetadataAudit
from app.services.market_sales import SYSTEM_MARKET_SOURCE_PRESETS, ensure_system_market_sources

from test_inventory import auth_headers, register_and_login


def _ops_headers(client: TestClient, email: str) -> dict[str, str]:
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
        "raw_title": overrides.pop("raw_title", "  Amazing Spider-Man  "),
        "raw_issue": overrides.pop("raw_issue", " no. 001 "),
        "raw_publisher": overrides.pop("raw_publisher", " marvel "),
        "raw_variant": overrides.pop("raw_variant", "B / Virgin"),
        "raw_grade": overrides.pop("raw_grade", " cgc 9.8 "),
        "raw_cert_number": overrides.pop("raw_cert_number", " cert 001 "),
        "sale_price": overrides.pop("sale_price", "100.00"),
        "shipping_price": overrides.pop("shipping_price", "5.00"),
        "total_price": overrides.pop("total_price", "105.00"),
        "currency_code": overrides.pop("currency_code", "usd"),
        "sale_date": overrides.pop("sale_date", "2026-05-20"),
        "seller_name": overrides.pop("seller_name", " Seller One "),
        "buyer_name": overrides.pop("buyer_name", " Buyer One "),
        "is_graded": overrides.pop("is_graded", True),
        "grading_company": overrides.pop("grading_company", "CGC"),
        "is_signed": overrides.pop("is_signed", False),
        "source_url": overrides.pop("source_url", " https://example.com/listing-1 "),
        "source_metadata_json": overrides.pop("source_metadata_json", {"source": "raw-import"}),
        "images": overrides.pop(
            "images",
            [
                {"image_url": " https://example.com/1.jpg ", "image_sha256": "abc123", "display_order": 0},
                {"image_url": " https://example.com/2.jpg ", "image_sha256": "def456", "display_order": 1},
            ],
        ),
    }
    payload.update(overrides)
    response = client.post("/ops/market-sales", json=payload, headers=headers)
    assert response.status_code == 201
    return response.json()


def test_market_source_registry_seeded_idempotently(client: TestClient, session: Session) -> None:
    owner_headers = auth_headers(register_and_login(client, "market-seed@example.com"))
    client.get("/market-sales", headers=owner_headers)
    ensure_system_market_sources(session)
    ensure_system_market_sources(session)
    rows = session.exec(select(MarketSource).order_by(MarketSource.import_priority.asc(), MarketSource.id.asc())).all()
    assert len(rows) == len(SYSTEM_MARKET_SOURCE_PRESETS)
    assert [row.source_name for row in rows] == [seed.source_name for seed in SYSTEM_MARKET_SOURCE_PRESETS]


def test_market_sale_upsert_normalizes_and_preserves_history(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-sales@example.com")
    get_settings.cache_clear()
    headers = _ops_headers(client, "ops-sales@example.com")
    source_id = _source_id(session, "eBay")

    first = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id=" listing-1 ",
        raw_title="  Amazing Spider-Man  ",
        raw_issue=" no. 001 ",
        raw_publisher=" marvel ",
        raw_variant="B / Virgin",
        raw_grade=" cgc 9.8 ",
        raw_cert_number=" cert 001 ",
        currency_code="usd",
    )
    assert first["source_listing_id"] == "listing-1"
    assert first["normalized_title"] == "Amazing Spider-Man"
    assert first["normalized_issue"] == "1"
    assert first["normalized_publisher"] == "Marvel"
    assert first["normalized_variant"] == "B / Virgin"
    assert first["normalized_grade"] == "CGC 9.8"
    assert first["normalized_cert_number"] == "CERT 001"
    assert first["currency_code"] == "USD"
    assert first["normalization_status"] == "partially_normalized"
    assert first["normalization_issue_count"] >= 1
    assert len(first["images"]) == 2
    assert len(first["normalization_issues"]) >= 1
    issues = session.exec(
        select(MarketSaleNormalizationIssue).where(MarketSaleNormalizationIssue.market_sale_record_id == first["id"])
    ).all()
    assert len(issues) >= 1

    second = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="listing-1",
        raw_title="Amazing Spider-Man (Updated)",
        raw_issue="1",
        raw_publisher="Marvel",
        raw_variant="B / Virgin",
        raw_grade="CGC 9.8",
        raw_cert_number="CERT 001",
        currency_code="USD",
        images=[{"image_url": "https://example.com/3.jpg", "image_sha256": "ghi789", "display_order": 2}],
    )
    assert second["id"] == first["id"]
    assert second["source_metadata_json"]["history"]
    assert len(second["source_metadata_json"]["history"]) == 2
    assert any(issue["issue_type"] == "duplicate_listing" for issue in second["normalization_issues"])
    assert len(second["images"]) == 3

    row = session.get(MarketSaleRecord, second["id"])
    assert row is not None
    assert row.raw_title == "Amazing Spider-Man (Updated)"


def test_market_sale_duplicate_candidates_surface_on_other_rows(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-sales-dupes@example.com")
    get_settings.cache_clear()
    headers = _ops_headers(client, "ops-sales-dupes@example.com")
    source_id = _source_id(session, "Heritage Auctions")

    base = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="ha-1",
        raw_title="Batman",
        raw_issue="1",
        raw_publisher="DC",
        raw_variant="A",
        raw_grade="CGC 9.8",
        raw_cert_number="12345",
        sale_price="250.00",
        shipping_price="0.00",
        total_price="250.00",
        sale_date="2026-05-21",
    )
    assert base["normalization_status"] in {"raw", "normalized"}

    cert_dup = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="ha-2",
        raw_title="Batman",
        raw_issue="1",
        raw_publisher="DC",
        raw_variant="A",
        raw_grade="CGC 9.8",
        raw_cert_number="12345",
        sale_price="250.00",
        shipping_price="0.00",
        total_price="250.00",
        sale_date="2026-05-21",
    )
    assert any(issue["issue_type"] == "duplicate_listing" for issue in cert_dup["normalization_issues"])
    assert any(issue["details_json"]["basis"] == "cert_price_sale_date" for issue in cert_dup["normalization_issues"])

    identity_dup = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="ha-3",
        raw_title="Batman",
        raw_issue="1",
        raw_publisher="DC",
        raw_variant="A",
        raw_grade="CGC 9.8",
        raw_cert_number="77777",
        sale_price="250.00",
        shipping_price="0.00",
        total_price="250.00",
        sale_date="2026-05-21",
    )
    assert any(issue["details_json"]["basis"] == "normalized_identity_total_price_sale_date" for issue in identity_dup["normalization_issues"])


def test_market_sales_list_filters_ordering_and_scope(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-sales-filters@example.com")
    get_settings.cache_clear()
    owner_headers = auth_headers(register_and_login(client, "market-owner@example.com"))
    ops_headers = _ops_headers(client, "ops-sales-filters@example.com")
    ebay = _source_id(session, "eBay")
    heritage = _source_id(session, "Heritage Auctions")

    _create_sale(
        client,
        ops_headers,
        market_source_id=ebay,
        source_listing_id="e1",
        raw_title="Alpha",
        raw_issue="1",
        raw_publisher="Marvel",
        raw_variant="A",
        raw_grade="CGC 9.8",
        raw_cert_number="111",
        sale_price="100.00",
        shipping_price="0.00",
        total_price="100.00",
        sale_date="2026-05-20",
    )
    _create_sale(
        client,
        ops_headers,
        market_source_id=heritage,
        source_listing_id="h1",
        raw_title="Beta",
        raw_issue="2",
        raw_publisher="DC",
        raw_variant="A",
        raw_grade="CGC 9.8",
        raw_cert_number="222",
        sale_price="200.00",
        shipping_price="0.00",
        total_price="200.00",
        sale_date="2026-05-21",
    )
    _create_sale(
        client,
        ops_headers,
        market_source_id=ebay,
        source_listing_id="e2",
        raw_title="Gamma",
        raw_issue="3",
        raw_publisher="Marvel",
        raw_variant="A",
        raw_grade="CGC 9.8",
        raw_cert_number="333",
        sale_price="150.00",
        shipping_price="0.00",
        total_price="150.00",
        sale_date="2026-05-21",
    )

    owner_list = client.get("/market-sales", headers=owner_headers)
    assert owner_list.status_code == 200
    owner_items = owner_list.json()["items"]
    assert [row["sale_date"] for row in owner_items] == ["2026-05-21", "2026-05-21", "2026-05-20"]
    assert [row["source_name"] for row in owner_items] == ["Heritage Auctions", "eBay", "eBay"]

    filtered = client.get("/market-sales", headers=owner_headers, params={"source": "Heritage"})
    assert filtered.status_code == 200
    assert all(row["source_name"] == "Heritage Auctions" for row in filtered.json()["items"])

    assert (
        client.post(
            "/ops/market-sales",
            headers=owner_headers,
            json={
                "market_source_id": ebay,
                "listing_type": "auction",
                "raw_title": "Not allowed",
                "raw_issue": "1",
                "currency_code": "USD",
            },
        ).status_code
        == 403
    )


def test_market_sales_read_paths_do_not_touch_metadata_or_network(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-sales-read@example.com")
    get_settings.cache_clear()
    ops_headers = _ops_headers(client, "ops-sales-read@example.com")
    owner_headers = auth_headers(register_and_login(client, "market-read@example.com"))
    source_id = _source_id(session, "Shortboxed")

    sale = _create_sale(
        client,
        ops_headers,
        market_source_id=source_id,
        source_listing_id="sb-1",
        raw_title="Read Test",
        raw_issue="1",
        raw_publisher="Marvel",
        raw_variant="A",
        raw_grade="CGC 9.8",
        raw_cert_number="9001",
        sale_price="50.00",
        shipping_price="0.00",
        total_price="50.00",
        sale_date="2026-05-22",
    )

    before_audits = session.exec(select(MetadataAudit)).all()
    before_audit_count = len(before_audits)

    def _boom(*args, **kwargs):
        raise AssertionError("network access is not allowed in market-sales reads")

    monkeypatch.setattr("requests.sessions.Session.request", _boom, raising=False)
    monkeypatch.setattr(urllib_request, "urlopen", _boom, raising=False)

    list_rsp = client.get("/market-sales", headers=owner_headers)
    detail_rsp = client.get(f"/market-sales/{sale['id']}", headers=owner_headers)
    ops_rsp = client.get("/ops/market-sales", headers=ops_headers)

    assert list_rsp.status_code == 200
    assert detail_rsp.status_code == 200
    assert ops_rsp.status_code == 200
    assert len(session.exec(select(MetadataAudit)).all()) == before_audit_count


def test_market_sales_routes_registered_once() -> None:
    from app.main import app

    wanted = {"/market-sales", "/market-sales/{market_sale_record_id}", "/ops/market-sales", "/ops/market-sales/{market_sale_record_id}"}
    seen = [route.path for route in app.routes if route.path in wanted]
    assert wanted.issubset(set(seen))
    unique_route_signatures = {
        (route.path, tuple(sorted(route.methods or [])))
        for route in app.routes
        if route.path in wanted
    }
    assert len(unique_route_signatures) == len(seen)

