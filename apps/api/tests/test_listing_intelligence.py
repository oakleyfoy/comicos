from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import Listing, ListingImage, ListingInventoryLink
from app.services import listing_intelligence as listing_intelligence_service
from test_inventory import auth_headers, create_order, register_and_login


def _inventory_copy_id(client: TestClient, token: str) -> int:
    response = client.get("/inventory", headers=auth_headers(token))
    assert response.status_code == 200
    return int(response.json()["items"][0]["inventory_copy_id"])


def _create_listing(
    client: TestClient,
    session: Session,
    token: str,
    *,
    title: str,
    description: str | None,
    source_type: str,
    replay_key: str,
    ready: bool = True,
    image: bool = False,
) -> int:
    create_order(client, token)
    inventory_copy_id = _inventory_copy_id(client, token)
    rsp = client.post(
        "/listings",
        json={
            "inventory_copy_id": inventory_copy_id,
            "source_type": source_type,
            "title": title,
            "description": description,
            "condition_summary": "Near Mint",
            "asking_price_amount": "19.99",
            "asking_price_currency": "USD",
            "replay_key": replay_key,
        },
        headers=auth_headers(token),
    )
    assert rsp.status_code in (200, 201)
    listing_id = int(rsp.json()["id"])
    if ready:
        patch = client.patch(f"/listings/{listing_id}", json={"status": "READY"}, headers=auth_headers(token))
        assert patch.status_code == 200
    listing = session.get(Listing, listing_id)
    assert listing is not None
    existing_link = session.exec(
        select(ListingInventoryLink).where(ListingInventoryLink.listing_id == listing_id)
    ).first()
    if existing_link is None:
        session.add(ListingInventoryLink(listing_id=listing_id, inventory_copy_id=inventory_copy_id, quantity_allocated=1))
    if image:
        existing_image = session.exec(
            select(ListingImage).where(ListingImage.listing_id == listing_id, ListingImage.display_order == 0)
        ).first()
        if existing_image is None:
            session.add(ListingImage(listing_id=listing_id, display_order=0, role="primary"))
    session.commit()
    return listing_id


def test_listing_intelligence_scoring_helpers() -> None:
    assert listing_intelligence_service._score_title("Amazing Spider-Man #1")[0] == Decimal("20.00")
    assert listing_intelligence_service._score_title("Short")[0] == Decimal("10.00")
    assert listing_intelligence_service._score_description("x" * 40)[0] == Decimal("20.00")
    assert listing_intelligence_service._score_description("brief note")[0] == Decimal("10.00")
    assert listing_intelligence_service._classify_status(
        evidence_count=1,
        completeness_score=Decimal("90.00"),
    ) == "STRONG"
    assert listing_intelligence_service._classify_status(
        evidence_count=1,
        completeness_score=Decimal("70.00"),
    ) == "ADEQUATE"
    assert listing_intelligence_service._classify_status(
        evidence_count=0,
        completeness_score=Decimal("0.00"),
    ) == "INSUFFICIENT_DATA"
    assert listing_intelligence_service._export_ready(
        title_ok=True,
        condition_ok=True,
        price_ok=True,
        currency_ok=True,
        inventory_ok=True,
        status="READY",
    )


