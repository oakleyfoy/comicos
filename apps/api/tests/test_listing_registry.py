from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlmodel import Session
from test_inventory import auth_headers, create_order, register_and_login

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.db.session import get_engine
from app.models import CoverImage, ListingImage, ListingPriceHistory, MetadataAudit


def _audit_row_count() -> int:
    with Session(get_engine()) as session:
        cnt = session.scalar(select(func.count(MetadataAudit.id)))
        return int(cnt or 0)


def _price_history_count(listing_id: int) -> int:
    with Session(get_engine()) as session:
        cnt = session.scalar(
            select(func.count(ListingPriceHistory.id)).where(
                ListingPriceHistory.listing_id == listing_id
            )
        )
        return int(cnt or 0)


def test_listing_lifecycle_scoped_and_append_only_history(client: TestClient) -> None:
    token = register_and_login(client, "listing-owner@example.com")
    create_order(client, token)
    inv = client.get("/inventory", headers=auth_headers(token)).json()["items"][0]
    copy_id = int(inv["inventory_copy_id"])

    create_payload = {
        "inventory_copy_id": copy_id,
        "source_type": "manual",
        "title": "Shop copy",
        "asking_price_amount": "10.00",
        "asking_price_currency": "USD",
        "replay_key": "rk-create-1",
    }

    first = client.post("/listings", json=create_payload, headers=auth_headers(token))
    assert first.status_code == 201
    dup = client.post("/listings", json=create_payload, headers=auth_headers(token))
    assert dup.status_code == 200
    assert dup.json()["id"] == first.json()["id"]

    listing_id = int(first.json()["id"])
    assert _price_history_count(listing_id) >= 1

    ready = client.patch(
        f"/listings/{listing_id}",
        json={"status": "READY", "replay_key": "rk-ready-1"},
        headers=auth_headers(token),
    )
    assert ready.status_code == 200

    active = client.post(
        f"/listings/{listing_id}/activate",
        json={"replay_key": "rk-activate-1"},
        headers=auth_headers(token),
    )
    assert active.status_code == 200
    assert active.json()["status"] == "ACTIVE"

    disallow_patch_activate = client.patch(
        f"/listings/{listing_id}",
        json={"status": "ACTIVE"},
        headers=auth_headers(token),
    )
    assert disallow_patch_activate.status_code == 400

    price = client.patch(
        f"/listings/{listing_id}",
        json={
            "asking_price_amount": "12.00",
            "asking_price_currency": "USD",
            "replay_key": "rk-price-1",
        },
        headers=auth_headers(token),
    )
    assert price.status_code == 200
    assert _price_history_count(listing_id) >= 2

    sold = client.patch(
        f"/listings/{listing_id}",
        json={"status": "SOLD", "replay_key": "rk-sold-1"},
        headers=auth_headers(token),
    )
    assert sold.status_code == 200

    cancel = client.post(f"/listings/{listing_id}/cancel", headers=auth_headers(token))
    assert cancel.status_code == 409

    other = register_and_login(client, "other-listing@example.com")
    assert client.get(f"/listings/{listing_id}", headers=auth_headers(other)).status_code == 404


def test_illegal_status_skips_allowed_chain(client: TestClient) -> None:
    token = register_and_login(client, "illegal-listing@example.com")
    create_order(client, token)
    inv = client.get("/inventory", headers=auth_headers(token)).json()["items"][0]
    copy_id = int(inv["inventory_copy_id"])
    rsp = client.post(
        "/listings",
        json={
            "inventory_copy_id": copy_id,
            "source_type": "manual",
            "title": "Bad path",
            "replay_key": "rk-illegal-1",
        },
        headers=auth_headers(token),
    )
    lid = int(rsp.json()["id"])
    hdr = auth_headers(token)
    assert client.patch(f"/listings/{lid}", json={"status": "SOLD"}, headers=hdr).status_code == 409


def test_listing_reads_do_not_mutate_metadata_audit(client: TestClient) -> None:
    token = register_and_login(client, "audit-listing@example.com")
    create_order(client, token)
    inv = client.get("/inventory", headers=auth_headers(token)).json()["items"][0]
    copy_id = int(inv["inventory_copy_id"])
    payload = {"inventory_copy_id": copy_id, "source_type": "whatnot", "title": "Audit listing"}
    created = client.post("/listings", json=payload, headers=auth_headers(token))
    listing_id = int(created.json()["id"])

    before = _audit_row_count()
    assert client.get("/listings/summary", headers=auth_headers(token)).status_code == 200
    assert client.get(f"/listings/{listing_id}", headers=auth_headers(token)).status_code == 200
    assert _audit_row_count() == before


