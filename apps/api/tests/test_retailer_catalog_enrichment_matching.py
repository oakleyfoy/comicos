"""Catalog enrichment must match retailer titles that carry cover/variant noise.

Regression for the global "every imported book needs catalog review" bug: the
catalog search query was built from the full retailer title (e.g.
"Absolute Green Arrow #1 Cover A Regular Rafael Albuquerque Cover (DC All In)(Limit 1 Per Customer)"),
so the longest title tokens became noise like "albuquerque"/"customer" and the
SQL prefilter returned zero candidates for every line.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlmodel import select

from app.models import (
    InventoryCopy,
    OrderItem,
    RetailerAccount,
    RetailerOrderItemSnapshot,
    RetailerOrderSnapshot,
    User,
)
from app.models.asset_ledger import ComicIssue, ComicTitle, Variant
from app.models.external_catalog import ExternalCatalogIssue
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.services.import_catalog_resolution_service import derive_catalog_search_title
from test_inventory import auth_headers, register_and_login

NOISY_TITLES = [
    ("Absolute Green Arrow #1 Cover A Regular Rafael Albuquerque Cover (DC All In)(Limit 1 Per Customer)", "Absolute Green Arrow", "1"),
    ("Absolute Catwoman #1 Cover C Jorge Fornes Variant (DC All In)(Limit 1 Per Customer)", "Absolute Catwoman", "1"),
    ("Barbara Gordon Breakout #2 Cover A Regular Bengal Cover", "Barbara Gordon Breakout", "2"),
]


def test_derive_catalog_search_title_strips_issue_and_variant_noise() -> None:
    assert (
        derive_catalog_search_title(NOISY_TITLES[0][0]) == "Absolute Green Arrow"
    )
    assert derive_catalog_search_title("Saga Compendium One (Mature Readers)") == "Saga Compendium One"
    assert derive_catalog_search_title("Plain Title") == "Plain Title"


def _create_account(client, session, token: str, email: str) -> RetailerAccount:
    created = client.post(
        "/api/v1/retailer-accounts",
        headers=auth_headers(token),
        json={
            "retailer": "midtown",
            "username": email,
            "password": "supersafe",
            "display_name": "Midtown Comics",
            "sync_enabled": True,
        },
    )
    assert created.status_code == 201, created.text
    account_id = created.json()["id"]
    return session.exec(select(RetailerAccount).where(RetailerAccount.id == account_id)).one()


def _seed_release_catalog(session, *, owner_user_id: int) -> dict[str, int]:
    """Seed the owner's release calendar so the titles have trivial catalog matches."""
    catalog_ids: dict[str, int] = {}
    for noisy_title, series_name, issue_number in NOISY_TITLES:
        series = ReleaseSeries(
            owner_user_id=owner_user_id,
            publisher="DC",
            series_name=series_name,
            series_type="ONGOING",
            status="ACTIVE",
        )
        session.add(series)
        session.flush()
        issue = ReleaseIssue(
            owner_user_id=owner_user_id,
            series_id=int(series.id),
            issue_number=issue_number,
            title=series_name,
            release_date=date(2026, 5, 6),
            foc_date=date(2026, 4, 13),
            release_status="released",
        )
        session.add(issue)
        session.flush()
        catalog_ids[series_name] = int(issue.id)
    session.commit()
    return catalog_ids