def test_listing_intelligence_generate_and_scope(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "intel-ops@example.com")
    from app.core.config import get_settings

    get_settings.cache_clear()

    owner_token = register_and_login(client, "intel-owner@example.com")
    other_token = register_and_login(client, "intel-other@example.com")
    ops_token = register_and_login(client, "intel-ops@example.com")

    strong_listing_id = _create_listing(
        client,
        session,
        owner_token,
        title="Amazing Spider-Man #1",
        description="A full, deterministic listing description with enough detail to score strongly.",
        source_type="manual",
        replay_key="intel-owner-strong",
        ready=True,
        image=True,
    )
    weak_listing_id = _create_listing(
        client,
        session,
        owner_token,
        title="Short",
        description=None,
        source_type="manual",
        replay_key="intel-owner-weak",
        ready=True,
        image=False,
    )
    other_listing_id = _create_listing(
        client,
        session,
        other_token,
        title="Other book",
        description=None,
        source_type="ebay_export",
        replay_key="intel-other-weak",
        ready=True,
        image=False,
    )

    strong_listing = session.get(Listing, strong_listing_id)
    weak_listing = session.get(Listing, weak_listing_id)
    other_listing = session.get(Listing, other_listing_id)
    assert strong_listing is not None and weak_listing is not None and other_listing is not None
    before_status = {
        strong_listing_id: strong_listing.status,
        weak_listing_id: weak_listing.status,
        other_listing_id: other_listing.status,
    }

    generate = client.post(
        "/listing-intelligence/generate",
        json={"snapshot_date": date(2026, 5, 25).isoformat(), "replay_key": "intel-gen-owner"},
        headers=auth_headers(owner_token),
    )
    assert generate.status_code == 201
    assert generate.json()["generated_snapshot_count"] == 2
    checksum = generate.json()["checksum"]

    repeat = client.post(
        "/listing-intelligence/generate",
        json={"snapshot_date": date(2026, 5, 25).isoformat(), "replay_key": "intel-gen-owner"},
        headers=auth_headers(owner_token),
    )
    assert repeat.status_code == 201
    assert repeat.json()["checksum"] == checksum

    owner_snapshots = client.get(
        "/listing-intelligence",
        params={"snapshot_date_from": "2026-05-25", "snapshot_date_to": "2026-05-25"},
        headers=auth_headers(owner_token),
    )
    assert owner_snapshots.status_code == 200
    owner_items = owner_snapshots.json()["items"]
    assert [row["listing_id"] for row in owner_items] == [weak_listing_id, strong_listing_id]

    strong_snapshot = next(row for row in owner_items if row["listing_id"] == strong_listing_id)
    assert strong_snapshot["intelligence_status"] == "STRONG"
    assert strong_snapshot["missing_required_fields_json"] == []
    assert strong_snapshot["stale_risk_flag"] is False

    evidence = client.get(
        "/listing-intelligence/evidence",
        params={"listing_id": strong_listing_id, "snapshot_date_from": "2026-05-25", "snapshot_date_to": "2026-05-25"},
        headers=auth_headers(owner_token),
    )
    assert evidence.status_code == 200
    assert evidence.json()["total_items"] > 0

    checks = client.get(
        "/listing-completeness-checks",
        params={"listing_id": strong_listing_id, "status": "PASS", "snapshot_date_from": "2026-05-25", "snapshot_date_to": "2026-05-25"},
        headers=auth_headers(owner_token),
    )
    assert checks.status_code == 200
    assert checks.json()["total_items"] >= 1

    channel_perf = client.get(
        "/listing-channel-performance",
        params={"snapshot_date_from": "2026-05-25", "snapshot_date_to": "2026-05-25"},
        headers=auth_headers(owner_token),
    )
    assert channel_perf.status_code == 200
    assert channel_perf.json()["items"][0]["channel"] == "private_sale"

    dashboard = client.get("/listing-intelligence/dashboard-summary", headers=auth_headers(owner_token))
    assert dashboard.status_code == 200
    assert dashboard.json()["strong_listing_count"] == 1
    assert dashboard.json()["export_ready_count"] == 2
    assert dashboard.json()["recent_weak_or_incomplete"]

    ops_snapshots = client.get(
        "/ops/listing-intelligence",
        params={"owner_user_id": int(session.get(Listing, strong_listing_id).owner_user_id)},
        headers=auth_headers(ops_token),
    )
    assert ops_snapshots.status_code == 200
    assert all(row["owner_user_id"] == int(strong_listing.owner_user_id) for row in ops_snapshots.json()["items"])

    ops_summary = client.get("/ops/listing-intelligence/dashboard-summary", headers=auth_headers(ops_token))
    assert ops_summary.status_code == 200
    assert ops_summary.json()["strong_listing_count"] >= 1

    session.refresh(strong_listing)
    session.refresh(weak_listing)
    session.refresh(other_listing)
    assert strong_listing.status == before_status[strong_listing_id]
    assert weak_listing.status == before_status[weak_listing_id]
    assert other_listing.status == before_status[other_listing_id]

