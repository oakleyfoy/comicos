from __future__ import annotations

from datetime import date
from functools import partial

from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlmodel import Session, select

from app.models import Listing, ListingImage, ListingInventoryLink, User
from app.services import dealer_dashboard as dealer_dashboard_service

from test_inventory import auth_headers, create_order, register_and_login


def _inventory_copy_id(client: TestClient, token: str) -> int:
    response = client.get("/inventory", headers=auth_headers(token))
    assert response.status_code == 200
    return int(response.json()["items"][0]["inventory_copy_id"])


def _create_ready_listing(
    client: TestClient,
    session: Session,
    token: str,
    *,
    title: str,
    replay_key: str,
    with_primary_image: bool,
) -> int:
    create_order(client, token)
    inventory_copy_id = _inventory_copy_id(client, token)
    rsp = client.post(
        "/listings",
        json={
            "inventory_copy_id": inventory_copy_id,
            "source_type": "manual",
            "title": title,
            "description": "Deterministic dealer dashboard listing description meets length minimums.",
            "condition_summary": "Near Mint",
            "asking_price_amount": "29.99",
            "asking_price_currency": "USD",
            "replay_key": replay_key,
        },
        headers=auth_headers(token),
    )
    assert rsp.status_code in (200, 201)
    listing_id = int(rsp.json()["id"])
    client.patch(f"/listings/{listing_id}", json={"status": "READY"}, headers=auth_headers(token))
    client.patch(f"/listings/{listing_id}", json={"status": "ACTIVE"}, headers=auth_headers(token))

    listing = session.get(Listing, listing_id)
    assert listing is not None
    link = session.exec(select(ListingInventoryLink).where(ListingInventoryLink.listing_id == listing_id)).first()
    if link is None:
        session.add(
            ListingInventoryLink(listing_id=listing_id, inventory_copy_id=inventory_copy_id, quantity_allocated=1),
        )
    if with_primary_image:
        has_img = session.exec(select(ListingImage).where(ListingImage.listing_id == listing_id)).first()
        if has_img is None:
            session.add(ListingImage(listing_id=listing_id, display_order=0, role="primary"))
    session.commit()

    rng = {"snapshot_date": "2026-05-01", "replay_key": f"intel-{replay_key}"}
    irsp = client.post("/listing-intelligence/generate", json=rng, headers=auth_headers(token))
    assert irsp.status_code in (200, 201), irsp.text
    return listing_id


def test_dealer_dashboard_checksum_payload_stable(client: TestClient, session: Session) -> None:
    pl = dealer_dashboard_service._compute_payload(session, owner_user_id=404, snapshot_date=date(2026, 1, 15))
    pl2 = dealer_dashboard_service._compute_payload(session, owner_user_id=404, snapshot_date=date(2026, 1, 15))
    assert dealer_dashboard_service._hash_payload(pl) == dealer_dashboard_service._hash_payload(pl2)


def test_generate_replay_returns_same_snapshot(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "dealer-owner-replay@example.com")
    _create_ready_listing(
        client,
        session,
        token,
        title="Captain Dealer #100",
        replay_key="replay-listing-primary",
        with_primary_image=True,
    )

    payload = partial(
        client.post,
        "/dealer-dashboard/generate",
        json={"snapshot_date": "2026-05-01", "replay_key": "replay-dash-aa"},
        headers=auth_headers(token),
    )

    rsp1 = payload()
    assert rsp1.status_code in (200, 201)
    chk1 = rsp1.json()["snapshot"]["checksum"]
    id1 = rsp1.json()["snapshot"]["id"]

    rsp2 = payload()
    assert rsp2.status_code in (200, 201)
    assert rsp2.json()["snapshot"]["id"] == id1
    assert rsp2.json()["snapshot"]["checksum"] == chk1


def test_dealer_dashboard_feed_ordering_and_no_listing_mutation(
    client: TestClient,
    session: Session,
) -> None:
    token_a = register_and_login(client, "dealer-owner-a@example.com")
    _create_ready_listing(
        client,
        session,
        token_a,
        title="Book One Dealer",
        replay_key="ddb-listing-one",
        with_primary_image=True,
    )

    before = session.exec(select(func.count(Listing.id))).one()

    gen = client.post(
        "/dealer-dashboard/generate",
        json={"snapshot_date": "2026-05-01", "replay_key": "fresh-dash-unique"},
        headers=auth_headers(token_a),
    )
    assert gen.status_code == 201, gen.text

    after_lc = session.exec(select(func.count(Listing.id))).one()
    assert int(after_lc or 0) == int(before or 0)

    feed = client.get("/dealer-dashboard/feed?limit=50", headers=auth_headers(token_a))
    assert feed.status_code == 200
    items = feed.json()["items"]
    keys = [(row["created_at"], row["id"]) for row in items]
    assert keys == sorted(keys, reverse=True)


def test_owner_ops_dashboard_scoping(monkeypatch, client: TestClient, session: Session) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "dealer-ops@example.com")
    from app.core.config import get_settings

    get_settings.cache_clear()

    owner_token = register_and_login(client, "dealer-owner-scope@example.com")
    ops_token = register_and_login(client, "dealer-ops@example.com")
    outsider_token = register_and_login(client, "dealer-outsider-scope@example.com")

    uid = session.exec(select(User).where(User.email == "dealer-owner-scope@example.com")).first()
    assert uid is not None
    oid = int(uid.id)

    _create_ready_listing(
        client,
        session,
        owner_token,
        title="Scope Case #1",
        replay_key="scope-listing-dash",
        with_primary_image=False,
    )
    rsp = client.post(
        "/dealer-dashboard/generate",
        json={"snapshot_date": "2026-05-01", "replay_key": "scope-dash-gen"},
        headers=auth_headers(owner_token),
    )
    assert rsp.status_code == 201, rsp.text

    owner_alerts = client.get("/dealer-dashboard/alerts", headers=auth_headers(owner_token))
    outsider_alerts = client.get("/dealer-dashboard/alerts", headers=auth_headers(outsider_token))
    assert owner_alerts.json()["total_items"] >= 1
    assert outsider_alerts.json()["total_items"] == 0

    scoped = client.get(f"/ops/dealer-dashboard/alerts?owner_user_id={oid}", headers=auth_headers(ops_token))
    assert scoped.status_code == 200
    assert scoped.json()["total_items"] >= 1

    unscoped = client.get("/ops/dealer-dashboard/alerts", headers=auth_headers(ops_token))
    assert unscoped.status_code == 200
    assert unscoped.json()["total_items"] >= scoped.json()["total_items"]