def _seed_order(session, *, account: RetailerAccount, order_id: int) -> RetailerOrderSnapshot:
    order = RetailerOrderSnapshot(
        id=order_id,
        owner_user_id=account.owner_user_id,
        retailer_account_id=int(account.id),
        retailer=account.retailer,
        retailer_order_number=str(order_id),
        order_date=date(2026, 5, 8),
        order_status="Shipped",
        order_total=Decimal("17.97"),
        source_url=f"https://www.midtowncomics.com/account/orders/view/{order_id}",
        raw_snapshot_json={"comicos_review_status": "captured"},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(order)
    session.flush()
    for index, (noisy_title, _series, issue_number) in enumerate(NOISY_TITLES, start=1):
        session.add(
            RetailerOrderItemSnapshot(
                owner_user_id=account.owner_user_id,
                retailer_order_snapshot_id=int(order.id),
                retailer=account.retailer,
                retailer_order_number=str(order_id),
                retailer_item_id=f"{order_id}-{index:03d}",
                product_url=None,
                image_url=f"https://www.midtowncomics.com/cover-{index}.jpg",
                thumbnail_url=f"https://www.midtowncomics.com/cover-{index}-thumb.jpg",
                title=noisy_title,
                publisher="DC",
                issue_number=issue_number,
                cover_name="Cover A",
                variant_type="Regular",
                cover_artist=None,
                quantity=1,
                unit_price=Decimal("5.99"),
                total_price=Decimal("5.99"),
                item_status="Shipped",
                release_date=None,
                raw_item_json={"line": index},
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )
    session.commit()
    session.refresh(order)
    return order


def test_confirm_matches_noisy_midtown_titles_to_catalog(client, session) -> None:
    token = register_and_login(client, "midtown-enrich-match@example.com")
    user = session.exec(select(User).where(User.email == "midtown-enrich-match@example.com")).one()
    account = _create_account(client, session, token, "midtown-enrich-match@example.com")
    catalog_ids = _seed_release_catalog(session, owner_user_id=int(user.id))
    _seed_order(session, account=account, order_id=9100000001)

    confirmed = client.post("/api/v1/retailer-orders/9100000001/confirm", headers=auth_headers(token))
    assert confirmed.status_code == 200, confirmed.text
    linked_order_id = confirmed.json()["linked_order_id"]
    assert linked_order_id is not None

    # Enrichment runs inline in tests (autouse scheduler) but in its own session.
    session.expire_all()

    order_items = session.exec(
        select(OrderItem).where(OrderItem.order_id == linked_order_id).order_by(OrderItem.id.asc())
    ).all()
    assert len(order_items) == len(NOISY_TITLES)

    matched_ids = {int(catalog_ids[series]) for _t, series, _i in NOISY_TITLES}
    clean_series_names = {series for _t, series, _i in NOISY_TITLES}
    for order_item in order_items:
        assert order_item.enrichment_status == "matched", order_item.enrichment_notes
        assert order_item.catalog_match_id in matched_ids
        assert order_item.foc_date == date(2026, 4, 13)

        # The stored book title should be the cleaned series name, not the noisy
        # retailer string with cover/variant/promo text.
        comic_title = session.exec(
            select(ComicTitle)
            .join(ComicIssue, ComicIssue.comic_title_id == ComicTitle.id)
            .join(Variant, Variant.comic_issue_id == ComicIssue.id)
            .where(Variant.id == order_item.variant_id)
        ).one()
        assert comic_title.name in clean_series_names
        assert "#" not in comic_title.name
        assert "(" not in comic_title.name
        assert "Cover" not in comic_title.name
        copies = session.exec(
            select(InventoryCopy).where(InventoryCopy.order_item_id == order_item.id)
        ).all()
        assert copies
        for copy in copies:
            assert copy.release_date == date(2026, 5, 6)
            assert copy.release_year == 2026
            assert copy.release_status == "released"
            assert copy.source_image_url  # cover present (catalog or retailer)


def test_reenrich_endpoint_returns_match_diagnostics(client, session) -> None:
    token = register_and_login(client, "midtown-reenrich@example.com")
    user = session.exec(select(User).where(User.email == "midtown-reenrich@example.com")).one()
    account = _create_account(client, session, token, "midtown-reenrich@example.com")
    _seed_release_catalog(session, owner_user_id=int(user.id))
    _seed_order(session, account=account, order_id=9100000002)

    confirmed = client.post("/api/v1/retailer-orders/9100000002/confirm", headers=auth_headers(token))
    assert confirmed.status_code == 200, confirmed.text

    re_enriched = client.post("/api/v1/retailer-orders/9100000002/re-enrich", headers=auth_headers(token))
    assert re_enriched.status_code == 200, re_enriched.text
    body = re_enriched.json()

    assert body["enrichment_summary"]["matched_items"] == len(NOISY_TITLES)
    assert body["enrichment_summary"]["needs_review_items"] == 0
    assert len(body["lines"]) == len(NOISY_TITLES)
    for line in body["lines"]:
        assert line["matched"] is True
        assert line["series_search_title"]
        assert "#" not in line["series_search_title"]
        assert line["catalog_match_id"] is not None
        assert line["match_score"] >= 70
        assert line["candidate_count"] >= 1
        assert line["rejection_reason"] is None


def test_confirm_completes_dates_and_cover_from_external_catalog(client, session, monkeypatch) -> None:
    # Force the local (DB-only) external-catalog fallback path; no live LOCG calls.
    monkeypatch.setenv("IMPORT_LOCG_HYDRATE", "0")
    token = register_and_login(client, "midtown-external-complete@example.com")
    user = session.exec(select(User).where(User.email == "midtown-external-complete@example.com")).one()
    account = _create_account(client, session, token, "midtown-external-complete@example.com")

    # A bare ReleaseIssue (matches on title+issue) with no dates...
    series = ReleaseSeries(
        owner_user_id=int(user.id),
        publisher="DC",
        series_name="Absolute Green Arrow",
        series_type="ONGOING",
        status="ACTIVE",
    )
    session.add(series)
    session.flush()
    session.add(
        ReleaseIssue(
            owner_user_id=int(user.id),
            series_id=int(series.id),
            issue_number="1",
            title="Absolute Green Arrow",
            release_date=None,
            foc_date=None,
            release_status="unknown",
        )
    )
    # ...and an external/LOCG catalog row for the same book WITH date, FOC, and cover.
    session.add(
        ExternalCatalogIssue(
            source_name="locg",
            title="Absolute Green Arrow #1",
            publisher="DC",
            series_name="Absolute Green Arrow",
            issue_number="1",
            release_date=date(2026, 5, 6),
            foc_date=date(2026, 4, 13),
            cover_image_url="https://catalog.example.com/green-arrow-1.jpg",
        )
    )
    session.commit()

    order = RetailerOrderSnapshot(
        id=9100000010,
        owner_user_id=account.owner_user_id,
        retailer_account_id=int(account.id),
        retailer=account.retailer,
        retailer_order_number="9100000010",
        order_date=date(2026, 5, 8),
        order_status="Shipped",
        order_total=Decimal("5.99"),
        raw_snapshot_json={"comicos_review_status": "captured"},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(order)
    session.flush()
    session.add(
        RetailerOrderItemSnapshot(
            owner_user_id=account.owner_user_id,
            retailer_order_snapshot_id=int(order.id),
            retailer=account.retailer,
            retailer_order_number="9100000010",
            retailer_item_id="9100000010-001",
            product_url=None,
            # Broken local saved-HTML image (would otherwise render as a placeholder).
            image_url="./Order_files/local-broken.jpg",
            thumbnail_url="./Order_files/local-broken-thumb.jpg",
            title="Absolute Green Arrow #1 Cover A Regular Rafael Albuquerque Cover (DC All In)(Limit 1 Per Customer)",
            publisher="DC",
            issue_number="1",
            cover_name="Cover A",
            variant_type="Regular",
            quantity=1,
            unit_price=Decimal("5.99"),
            total_price=Decimal("5.99"),
            item_status="Shipped",
            release_date=None,
            raw_item_json={"line": 1},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )
    session.commit()
    session.refresh(order)

    confirmed = client.post("/api/v1/retailer-orders/9100000010/confirm", headers=auth_headers(token))
    assert confirmed.status_code == 200, confirmed.text
    linked_order_id = confirmed.json()["linked_order_id"]
    session.expire_all()

    order_item = session.exec(select(OrderItem).where(OrderItem.order_id == linked_order_id)).one()
    assert order_item.enrichment_status == "matched", order_item.enrichment_notes
    assert order_item.foc_date == date(2026, 4, 13)

    copy = session.exec(select(InventoryCopy).where(InventoryCopy.order_item_id == order_item.id)).one()
    assert copy.release_date == date(2026, 5, 6)
    assert copy.release_year == 2026
    assert copy.source_image_url == "https://catalog.example.com/green-arrow-1.jpg"


def test_reenrich_requires_confirmed_order(client, session) -> None:
    token = register_and_login(client, "midtown-reenrich-guard@example.com")
    account = _create_account(client, session, token, "midtown-reenrich-guard@example.com")
    _seed_order(session, account=account, order_id=9100000003)

    response = client.post("/api/v1/retailer-orders/9100000003/re-enrich", headers=auth_headers(token))
    assert response.status_code == 409, response.text
