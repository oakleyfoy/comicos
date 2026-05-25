from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import MarketFmvCompReference, MarketFmvSnapshot, MarketSaleRecord, MarketSource
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


def _seed_trend_day(
    session: Session,
    *,
    identity_key: str,
    sale_id: int,
    snapshot_date: date,
    median_value: str,
    weighted_value: str,
    canonical_issue_id: int | None = None,
    snapshot_scope: str = "raw",
) -> None:
    now = datetime.now(timezone.utc)
    median_row = MarketFmvSnapshot(
        canonical_issue_id=canonical_issue_id,
        metadata_identity_key=identity_key,
        snapshot_scope=snapshot_scope,
        grading_company=None,
        normalized_grade=None,
        currency_code="USD",
        snapshot_date=snapshot_date,
        comp_count=1,
        valuation_method="median_recent_sales",
        estimated_fmv=Decimal(median_value),
        confidence_bucket="high",
        liquidity_bucket="high",
        volatility_bucket="stable",
        stale_data=False,
        evidence_json={"seeded_for_test": True, "identity_key": identity_key},
        created_at=now,
        updated_at=now,
    )
    weighted_row = MarketFmvSnapshot(
        canonical_issue_id=canonical_issue_id,
        metadata_identity_key=identity_key,
        snapshot_scope=snapshot_scope,
        grading_company=None,
        normalized_grade=None,
        currency_code="USD",
        snapshot_date=snapshot_date,
        comp_count=1,
        valuation_method="weighted_recent_sales",
        estimated_fmv=Decimal(weighted_value),
        confidence_bucket="high",
        liquidity_bucket="high",
        volatility_bucket="stable",
        stale_data=False,
        evidence_json={"seeded_for_test": True, "identity_key": identity_key},
        created_at=now,
        updated_at=now,
    )
    session.add(median_row)
    session.add(weighted_row)
    session.flush()
    session.add(
        MarketFmvCompReference(
            market_fmv_snapshot_id=int(median_row.id or 0),
            market_sale_record_id=sale_id,
            weighting_factor=1.0,
            included_reason="eligible_comp",
            excluded_reason=None,
            created_at=now,
        )
    )
    session.add(
        MarketFmvCompReference(
            market_fmv_snapshot_id=int(weighted_row.id or 0),
            market_sale_record_id=sale_id,
            weighting_factor=1.0,
            included_reason="eligible_comp",
            excluded_reason=None,
            created_at=now,
        )
    )
    session.commit()


def _seed_trend_series(
    client: TestClient,
    headers: dict[str, str],
    session: Session,
    *,
    source_id: int,
    identity_key: str,
    day_offsets: list[int],
    median_values: list[str],
    weighted_values: list[str],
    sale_prefix: str,
) -> list[int]:
    sale_ids: list[int] = []
    for index, day_offset in enumerate(day_offsets):
        sale = _create_sale(
            client,
            headers,
            market_source_id=source_id,
            source_listing_id=f"{sale_prefix}-{index + 1}",
            sale_price=weighted_values[index],
            total_price=weighted_values[index],
            sale_date=(date.today() - timedelta(days=day_offset)).isoformat(),
        )
        sale_ids.append(int(sale["id"]))
        _seed_trend_day(
            session,
            identity_key=identity_key,
            sale_id=int(sale["id"]),
            snapshot_date=date.today() - timedelta(days=day_offset),
            median_value=median_values[index],
            weighted_value=weighted_values[index],
        )
    return sale_ids


