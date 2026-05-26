from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import InventoryFmvSnapshot, MarketSaleMatchSuggestion, MarketSaleNormalizationIssue, MarketSaleRecord, MarketSaleReviewAction, MarketSource
from app.services.market_sales import ensure_system_market_sources
from test_inventory import auth_headers, register_and_login


def _ops_headers(client: TestClient, email: str) -> dict[str, str]:
    get_settings.cache_clear()
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
        "sale_date": overrides.pop("sale_date", "2026-05-20"),
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
    review_state: str = "approved",
    confidence_bucket: str = "high",
    deterministic_score: float = 0.94,
) -> MarketSaleMatchSuggestion:
    now = datetime.now(timezone.utc)
    row = MarketSaleMatchSuggestion(
        market_sale_record_id=sale_id,
        canonical_issue_id=None,
        canonical_series_id=None,
        canonical_publisher_id=None,
        suggested_identity_key=None,
        suggestion_type="exact_identity_key",
        confidence_bucket=confidence_bucket,
        deterministic_score=deterministic_score,
        confidence_version="market-sale-match-suggestion-v1",
        evidence_json={"seeded_for_test": True},
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


def _comp_eligibility_response(client: TestClient, headers: dict[str, str], sale_id: int):
    response = client.get(f"/ops/market-sales/{sale_id}/comp-eligibility", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_market_comp_eligibility_raw_comp_is_eligible(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-comp-raw@example.com")
    headers = _ops_headers(client, "ops-comp-raw@example.com")
    source_id = _source_id(session, "eBay")

    sale = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        raw_title="Invincible",
        raw_issue="1",
        raw_publisher="Image",
        sale_price="42.00",
        total_price="42.00",
    )
    _seed_match_suggestion(session, sale_id=sale["id"], review_state="approved", confidence_bucket="very_high")

    payload = _comp_eligibility_response(client, headers, sale["id"])
    assert payload["eligibility_status"] == "eligible"
    assert payload["eligibility_classification"] == "eligible_raw_comp"


def test_market_comp_eligibility_graded_comp_is_eligible(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-comp-graded@example.com")
    headers = _ops_headers(client, "ops-comp-graded@example.com")
    source_id = _source_id(session, "Heritage Auctions")

    sale = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        raw_title="Invincible",
        raw_issue="1",
        raw_publisher="Image",
        raw_grade="cgc 9.8",
        is_graded=True,
        grading_company="CGC",
        sale_price="150.00",
        total_price="150.00",
    )
    _seed_match_suggestion(session, sale_id=sale["id"], review_state="approved", confidence_bucket="high")

    payload = _comp_eligibility_response(client, headers, sale["id"])
    assert payload["eligibility_status"] == "eligible"
    assert payload["eligibility_classification"] == "eligible_graded_comp"


def test_market_comp_eligibility_missing_price_is_ineligible(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-comp-missing-price@example.com")
    headers = _ops_headers(client, "ops-comp-missing-price@example.com")
    source_id = _source_id(session, "Shortboxed")

    sale = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        sale_price=None,
        total_price=None,
    )

    payload = _comp_eligibility_response(client, headers, sale["id"])
    assert payload["eligibility_status"] == "ineligible"
    assert payload["eligibility_classification"] == "ineligible_missing_price"


def test_market_comp_eligibility_unsupported_currency_is_ineligible(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-comp-currency@example.com")
    headers = _ops_headers(client, "ops-comp-currency@example.com")
    source_id = _source_id(session, "ComicLink")

    sale = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        currency_code="INR",
        sale_price="50.00",
        total_price="50.00",
    )

    payload = _comp_eligibility_response(client, headers, sale["id"])
    assert payload["eligibility_status"] == "ineligible"
    assert payload["eligibility_classification"] == "ineligible_unsupported_currency"


def test_market_comp_eligibility_duplicate_listing_is_ineligible(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-comp-duplicate@example.com")
    headers = _ops_headers(client, "ops-comp-duplicate@example.com")
    source_id = _source_id(session, "eBay")

    sale = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="dup-1",
        sale_price="75.00",
        total_price="75.00",
    )
    assert client.post(f"/ops/market-sales/{sale['id']}/flag-duplicate", headers=headers, json={"reason": "duplicate"}).status_code == 200

    payload = _comp_eligibility_response(client, headers, sale["id"])
    assert payload["eligibility_status"] == "ineligible"
    assert payload["eligibility_classification"] == "ineligible_duplicate_listing"


def test_market_comp_eligibility_ignored_record_is_ineligible(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-comp-ignored@example.com")
    headers = _ops_headers(client, "ops-comp-ignored@example.com")
    source_id = _source_id(session, "HipComic")

    sale = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="ign-1",
        sale_price="80.00",
        total_price="80.00",
    )
    assert client.post(f"/ops/market-sales/{sale['id']}/ignore", headers=headers, json={"reason": "ignored"}).status_code == 200

    payload = _comp_eligibility_response(client, headers, sale["id"])
    assert payload["eligibility_status"] == "ineligible"
    assert payload["eligibility_classification"] == "ineligible_ignored_record"


def test_market_comp_eligibility_invalid_grade_is_ineligible(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-comp-invalid-grade@example.com")
    headers = _ops_headers(client, "ops-comp-invalid-grade@example.com")
    source_id = _source_id(session, "Heritage Auctions")

    sale = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        raw_grade="CGC",
        is_graded=True,
        grading_company="CGC",
        sale_price="125.00",
        total_price="125.00",
    )

    payload = _comp_eligibility_response(client, headers, sale["id"])
    assert payload["eligibility_status"] == "ineligible"
    assert payload["eligibility_classification"] == "ineligible_invalid_grade"


def test_market_comp_eligibility_unresolved_identity_is_ineligible(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-comp-identity@example.com")
    headers = _ops_headers(client, "ops-comp-identity@example.com")
    source_id = _source_id(session, "Shortboxed")

    sale = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        raw_publisher=None,
        sale_price="140.00",
        total_price="140.00",
    )

    payload = _comp_eligibility_response(client, headers, sale["id"])
    assert payload["eligibility_status"] == "ineligible"
    assert payload["eligibility_classification"] == "ineligible_unresolved_identity"


def test_market_comp_eligibility_approved_canonical_suggestion_makes_record_eligible(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-comp-approved@example.com")
    headers = _ops_headers(client, "ops-comp-approved@example.com")
    source_id = _source_id(session, "eBay")

    sale = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="approved-1",
        sale_price="33.00",
        total_price="33.00",
    )
    _seed_match_suggestion(session, sale_id=sale["id"], review_state="approved", confidence_bucket="high")

    payload = _comp_eligibility_response(client, headers, sale["id"])
    assert payload["eligibility_status"] == "eligible"
    assert payload["eligibility_classification"] == "eligible_raw_comp"
    assert payload["canonical_match_state"] == "approved"


def test_market_comp_eligibility_is_deterministic_and_read_only(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-comp-deterministic@example.com")
    headers = _ops_headers(client, "ops-comp-deterministic@example.com")
    source_id = _source_id(session, "Heritage Auctions")

    sale_a = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="order-a",
        sale_price="21.00",
        shipping_price="4.00",
        total_price="25.00",
        sale_date="2026-05-21",
    )
    sale_b = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="order-b",
        sale_price="19.00",
        shipping_price="1.00",
        total_price="20.00",
        sale_date="2026-05-20",
    )
    _seed_match_suggestion(session, sale_id=sale_a["id"], review_state="approved", confidence_bucket="high")
    _seed_match_suggestion(session, sale_id=sale_b["id"], review_state="approved", confidence_bucket="high")

    before_sale_a = session.get(MarketSaleRecord, sale_a["id"])
    before_issue_count = len(session.exec(select(MarketSaleNormalizationIssue)).all())
    before_review_count = len(session.exec(select(MarketSaleReviewAction)).all())
    before_fmv_count = len(session.exec(select(InventoryFmvSnapshot)).all())
    assert before_sale_a is not None
    before_metadata_json = dict(before_sale_a.source_metadata_json or {})
    before_updated_at = before_sale_a.updated_at

    first = client.get("/ops/market-comp-eligibility", headers=headers)
    second = client.get("/ops/market-comp-eligibility", headers=headers)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert [row["id"] for row in first.json()["items"]] == [row["id"] for row in second.json()["items"]]
    assert [row["id"] for row in first.json()["items"][:2]] == [sale_a["id"], sale_b["id"]]

    detail = client.get(f"/ops/market-sales/{sale_a['id']}/comp-eligibility", headers=headers)
    assert detail.status_code == 200, detail.text
    detail_payload = detail.json()
    assert detail_payload["sale_price"] == "21.00"
    assert detail_payload["total_price"] == "25.00"

    after_sale_a = session.get(MarketSaleRecord, sale_a["id"])
    assert after_sale_a is not None
    assert after_sale_a.source_metadata_json == before_metadata_json
    assert after_sale_a.updated_at == before_updated_at
    assert len(session.exec(select(MarketSaleNormalizationIssue)).all()) == before_issue_count
    assert len(session.exec(select(MarketSaleReviewAction)).all()) == before_review_count
    assert len(session.exec(select(InventoryFmvSnapshot)).all()) == before_fmv_count

