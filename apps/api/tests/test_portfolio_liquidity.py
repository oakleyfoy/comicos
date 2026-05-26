"""P38-03 portfolio liquidity allocation engine — deterministic behavior."""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import InventoryCopy, InventoryLiquiditySnapshot, User
from app.models.portfolio_liquidity import PortfolioLiquidityHistory

from test_inventory import auth_headers, create_order, register_and_login


def _ck() -> str:
    return hashlib.sha256(b"p38-03-test").hexdigest()


def test_portfolio_liquidity_replay_stable_checksum_no_fmv_mutation(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "pluq-replay@example.com")

    uid_row = session.exec(select(User.id).where(User.email == "pluq-replay@example.com")).first()
    assert uid_row is not None
    owner_id = int(uid_row)

    create_order(
        client,
        token,
        items=[
            {
                "title": "Spawn",
                "publisher": "Image",
                "issue_number": "9",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 6.25,
            },
        ],
    )
    inv_rsp = client.get("/inventory", headers=auth_headers(token))
    assert inv_rsp.status_code == 200
    pk = int(inv_rsp.json()["items"][0]["inventory_copy_id"])
    inv_before = session.get(InventoryCopy, pk)
    assert inv_before is not None

    liq_row = InventoryLiquiditySnapshot(
        owner_user_id=owner_id,
        inventory_item_id=pk,
        canonical_comic_issue_id=None,
        channel=None,
        liquidity_status="HIGH",
        days_on_market_median=None,
        days_to_sale_median=None,
        sell_through_rate_pct=Decimal("40.00"),
        stale_listing_rate_pct=Decimal("10.00"),
        relist_rate_pct=Decimal("0"),
        successful_sale_count=0,
        failed_listing_count=0,
        active_listing_count=0,
        liquidity_confidence="CONFIDENT",
        evaluation_window_days=365,
        snapshot_date=date(2026, 5, 26),
        checksum=_ck(),
        evidence_count=0,
    )
    session.add(liq_row)
    session.commit()

    body = {"replay_key": "pluq-rk-1", "snapshot_date": str(date(2026, 5, 26))}

    r1 = client.post("/portfolio-liquidity/generate", headers=auth_headers(token), json=body)
    assert r1.status_code == 201, r1.text
    r2 = client.post("/portfolio-liquidity/generate", headers=auth_headers(token), json=body)
    assert r2.status_code == 200, r2.text
    assert r1.json()["snapshot"]["checksum"] == r2.json()["snapshot"]["checksum"]

    inv_after = session.get(InventoryCopy, pk)
    assert inv_after is not None
    assert inv_after.current_fmv == inv_before.current_fmv

    bk = sorted(r2.json()["buckets"], key=lambda b: b["liquidity_bucket"])
    assert [b["liquidity_bucket"] for b in bk] == ["HIGH", "ILLIQUID", "LOW", "MEDIUM"]


