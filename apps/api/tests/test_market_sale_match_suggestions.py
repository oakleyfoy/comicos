from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import (
    InventoryCopy,
    MarketSaleMatchSuggestion,
    MarketSaleRecord,
    MarketSource,
    MetadataAlias,
)
from app.services.metadata_enrichment import build_metadata_identity_components, build_metadata_identity_key
from app.services.market_sales import ensure_system_market_sources
from test_inventory import auth_headers, create_order, register_and_login


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


def _latest_inventory_copy(session: Session) -> InventoryCopy:
    row = session.exec(select(InventoryCopy).order_by(InventoryCopy.id.desc())).first()
    assert row is not None
    return row


def _set_identity_key(session: Session, copy: InventoryCopy, key: str) -> None:
    copy.metadata_identity_key = key
    session.add(copy)
    session.commit()


def test_exact_identity_key_and_registry_match_generation(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-match-exact@example.com")
    headers = _ops_headers(client, "ops-match-exact@example.com")
    source_id = _source_id(session, "eBay")

    create_order(
        client,
        register_and_login(client, "inventory-match-exact@example.com"),
        items=[
            {
                "title": "Invincible",
                "publisher": "Image",
                "issue_number": "1",
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
    copy = _latest_inventory_copy(session)
    exact_key = build_metadata_identity_key(
        build_metadata_identity_components(
            publisher="Image",
            series_title="Invincible",
            issue_number="1",
            variant="Cover A",
        )
    )
    _set_identity_key(session, copy, exact_key)
    alias_count_before = len(session.exec(select(MetadataAlias)).all())

    sale = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="match-exact-1",
        raw_title="Invincible",
        raw_issue="1",
        raw_publisher="Image",
        raw_variant="Cover A",
        source_metadata_json={"barcode": "123456789012"},
    )

    response = client.post(f"/ops/market-sales/{sale['id']}/generate-match-suggestions", headers=headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    types = {row["suggestion_type"] for row in payload["suggestions"]}
    assert "exact_identity_key" in types
    assert "normalized_title_issue_publisher" in types
    assert payload["suggestion_count"] == len(payload["suggestions"])
    assert session.get(InventoryCopy, copy.id).metadata_identity_key == exact_key
    assert len(session.exec(select(MetadataAlias)).all()) == alias_count_before

    rerun = client.post(f"/ops/market-sales/{sale['id']}/generate-match-suggestions", headers=headers)
    assert rerun.status_code == 200, rerun.text
    rows = session.exec(select(MarketSaleMatchSuggestion).where(MarketSaleMatchSuggestion.market_sale_record_id == sale["id"])).all()
    signatures = {
        (row.market_sale_record_id, row.canonical_issue_id, row.canonical_series_id, row.suggested_identity_key, row.suggestion_type, row.confidence_version)
        for row in rows
    }
    assert len(rows) == len(signatures)


def test_inventory_context_suggestions_surface_for_variant_mismatch(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-match-inventory@example.com")
    headers = _ops_headers(client, "ops-match-inventory@example.com")
    source_id = _source_id(session, "Heritage Auctions")

    create_order(
        client,
        register_and_login(client, "inventory-match-prefix@example.com"),
        items=[
            {
                "title": "Invincible",
                "publisher": "Image",
                "issue_number": "1",
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
    copy = _latest_inventory_copy(session)
    prefix_key = build_metadata_identity_key(
        build_metadata_identity_components(
            publisher="Image",
            series_title="Invincible",
            issue_number="1",
            variant="Cover A",
        )
    )
    _set_identity_key(session, copy, prefix_key)

    sale = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="match-prefix-1",
        raw_title="Invincible",
        raw_issue="1",
        raw_publisher="Image",
        raw_variant="Cover B",
    )

    response = client.post(f"/ops/market-sales/{sale['id']}/generate-match-suggestions", headers=headers)
    assert response.status_code == 200, response.text
    types = {row["suggestion_type"] for row in response.json()["suggestions"]}
    assert "publisher_series_issue" in types
    assert "inventory_context_supported" in types
    assert "exact_identity_key" not in types


def test_title_issue_only_is_lower_confidence(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-match-title-issue@example.com")
    headers = _ops_headers(client, "ops-match-title-issue@example.com")
    source_id = _source_id(session, "Shortboxed")

    create_order(
        client,
        register_and_login(client, "inventory-match-title@example.com"),
        items=[
            {
                "title": "Invincible",
                "publisher": "Image",
                "issue_number": "1",
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

    sale = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="match-title-issue-1",
        raw_title="Invincible",
        raw_issue="1",
        raw_publisher=None,
        raw_variant=None,
    )

    response = client.post(f"/ops/market-sales/{sale['id']}/generate-match-suggestions", headers=headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    weaker = next(row for row in payload["suggestions"] if row["suggestion_type"] == "normalized_title_issue")
    assert weaker["confidence_bucket"] in {"medium", "low"}
    assert "normalized_title_issue_publisher" not in {row["suggestion_type"] for row in payload["suggestions"]}


def test_barcode_cannot_be_sole_identity_source(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-match-barcode@example.com")
    headers = _ops_headers(client, "ops-match-barcode@example.com")
    source_id = _source_id(session, "HipComic")

    sale = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="match-barcode-1",
        raw_title="Totally Unmatched Comic",
        raw_issue="99",
        raw_publisher="Unknown",
        raw_variant=None,
        source_metadata_json={"barcode": "9780000000000"},
        raw_cert_number="9780000000000",
    )

    response = client.post(f"/ops/market-sales/{sale['id']}/generate-match-suggestions", headers=headers)
    assert response.status_code == 200, response.text
    types = {row["suggestion_type"] for row in response.json()["suggestions"]}
    assert "barcode_supported" not in types
    assert types == {"unresolved_ambiguous"}


def test_unresolved_normalization_issue_reduces_confidence(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-match-penalty@example.com")
    headers = _ops_headers(client, "ops-match-penalty@example.com")
    source_id = _source_id(session, "ComicLink")

    create_order(
        client,
        register_and_login(client, "inventory-match-penalty@example.com"),
        items=[
            {
                "title": "Invincible",
                "publisher": "Image",
                "issue_number": "1",
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
    copy = _latest_inventory_copy(session)
    exact_key = build_metadata_identity_key(
        build_metadata_identity_components(
            publisher="Image",
            series_title="Invincible",
            issue_number="1",
            variant="Cover A",
        )
    )
    _set_identity_key(session, copy, exact_key)

    clean_sale = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="match-penalty-clean",
        raw_title="Invincible",
        raw_issue="1",
        raw_publisher="Image",
        raw_variant="Cover A",
    )
    noisy_sale = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="match-penalty-noisy",
        raw_title="  Invincible  ",
        raw_issue="1",
        raw_publisher="Image",
        raw_variant="Cover A",
        raw_grade="Mint",
    )

    clean_rsp = client.post(f"/ops/market-sales/{clean_sale['id']}/generate-match-suggestions", headers=headers)
    noisy_rsp = client.post(f"/ops/market-sales/{noisy_sale['id']}/generate-match-suggestions", headers=headers)
    assert clean_rsp.status_code == 200
    assert noisy_rsp.status_code == 200
    clean_score = next(
        row["deterministic_score"]
        for row in clean_rsp.json()["suggestions"]
        if row["suggestion_type"] == "exact_identity_key"
    )
    noisy_score = next(
        row["deterministic_score"]
        for row in noisy_rsp.json()["suggestions"]
        if row["suggestion_type"] == "exact_identity_key"
    )
    assert noisy_score < clean_score


def test_review_transitions_and_idempotent_regeneration(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-match-review@example.com")
    headers = _ops_headers(client, "ops-match-review@example.com")
    source_id = _source_id(session, "eBay")

    sale = _create_sale(
        client,
        headers,
        market_source_id=source_id,
        source_listing_id="match-review-1",
        raw_title="Invincible",
        raw_issue="1",
        raw_publisher="Image",
        raw_variant="Cover A",
    )
    generated = client.post(f"/ops/market-sales/{sale['id']}/generate-match-suggestions", headers=headers)
    assert generated.status_code == 200, generated.text
    suggestion_id = generated.json()["suggestions"][0]["id"]

    approve = client.patch(f"/ops/market-match-suggestions/{suggestion_id}/approve", headers=headers)
    assert approve.status_code == 200, approve.text
    assert approve.json()["suggestion"]["review_state"] == "approved"

    reject = client.patch(f"/ops/market-match-suggestions/{suggestion_id}/reject", headers=headers)
    assert reject.status_code == 200, reject.text
    assert reject.json()["suggestion"]["review_state"] == "rejected"

    ignore = client.patch(f"/ops/market-match-suggestions/{suggestion_id}/ignore", headers=headers)
    assert ignore.status_code == 200, ignore.text
    assert ignore.json()["suggestion"]["review_state"] == "ignored"

    rerun = client.post(f"/ops/market-sales/{sale['id']}/generate-match-suggestions", headers=headers)
    assert rerun.status_code == 200, rerun.text
    rows = session.exec(select(MarketSaleMatchSuggestion).where(MarketSaleMatchSuggestion.market_sale_record_id == sale["id"])).all()
    assert len(rows) == len(
        {
            (row.market_sale_record_id, row.canonical_issue_id, row.canonical_series_id, row.suggested_identity_key, row.suggestion_type, row.confidence_version)
            for row in rows
        }
    )
    refreshed = session.get(MarketSaleMatchSuggestion, suggestion_id)
    assert refreshed is not None
    assert refreshed.review_state == "ignored"


def test_owner_read_scope_and_ops_access_control(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-match-access@example.com")
    admin_headers = _ops_headers(client, "ops-match-access@example.com")
    owner_headers = auth_headers(register_and_login(client, "match-owner@example.com"))
    intruder_headers = auth_headers(register_and_login(client, "match-intruder@example.com"))
    source_id = _source_id(session, "MyComicShop")

    sale = _create_sale(
        client,
        admin_headers,
        market_source_id=source_id,
        source_listing_id="match-access-1",
        raw_title="Invincible",
        raw_issue="1",
        raw_publisher="Image",
        raw_variant="Cover A",
    )

    monkeypatch.setattr("app.services.inventory.get_inventory_fmv_history", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("FMV lookup should not run")), raising=False)
    monkeypatch.setattr(
        "app.services.canonical_issue_link_suggestions.generate_canonical_issue_suggestions_for_ops",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("canonical mutation should not run")),
        raising=False,
    )

    assert client.get(f"/market-sales/{sale['id']}/match-suggestions", headers=owner_headers).status_code == 200
    assert client.get("/market-match-suggestions", headers=owner_headers).status_code == 200
    assert client.get("/ops/market-match-suggestions", headers=intruder_headers).status_code == 403
    assert client.post(f"/ops/market-sales/{sale['id']}/generate-match-suggestions", headers=intruder_headers).status_code == 403
    assert client.patch("/ops/market-match-suggestions/1/approve", headers=intruder_headers).status_code == 403

    generated = client.post(f"/ops/market-sales/{sale['id']}/generate-match-suggestions", headers=admin_headers)
    assert generated.status_code == 200, generated.text
