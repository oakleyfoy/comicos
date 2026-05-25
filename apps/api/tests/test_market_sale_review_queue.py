from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import MarketSaleRecord, MarketSaleReviewAction, MarketSource
from app.services.market_sales import ensure_system_market_sources
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
        "raw_title": overrides.pop("raw_title", "Amazing Spider-Man"),
        "raw_issue": overrides.pop("raw_issue", "1"),
        "raw_publisher": overrides.pop("raw_publisher", "Marvel"),
        "raw_variant": overrides.pop("raw_variant", None),
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
        "source_metadata_json": overrides.pop("source_metadata_json", {"source": "review-test"}),
        "images": overrides.pop("images", []),
    }
    payload.update(overrides)
    response = client.post("/ops/market-sales", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_market_sale_review_queue_classification_priority_and_summary(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-review@example.com")
    get_settings.cache_clear()
    headers = _ops_headers(client, "ops-review@example.com")
    source_id = _source_id(session, "eBay")

    ready = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="ready-1",
        raw_variant=None,
        raw_grade=None,
        raw_cert_number=None,
        currency_code="USD",
        sale_price="50.00",
        total_price="50.00",
    )
    unsupported = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="currency-1",
        raw_variant=None,
        raw_grade=None,
        raw_cert_number=None,
        currency_code="BRL",
        sale_price="50.00",
        total_price="50.00",
    )
    _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="dup-1",
        raw_variant=None,
        raw_grade=None,
        raw_cert_number="CERT-1",
        sale_price="75.00",
        total_price="75.00",
        sale_date="2026-05-21",
    )
    duplicate = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="dup-2",
        raw_variant=None,
        raw_grade=None,
        raw_cert_number="CERT-1",
        sale_price="75.00",
        total_price="75.00",
        sale_date="2026-05-21",
    )

    queue_rsp = client.get("/ops/market-sale-review-queue", headers=headers)
    assert queue_rsp.status_code == 200, queue_rsp.text
    queue = queue_rsp.json()
    assert queue["total"] == 4
    assert queue["items"][0]["queue_priority"] == "critical"
    assert queue["items"][0]["queue_classification"] == "unsupported_currency"
    assert any(item["id"] == unsupported["id"] and item["queue_classification"] == "unsupported_currency" for item in queue["items"])
    assert any(item["id"] == duplicate["id"] and item["queue_classification"] == "possible_duplicate" for item in queue["items"])
    assert any(item["id"] == ready["id"] and item["queue_classification"] == "ready_for_comp_review" for item in queue["items"])

    summary = client.get("/ops/market-sale-review-queue/summary", headers=headers).json()
    assert summary["total"] == 4
    assert summary["by_priority"]["critical"] == 1
    assert summary["by_priority"]["high"] == 1
    assert summary["by_priority"]["low"] >= 1
    assert summary["by_classification"]["unsupported_currency"] == 1
    assert summary["by_classification"]["possible_duplicate"] == 1


def test_market_sale_review_manual_updates_preserve_raw_fields_and_issue_history(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-manual@example.com")
    get_settings.cache_clear()
    headers = _ops_headers(client, "ops-manual@example.com")
    source_id = _source_id(session, "Heritage Auctions")

    sale = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="manual-1",
        raw_title="  Amazing Spider-Man  ",
        raw_issue=" no. 001 ",
        raw_variant="A / Virgin",
        raw_grade=" cgc 9.8 ",
        raw_cert_number=" cert 9 ",
        currency_code="USD",
        sale_price="125.00",
        total_price="125.00",
    )
    issues_before = client.get(f"/ops/market-sales/{sale['id']}/normalization-issues", headers=headers).json()
    assert len(issues_before) >= 1

    update_rsp = client.patch(
        f"/ops/market-sales/{sale['id']}/normalization",
        headers=headers,
        json={
            "normalized_title": "Amazing Spider-Man Deluxe",
            "normalized_issue": "1",
            "normalized_publisher": "Marvel",
            "normalized_variant": "A / Virgin",
            "normalized_grade": "CGC 9.8",
            "normalized_cert_number": "CERT 9",
            "normalization_status": "normalized",
            "mark_reviewed": True,
            "review_note": "checked manually",
        },
    )
    assert update_rsp.status_code == 200, update_rsp.text
    detail = update_rsp.json()
    assert detail["review_status"] == "reviewed"
    assert detail["normalized_title"] == "Amazing Spider-Man Deluxe"
    assert detail["raw_title"].strip() == "Amazing Spider-Man"
    assert detail["raw_issue"].strip() == "no. 001"
    assert len(detail["review_actions"]) == 1
    assert detail["review_actions"][0]["action_type"] == "manual_normalization_update"

    row = session.get(MarketSaleRecord, sale["id"])
    assert row is not None
    assert row.raw_title == "Amazing Spider-Man"
    assert row.raw_issue == "no. 001"
    assert row.review_status == "reviewed"
    assert row.normalized_title == "Amazing Spider-Man Deluxe"
    assert len(session.exec(select(MarketSaleReviewAction).where(MarketSaleReviewAction.market_sale_record_id == sale["id"])).all()) == 1
    assert len(client.get(f"/ops/market-sales/{sale['id']}/normalization-issues", headers=headers).json()) == len(issues_before)