def test_ops_listing_endpoints_require_admin(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPS_ADMIN_EMAILS", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    token = register_and_login(client, "not-ops-listing@example.com")
    assert client.get("/ops/listings", headers=auth_headers(token)).status_code == 403

    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-listing-admin@example.com")
    get_settings.cache_clear()
    admin = register_and_login(client, "ops-listing-admin@example.com")
    assert client.get("/ops/listings", headers=auth_headers(admin)).status_code == 200


def test_ops_listings_filter_and_duplicate_lifecycle_suppressed(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-listing-scope@example.com")
    get_settings.cache_clear()

    owner_email = "listing-scope-owner@example.com"
    owner_tok = register_and_login(client, owner_email)
    create_order(client, owner_tok)
    inv = client.get("/inventory", headers=auth_headers(owner_tok)).json()["items"][0]
    copy_id = int(inv["inventory_copy_id"])

    rsp = client.post(
        "/listings",
        json={
            "inventory_copy_id": copy_id,
            "source_type": "manual",
            "title": "A",
            "replay_key": "rk-scope-a",
        },
        headers=auth_headers(owner_tok),
    )
    lid = int(rsp.json()["id"])
    client.patch(f"/listings/{lid}", json={"status": "READY"}, headers=auth_headers(owner_tok))
    client.post(f"/listings/{lid}/activate", headers=auth_headers(owner_tok))

    ph_before = _price_history_count(lid)
    rk = "rk-dup-ph"
    body = {
        "asking_price_amount": "33.00",
        "asking_price_currency": "USD",
        "replay_key": rk,
    }
    hdr_o = auth_headers(owner_tok)
    p1 = client.patch(f"/listings/{lid}", json=body, headers=hdr_o)
    assert p1.status_code == 200
    ph_mid = _price_history_count(lid)
    assert ph_mid > ph_before
    p2 = client.patch(f"/listings/{lid}", json=body, headers=hdr_o)
    assert p2.status_code == 200
    assert _price_history_count(lid) == ph_mid

    uid = decode_access_token(owner_tok)["sub"]

    admin = register_and_login(client, "ops-listing-scope@example.com")
    ops = auth_headers(admin)
    filtered = client.get(
        "/ops/listings",
        params={"owner_user_id": uid, "limit": "5"},
        headers=ops,
    ).json()
    assert filtered["total_items"] >= 1
    ours = next((r for r in filtered["items"] if int(r["id"]) == lid), None)
    assert ours is not None

    by_status = client.get(
        "/ops/listings",
        params={"status": "ACTIVE", "limit": "50"},
        headers=ops,
    ).json()
    statuses = {r["status"] for r in by_status["items"]}
    assert statuses <= {"ACTIVE"}


def test_listing_detail_images_sorted_deterministic(client: TestClient) -> None:
    tok = register_and_login(client, "listing-img-sort@example.com")
    create_order(client, tok)
    inv_row = client.get("/inventory", headers=auth_headers(tok)).json()["items"][0]
    copy_id = int(inv_row["inventory_copy_id"])
    rsp = client.post(
        "/listings",
        json={
            "inventory_copy_id": copy_id,
            "source_type": "manual",
            "title": "Img order",
            "replay_key": "rk-img-1",
        },
        headers=auth_headers(tok),
    )
    lid = int(rsp.json()["id"])
    with Session(get_engine()) as session:
        cover_ids = list(
            session.exec(
                select(CoverImage.id)
                .where(CoverImage.inventory_copy_id == copy_id)
                .order_by(CoverImage.id)
            ).all()
        )
        if len(cover_ids) < 2:
            pytest.skip("fixture inventory lacked multiple cover rows")
        session.add(
            ListingImage(
                listing_id=lid,
                cover_image_id=cover_ids[1],
                display_order=50,
                role="gallery",
            )
        )
        session.add(
            ListingImage(
                listing_id=lid,
                cover_image_id=cover_ids[0],
                display_order=10,
                role="primary",
            )
        )
        session.commit()

    detail = client.get(f"/listings/{lid}", headers=auth_headers(tok)).json()
    orders = [img["display_order"] for img in detail["images"]]
    assert orders == [10, 50]


def test_ops_listing_events_and_price_history_list(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-evts@example.com")
    get_settings.cache_clear()

    owner_tok = register_and_login(client, "listing-evts-owner@example.com")
    create_order(client, owner_tok)
    inv = client.get("/inventory", headers=auth_headers(owner_tok)).json()["items"][0]
    copy_id = int(inv["inventory_copy_id"])
    rsp = client.post(
        "/listings",
        json={
            "inventory_copy_id": copy_id,
            "source_type": "manual",
            "title": "Events",
            "asking_price_amount": "1.00",
            "asking_price_currency": "USD",
            "replay_key": "rk-evts-1",
        },
        headers=auth_headers(owner_tok),
    )
    lid = int(rsp.json()["id"])

    ops = auth_headers(register_and_login(client, "ops-evts@example.com"))
    ev = client.get(
        "/ops/listing-events",
        params={"listing_id": str(lid), "limit": "10"},
        headers=ops,
    )
    assert ev.status_code == 200
    body = ev.json()
    assert body["total_items"] >= 1
    ph = client.get(
        "/ops/listing-price-history", params={"listing_id": str(lid), "limit": "10"}, headers=ops
    )
    assert ph.status_code == 200
    assert ph.json()["total_items"] >= 1