def test_portfolio_liquidity_append_history_and_bucket_rules(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "pluq-hist@example.com")
    uid_row = session.exec(select(User.id).where(User.email == "pluq-hist@example.com")).first()
    assert uid_row is not None
    owner_id = int(uid_row)

    create_order(
        client,
        token,
        items=[
            {
                "title": "Spawn",
                "publisher": "Image",
                "issue_number": "10",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 11.00,
            },
        ],
    )
    inv_rsp = client.get("/inventory", headers=auth_headers(token))
    pk = int(inv_rsp.json()["items"][0]["inventory_copy_id"])
    inv_row = session.get(InventoryCopy, pk)
    assert inv_row is not None
    inv_row.current_fmv = Decimal("100.00")
    session.add(inv_row)
    session.commit()

    liq_row = InventoryLiquiditySnapshot(
        owner_user_id=owner_id,
        inventory_item_id=pk,
        canonical_comic_issue_id=None,
        channel=None,
        liquidity_status="ILLIQUID",
        days_on_market_median=None,
        days_to_sale_median=None,
        sell_through_rate_pct=Decimal("5.00"),
        stale_listing_rate_pct=Decimal("80.00"),
        relist_rate_pct=Decimal("0"),
        successful_sale_count=0,
        failed_listing_count=0,
        active_listing_count=0,
        liquidity_confidence="CONFIDENT",
        evaluation_window_days=365,
        snapshot_date=date(2026, 5, 26),
        checksum=_ck(),
        evidence_count=0,
    )
    session.add(liq_row)
    session.commit()

    rk = "pluq-append"
    rsp = client.post(
        "/portfolio-liquidity/generate",
        headers=auth_headers(token),
        json={"replay_key": rk, "snapshot_date": str(date(2026, 5, 27))},
    )
    assert rsp.status_code == 201, rsp.text
    js = rsp.json()
    assert js["replayed"] is False
    assert js["snapshot"]["liquidity_balance_status"] in {"CRITICAL", "IMBALANCED", "WATCH", "HEALTHY", "INSUFFICIENT_DATA"}
    assert js["snapshot"]["illiquid_count"] >= 1
    buckets = js["buckets"]
    ill_b = next(b for b in buckets if b["liquidity_bucket"] == "ILLIQUID")
    assert int(ill_b["item_count"]) >= 1

    hid = js["snapshot"]["id"]
    ev = client.get("/portfolio-liquidity-evidence", headers=auth_headers(token))
    assert ev.status_code == 200
    assert any(row["portfolio_liquidity_snapshot_id"] == hid for row in ev.json()["items"])

    hist_before = session.exec(select(PortfolioLiquidityHistory).where(PortfolioLiquidityHistory.owner_user_id == owner_id)).all()

    rsp2 = client.post(
        "/portfolio-liquidity/generate",
        headers=auth_headers(token),
        json={"replay_key": rk, "snapshot_date": str(date(2026, 5, 27))},
    )
    assert rsp2.status_code == 200
    hist_after = session.exec(select(PortfolioLiquidityHistory).where(PortfolioLiquidityHistory.owner_user_id == owner_id)).all()
    assert len(hist_after) == len(hist_before)


def test_ops_portfolio_liquidity_list(client: TestClient) -> None:
    token = register_and_login(client, "pluq-ops@example.com")
    h = auth_headers(token)

    rsp = client.get("/portfolio-liquidity-history", headers=h)
    assert rsp.status_code == 200
    snaps = client.get("/ops/portfolio-liquidity", headers=h)
    assert snaps.status_code == 200, snaps.text
    evid = client.get("/ops/portfolio-liquidity-evidence", headers=h)
    assert evid.status_code == 200, evid.text
    hist_ops = client.get("/ops/portfolio-liquidity-history", headers=h)
    assert hist_ops.status_code == 200, hist_ops.text


def test_portfolio_liquidity_owner_cannot_read_peer_snapshot(client: TestClient, session: Session) -> None:
    token_a = register_and_login(client, "pluq-scope-a@example.com")
    token_b = register_and_login(client, "pluq-scope-b@example.com")

    create_order(
        client,
        token_a,
        items=[
            {
                "title": "X-Men",
                "publisher": "Marvel",
                "issue_number": "1",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 4.0,
            },
        ],
    )
    uid_row = session.exec(select(User.id).where(User.email == "pluq-scope-a@example.com")).first()
    assert uid_row is not None
    owner_a = int(uid_row)

    inv_rsp = client.get("/inventory", headers=auth_headers(token_a))
    pk = int(inv_rsp.json()["items"][0]["inventory_copy_id"])
    session.add(
        InventoryLiquiditySnapshot(
            owner_user_id=owner_a,
            inventory_item_id=pk,
            canonical_comic_issue_id=None,
            channel=None,
            liquidity_status="HIGH",
            days_on_market_median=None,
            days_to_sale_median=None,
            sell_through_rate_pct=Decimal("30.00"),
            stale_listing_rate_pct=Decimal("5.00"),
            relist_rate_pct=Decimal("0"),
            successful_sale_count=0,
            failed_listing_count=0,
            active_listing_count=0,
            liquidity_confidence="CONFIDENT",
            evaluation_window_days=365,
            snapshot_date=date(2026, 5, 28),
            checksum=_ck(),
            evidence_count=0,
        )
    )
    session.commit()

    gen = client.post(
        "/portfolio-liquidity/generate",
        headers=auth_headers(token_a),
        json={"replay_key": "scope-rk", "snapshot_date": str(date(2026, 5, 28))},
    )
    assert gen.status_code == 201, gen.text
    snap_id = int(gen.json()["snapshot"]["id"])

    peer = client.get(f"/portfolio-liquidity/{snap_id}", headers=auth_headers(token_b))
    assert peer.status_code == 404