def test_market_sale_ignore_and_flag_duplicate_actions(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-actions@example.com")
    get_settings.cache_clear()
    headers = _ops_headers(client, "ops-actions@example.com")
    source_id = _source_id(session, "Shortboxed")

    ignored_sale = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="ignore-1",
        raw_variant=None,
        raw_grade=None,
        raw_cert_number=None,
        sale_price="35.00",
        total_price="35.00",
    )
    ignore_rsp = client.post(
        f"/ops/market-sales/{ignored_sale['id']}/ignore",
        headers=headers,
        json={"reason": "out of scope"},
    )
    assert ignore_rsp.status_code == 200, ignore_rsp.text
    ignore_detail = ignore_rsp.json()
    assert ignore_detail["review_status"] == "ignored"
    assert ignore_detail["normalization_status"] == "ignored"
    assert len(ignore_detail["review_actions"]) == 1
    assert ignore_detail["review_actions"][0]["action_type"] == "ignore_record"

    duplicate_sale = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="dup-action-1",
        raw_variant=None,
        raw_grade=None,
        raw_cert_number=None,
        sale_price="40.00",
        total_price="40.00",
    )
    flag_rsp = client.post(
        f"/ops/market-sales/{duplicate_sale['id']}/flag-duplicate",
        headers=headers,
        json={"reason": "same source listing"},
    )
    assert flag_rsp.status_code == 200, flag_rsp.text
    flag_detail = flag_rsp.json()
    assert flag_detail["review_status"] == "duplicate_flagged"
    assert len(flag_detail["review_actions"]) == 1
    assert flag_detail["review_actions"][0]["action_type"] == "flag_duplicate"

    queue = client.get("/ops/market-sale-review-queue", headers=headers, params={"classification": "possible_duplicate"}).json()
    assert any(item["id"] == duplicate_sale["id"] for item in queue["items"])


def test_market_sale_review_visibility_and_access_control(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-access@example.com")
    get_settings.cache_clear()
    ops_headers = _ops_headers(client, "ops-access@example.com")
    owner_headers = auth_headers(register_and_login(client, "market-owner@example.com"))
    source_id = _source_id(session, "ComicLink")

    sale = _create_sale(
        client,
        ops_headers,
        market_source_id=source_id,
        source_listing_id="access-1",
        raw_variant=None,
        raw_grade=None,
        raw_cert_number=None,
        sale_price="60.00",
        total_price="60.00",
    )

    assert client.get("/market-sale-review-queue", headers=owner_headers).status_code == 200
    assert client.get("/market-sale-review-queue/summary", headers=owner_headers).status_code == 200
    assert client.get(f"/market-sales/{sale['id']}/normalization-issues", headers=owner_headers).status_code == 200
    assert client.get("/ops/market-sale-review-queue", headers=owner_headers).status_code == 403
    assert client.post(f"/ops/market-sales/{sale['id']}/ignore", headers=owner_headers).status_code == 403


def test_market_sale_review_queue_reads_do_not_trigger_fmv_or_fuzzy_normalization(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-guardrail@example.com")
    get_settings.cache_clear()
    headers = _ops_headers(client, "ops-guardrail@example.com")
    source_id = _source_id(session, "HipComic")

    sale = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="guardrail-1",
        raw_variant=None,
        raw_grade=None,
        raw_cert_number=None,
        sale_price="80.00",
        total_price="80.00",
    )

    def _boom(*args, **kwargs):
        raise AssertionError("unexpected deterministic-review dependency")

    monkeypatch.setattr("app.services.market_sales.normalize_publisher_name", _boom, raising=False)
    monkeypatch.setattr("app.services.market_sales.normalize_issue_number", _boom, raising=False)
    monkeypatch.setattr("app.services.inventory.get_inventory_fmv_history", _boom, raising=False)
    monkeypatch.setattr(
        "app.services.canonical_issue_link_suggestions.generate_canonical_issue_suggestions_for_owner",
        _boom,
        raising=False,
    )

    assert client.get("/ops/market-sale-review-queue", headers=headers).status_code == 200
    assert client.get("/ops/market-sale-review-queue/summary", headers=headers).status_code == 200
    assert client.get(f"/ops/market-sales/{sale['id']}/normalization-issues", headers=headers).status_code == 200
    assert (
        client.patch(
            f"/ops/market-sales/{sale['id']}/normalization",
            headers=headers,
            json={
                "normalized_title": "Guardrail Test",
                "normalized_issue": "1",
                "normalized_publisher": "HipComic",
                "normalized_variant": None,
                "normalized_grade": None,
                "normalized_cert_number": None,
                "normalization_status": "normalized",
                "mark_reviewed": True,
            },
        ).status_code
        == 200
    )
    assert session.get(MarketSaleRecord, sale["id"]) is not None
