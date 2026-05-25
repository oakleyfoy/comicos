from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import MarketFmvSnapshot, MarketSaleMatchSuggestion, MarketSaleRecord, MarketSource
from app.services.market_sales import ensure_system_market_sources
from test_inventory import auth_headers, register_and_login


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


def _seed_approved_suggestion(session: Session, *, sale_id: int, identity_key: str, deterministic_score: float = 0.97) -> None:
    now = datetime.now(timezone.utc)
    row = MarketSaleMatchSuggestion(
        market_sale_record_id=sale_id,
        canonical_issue_id=1,
        canonical_series_id=None,
        canonical_publisher_id=None,
        suggested_identity_key=identity_key,
        suggestion_type="exact_identity_key",
        confidence_bucket="very_high",
        deterministic_score=deterministic_score,
        confidence_version="market-sale-match-suggestion-v1",
        evidence_json={"seeded_for_test": True, "metadata_identity_key": identity_key},
        review_state="approved",
        reviewed_by_user_id=None,
        reviewed_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.commit()


def test_market_comps_groups_and_classifications(client: TestClient, session: Session, monkeypatch) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-market-comps@example.com")
    headers = _ops_headers(client, "ops-market-comps@example.com")
    source_id = _source_id(session, "eBay")
    identity_key = "Image|Invincible|1|Cover A"

    sale_included = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="comps-included",
        sale_price="42.00",
        total_price="42.00",
        sale_date=date.today().isoformat(),
    )
    sale_wrong_scope = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="comps-graded",
        sale_price="92.00",
        total_price="92.00",
        sale_date=date.today().isoformat(),
        is_graded=True,
        grading_company="CGC",
        raw_grade="CGC 9.8",
    )
    sale_wrong_grade = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="comps-graded-9-6",
        sale_price="88.00",
        total_price="88.00",
        sale_date=date.today().isoformat(),
        is_graded=True,
        grading_company="CGC",
        raw_grade="CGC 9.6",
    )
    sale_stale = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="comps-stale",
        sale_price="10.00",
        total_price="10.00",
        sale_date=(date.today() - timedelta(days=400)).isoformat(),
    )
    sale_duplicate = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="comps-dup",
        sale_price="42.00",
        total_price="42.00",
        sale_date=date.today().isoformat(),
    )
    sale_unresolved = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="comps-unresolved",
        raw_publisher=None,
        sale_price="11.00",
        total_price="11.00",
        sale_date=date.today().isoformat(),
    )
    for sale_id in [sale_included["id"], sale_wrong_scope["id"], sale_wrong_grade["id"], sale_stale["id"], sale_duplicate["id"]]:
        _seed_approved_suggestion(session, sale_id=sale_id, identity_key=identity_key)
    assert client.post(f"/ops/market-sales/{sale_duplicate['id']}/flag-duplicate", headers=headers, json={"reason": "duplicate"}).status_code == 200

    response = client.get("/ops/market-comps?include_excluded=true", headers=headers)
    assert response.status_code == 200, response.text
    groups = response.json()["items"]
    classifications = [comp["comp_classification"] for group in groups for comp in group["included_comps"] + group["excluded_comps"]]
    assert "included_comp" in classifications
    assert "excluded_wrong_scope" in classifications
    assert "excluded_wrong_grade" in classifications
    assert "excluded_stale" in classifications
    assert "excluded_duplicate" in classifications
    assert "excluded_unresolved_identity" in classifications