def _generate(client: TestClient, headers: dict[str, str]):
    response = client.post("/ops/market-trends/generate", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_market_trends_generate_deterministic_directions_and_liquidity(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-market-trends@example.com")
    headers = _ops_headers(client, "ops-market-trends@example.com")
    owner_headers = _owner_headers(client, "owner-market-trends@example.com")
    source_id = _source_id(session, "eBay")

    rising_identity = "Image|Invincible|trend-rising|Cover A"
    falling_identity = "Image|Invincible|trend-falling|Cover A"
    stable_identity = "Image|Invincible|trend-stable|Cover A"
    volatile_identity = "Image|Invincible|trend-volatile|Cover A"

    _seed_trend_series(
        client,
        headers,
        session,
        source_id=source_id,
        identity_key=rising_identity,
        day_offsets=[40, 30, 20, 10, 1],
        median_values=["100.00", "102.00", "105.00", "108.00", "111.00"],
        weighted_values=["101.00", "104.00", "107.00", "110.00", "113.00"],
        sale_prefix="trend-rising",
    )
    _seed_trend_series(
        client,
        headers,
        session,
        source_id=source_id,
        identity_key=falling_identity,
        day_offsets=[200, 190, 180, 170, 100, 90],
        median_values=["200.00", "196.00", "192.00", "188.00", "184.00", "180.00"],
        weighted_values=["198.00", "194.00", "190.00", "186.00", "182.00", "178.00"],
        sale_prefix="trend-falling",
    )
    _seed_trend_series(
        client,
        headers,
        session,
        source_id=source_id,
        identity_key=stable_identity,
        day_offsets=[90, 70, 50, 30],
        median_values=["100.00", "100.00", "100.00", "100.00"],
        weighted_values=["100.00", "100.00", "100.00", "100.00"],
        sale_prefix="trend-stable",
    )
    _seed_trend_series(
        client,
        headers,
        session,
        source_id=source_id,
        identity_key=volatile_identity,
        day_offsets=[120, 100, 80, 60, 40],
        median_values=["100.00", "180.00", "90.00", "175.00", "105.00"],
        weighted_values=["110.00", "190.00", "85.00", "185.00", "95.00"],
        sale_prefix="trend-volatile",
    )

    _generate(client, headers)

    first = client.get("/market-trends?trend_window=one_year", headers=owner_headers)
    second = client.get("/market-trends?trend_window=one_year", headers=owner_headers)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert [row["id"] for row in first.json()["items"]] == [row["id"] for row in second.json()["items"]]

    items = first.json()["items"]
    rows_by_identity = {row["metadata_identity_key"]: row for row in items if row["trend_window"] == "one_year"}
    assert {row["trend_direction"] for row in rows_by_identity.values()} >= {"rising", "falling", "stable", "volatile"}
    assert {row["liquidity_direction"] for row in rows_by_identity.values()} >= {"improving", "weakening"}

    rising_row = rows_by_identity[rising_identity]
    rising_detail = client.get(f"/market-trends/{rising_row['id']}", headers=owner_headers)
    assert rising_detail.status_code == 200, rising_detail.text
    rising_detail_payload = rising_detail.json()
    assert Decimal(str(rising_detail_payload["evidence_json"]["weighted_median_divergence_pct"])) > 0
    assert rising_detail_payload["evidence_items"]
    assert {item["evidence_type"] for item in rising_detail_payload["evidence_items"]} >= {
        "comp_reference",
        "fmv_snapshot",
        "liquidity_signal",
        "volatility_signal",
    }
    assert "forecast" not in str(rising_detail_payload["evidence_json"]).lower()
    assert "speculation" not in str(rising_detail_payload["evidence_json"]).lower()


def test_market_trends_surface_stale_rows_and_do_not_mutate_records(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-market-trends-stale@example.com")
    headers = _ops_headers(client, "ops-market-trends-stale@example.com")
    owner_headers = _owner_headers(client, "owner-market-trends-stale@example.com")
    source_id = _source_id(session, "Heritage Auctions")

    stale_identity = "Image|Invincible|trend-stale|Cover A"
    sale = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="trend-stale-1",
        sale_price="50.00",
        total_price="50.00",
        sale_date=(date.today() - timedelta(days=500)).isoformat(),
    )
    _seed_trend_day(
        session,
        identity_key=stale_identity,
        sale_id=int(sale["id"]),
        snapshot_date=date.today() - timedelta(days=500),
        median_value="50.00",
        weighted_value="55.00",
    )
    _seed_trend_day(
        session,
        identity_key=stale_identity,
        sale_id=int(sale["id"]),
        snapshot_date=date.today() - timedelta(days=490),
        median_value="55.00",
        weighted_value="60.00",
    )

    before_sale = session.get(MarketSaleRecord, int(sale["id"]))
    assert before_sale is not None
    before_metadata = dict(before_sale.source_metadata_json or {})
    before_norm = before_sale.normalized_title, before_sale.normalized_issue, before_sale.normalized_publisher, before_sale.normalized_variant

    _generate(client, headers)

    after_sale = session.get(MarketSaleRecord, int(sale["id"]))
    assert after_sale is not None
    assert after_sale.source_metadata_json == before_metadata
    assert (after_sale.normalized_title, after_sale.normalized_issue, after_sale.normalized_publisher, after_sale.normalized_variant) == before_norm

    stale_list = client.get("/market-trends?trend_window=one_year&stale_data=true", headers=owner_headers)
    assert stale_list.status_code == 200, stale_list.text
    stale_items = [row for row in stale_list.json()["items"] if row["metadata_identity_key"] == stale_identity]
    assert stale_items and stale_items[0]["stale_data"] is True

    stale_detail = client.get(f"/market-trends/{stale_items[0]['id']}", headers=owner_headers)
    assert stale_detail.status_code == 200, stale_detail.text
    payload = stale_detail.json()
    assert payload["stale_data"] is True
    assert {item["evidence_type"] for item in payload["evidence_items"]} >= {
        "comp_reference",
        "fmv_snapshot",
        "liquidity_signal",
        "volatility_signal",
    }


def test_market_trends_allow_filtered_ops_queries(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-market-trends-filtered@example.com")
    headers = _ops_headers(client, "ops-market-trends-filtered@example.com")
    source_id = _source_id(session, "ComicLink")

    filtered_identity = "Image|Invincible|trend-filtered|Cover A"
    _seed_trend_series(
        client,
        headers,
        session,
        source_id=source_id,
        identity_key=filtered_identity,
        day_offsets=[25, 15, 8, 2],
        median_values=["80.00", "85.00", "90.00", "95.00"],
        weighted_values=["82.00", "88.00", "92.00", "98.00"],
        sale_prefix="trend-filtered",
    )

    _generate(client, headers)

    response = client.get(
        "/ops/market-trends?trend_window=one_year&trend_direction=rising&snapshot_scope=raw&currency=USD",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert items
    assert all(row["snapshot_scope"] == "raw" for row in items)
    assert all(row["currency_code"] == "USD" for row in items)
    assert all(row["trend_direction"] == "rising" for row in items)