def test_market_comps_are_deterministic_and_surface_quality_signals(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-market-comps-deterministic@example.com")
    headers = _owner_headers(client, "owner-market-comps-deterministic@example.com")
    source_ebay = _source_id(session, "eBay")
    source_heritage = _source_id(session, "Heritage Auctions")
    identity_key = "Image|Invincible|2|Cover A"

    first_sale = _create_sale(
        client,
        headers,
        market_source_id=source_ebay,
        source_listing_id="det-1",
        sale_price="100.00",
        total_price="100.00",
        sale_date=date.today().isoformat(),
    )
    second_sale = _create_sale(
        client,
        headers,
        market_source_id=source_heritage,
        source_listing_id="det-2",
        sale_price="120.00",
        total_price="120.00",
        sale_date=date.today().isoformat(),
    )
    _seed_approved_suggestion(session, sale_id=first_sale["id"], identity_key=identity_key)
    _seed_approved_suggestion(session, sale_id=second_sale["id"], identity_key=identity_key)

    first = client.get(f"/market-comps/by-identity/{identity_key}?include_excluded=false", headers=headers)
    second = client.get(f"/market-comps/by-identity/{identity_key}?include_excluded=false", headers=headers)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    first_groups = first.json()["items"]
    second_groups = second.json()["items"]
    assert [group["group_key"] for group in first_groups] == [group["group_key"] for group in second_groups]
    assert first_groups[0]["quality_signals"]["comp_count"] == 2
    assert first_groups[0]["quality_signals"]["source_diversity_count"] == 2
    assert first_groups[0]["quality_signals"]["stale_data_warning"] is False


def test_market_comps_owner_scope_ops_visibility_and_read_only(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-market-comps-scope@example.com")
    owner_headers = _owner_headers(client, "owner-market-comps-scope@example.com")
    intruder_headers = auth_headers(register_and_login(client, "intruder-market-comps-scope@example.com"))
    source_id = _source_id(session, "Shortboxed")

    sale = _create_sale(
        client,
        owner_headers,
        market_source_id=source_id,
        source_listing_id="scope-1",
        sale_price="55.00",
        total_price="55.00",
        sale_date=date.today().isoformat(),
    )
    _seed_approved_suggestion(session, sale_id=sale["id"], identity_key="Image|Invincible|3|Cover A")

    monkeypatch.setattr(
        "app.services.market_fmv.generate_market_fmv_snapshots",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("FMV recalculation should not run")),
        raising=False,
    )

    before_sale = session.get(MarketSaleRecord, sale["id"])
    assert before_sale is not None
    before_metadata = dict(before_sale.source_metadata_json or {})

    owner_rsp = client.get("/market-comps", headers=owner_headers)
    ops_rsp = client.get("/ops/market-comps", headers=intruder_headers)
    assert owner_rsp.status_code == 200, owner_rsp.text
    assert ops_rsp.status_code == 403

    after_sale = session.get(MarketSaleRecord, sale["id"])
    assert after_sale is not None
    assert after_sale.source_metadata_json == before_metadata


def test_market_fmv_snapshot_comps_are_read_only_and_traceable(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-market-fmv-comps@example.com")
    headers = _ops_headers(client, "ops-market-fmv-comps@example.com")
    source_id = _source_id(session, "ComicLink")
    identity_key = "Image|Invincible|4|Cover A"

    fresh_sale = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="snapshot-fresh",
        sale_price="75.00",
        total_price="75.00",
        sale_date=(date.today() - timedelta(days=7)).isoformat(),
    )
    stale_sale = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="snapshot-stale",
        sale_price="175.00",
        total_price="175.00",
        sale_date=(date.today() - timedelta(days=400)).isoformat(),
    )
    _seed_approved_suggestion(session, sale_id=fresh_sale["id"], identity_key=identity_key)
    _seed_approved_suggestion(session, sale_id=stale_sale["id"], identity_key=identity_key)

    generate = client.post("/ops/market-fmv/generate", headers=headers)
    assert generate.status_code == 200, generate.text
    snapshot_id = generate.json()["snapshots"][0]["id"]

    before_snapshot_count = len(session.exec(select(MarketFmvSnapshot)).all())
    before_sale_count = len(session.exec(select(MarketSaleRecord)).all())
    response = client.get(f"/market-fmv/{snapshot_id}/comps?include_excluded=true", headers=headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["snapshot"]["id"] == snapshot_id
    flattened = [comp["market_sale_record_id"] for group in payload["items"] for comp in group["included_comps"] + group["excluded_comps"]]
    assert fresh_sale["id"] in flattened
    assert stale_sale["id"] in flattened
    assert len(session.exec(select(MarketFmvSnapshot)).all()) == before_snapshot_count
    assert len(session.exec(select(MarketSaleRecord)).all()) == before_sale_count

