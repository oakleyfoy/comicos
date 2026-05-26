"""P38-05 concentration-risk engine deterministic behavior."""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import InventoryCopy, InventoryLiquiditySnapshot, User
from app.models.concentration_risk import ConcentrationRiskHistory
from app.services.concentration_risk import _classify_status
from test_inventory import auth_headers, create_order, register_and_login


def _ck(label: str = "p38-05-test") -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _seed_liquidity_snapshot(
    session: Session,
    *,
    owner_user_id: int,
    inventory_item_id: int,
    liquidity_status: str,
    sell_through_rate_pct: Decimal,
    stale_listing_rate_pct: Decimal,
    snapshot_date: date,
) -> None:
    session.add(
        InventoryLiquiditySnapshot(
            owner_user_id=owner_user_id,
            inventory_item_id=inventory_item_id,
            canonical_comic_issue_id=None,
            channel=None,
            liquidity_status=liquidity_status,
            days_on_market_median=None,
            days_to_sale_median=None,
            sell_through_rate_pct=sell_through_rate_pct,
            stale_listing_rate_pct=stale_listing_rate_pct,
            relist_rate_pct=Decimal("0"),
            successful_sale_count=0,
            failed_listing_count=0,
            active_listing_count=0,
            liquidity_confidence="CONFIDENT",
            evaluation_window_days=365,
            snapshot_date=snapshot_date,
            checksum=_ck(f"{owner_user_id}:{inventory_item_id}:{snapshot_date.isoformat()}"),
            evidence_count=0,
        )
    )
    session.commit()


def test_concentration_risk_replay_stable_checksum_and_no_fmv_mutation(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "concentration-replay@example.com")
    owner_id = int(session.exec(select(User.id).where(User.email == "concentration-replay@example.com")).one())

    create_order(
        client,
        token,
        items=[
            {
                "title": "Spawn",
                "publisher": "Image",
                "issue_number": "18",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": "Main",
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 14.25,
            },
            {
                "title": "Spawn",
                "publisher": "Image",
                "issue_number": "19",
                "cover_name": "Cover B",
                "printing": None,
                "ratio": None,
                "variant_type": "B&W",
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 11.50,
            },
        ],
    )

    inv_rsp = client.get("/inventory", headers=auth_headers(token))
    assert inv_rsp.status_code == 200, inv_rsp.text
    inventory_rows = inv_rsp.json()["items"]
    inventory_ids = [int(row["inventory_copy_id"]) for row in inventory_rows]
    for idx, inventory_item_id in enumerate(inventory_ids, start=1):
        inv = session.get(InventoryCopy, inventory_item_id)
        assert inv is not None
        inv.current_fmv = Decimal("100.00") + Decimal(str(idx))
        session.add(inv)
        _seed_liquidity_snapshot(
            session,
            owner_user_id=owner_id,
            inventory_item_id=inventory_item_id,
            liquidity_status="HIGH" if idx == 1 else "LOW",
            sell_through_rate_pct=Decimal("45.00"),
            stale_listing_rate_pct=Decimal("8.00") if idx == 1 else Decimal("65.00"),
            snapshot_date=date(2026, 5, 26),
        )
    session.commit()
    before_fmv = [session.get(InventoryCopy, iid).current_fmv for iid in inventory_ids]

    body = {"replay_key": "concentration-rk-1", "snapshot_date": str(date(2026, 5, 26))}
    r1 = client.post("/concentration-risk/generate", headers=auth_headers(token), json=body)
    assert r1.status_code == 201, r1.text
    r2 = client.post("/concentration-risk/generate", headers=auth_headers(token), json=body)
    assert r2.status_code == 200, r2.text

    js1 = r1.json()
    js2 = r2.json()
    assert js1["total"] > 0
    assert js1["total"] == js2["total"]
    checksums_1 = [row["checksum"] for row in js1["items"]]
    checksums_2 = [row["checksum"] for row in js2["items"]]
    assert checksums_1 == checksums_2

    after_fmv = [session.get(InventoryCopy, iid).current_fmv for iid in inventory_ids]
    assert after_fmv == before_fmv


def test_concentration_risk_detail_factors_history_and_inventory_teaser(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "concentration-detail@example.com")
    owner_id = int(session.exec(select(User.id).where(User.email == "concentration-detail@example.com")).one())

    create_order(
        client,
        token,
        items=[
            {
                "title": "X-Men",
                "publisher": "Marvel",
                "issue_number": "5",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": "Regular",
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 9.0,
            }
        ],
    )

    inv_rsp = client.get("/inventory", headers=auth_headers(token))
    inventory_item_id = int(inv_rsp.json()["items"][0]["inventory_copy_id"])
    inv_row = session.get(InventoryCopy, inventory_item_id)
    assert inv_row is not None
    inv_row.current_fmv = Decimal("100.00")
    session.add(inv_row)
    session.commit()

    _seed_liquidity_snapshot(
        session,
        owner_user_id=owner_id,
        inventory_item_id=inventory_item_id,
        liquidity_status="ILLIQUID",
        sell_through_rate_pct=Decimal("5.00"),
        stale_listing_rate_pct=Decimal("88.00"),
        snapshot_date=date(2026, 5, 27),
    )

    body = {"replay_key": "conc-detail", "snapshot_date": str(date(2026, 5, 27))}
    gen = client.post("/concentration-risk/generate", headers=auth_headers(token), json=body)
    assert gen.status_code == 201, gen.text
    publisher_row = next(row for row in gen.json()["items"] if row["concentration_type"] == "publisher")
    snapshot_id = int(publisher_row["id"])

    detail = client.get(f"/concentration-risk/{snapshot_id}", headers=auth_headers(token))
    assert detail.status_code == 200, detail.text
    detail_body = detail.json()
    assert detail_body["snapshot"]["exposure_status"] == "CRITICAL"
    factor_keys = [item["factor_key"] for item in detail_body["factors"]]
    assert factor_keys == sorted(factor_keys)
    assert len(detail_body["history"]) == 1

    teaser = client.get(f"/inventory/{inventory_item_id}", headers=auth_headers(token))
    assert teaser.status_code == 200, teaser.text
    assert teaser.json()["concentration_risk"] is not None


def test_concentration_risk_history_append_and_owner_ops_scoping(client: TestClient, session: Session) -> None:
    token_a = register_and_login(client, "concentration-scope-a@example.com")
    token_b = register_and_login(client, "concentration-scope-b@example.com")
    owner_a = int(session.exec(select(User.id).where(User.email == "concentration-scope-a@example.com")).one())

    create_order(
        client,
        token_a,
        items=[
            {
                "title": "Saga",
                "publisher": "Image",
                "issue_number": "1",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": "Regular",
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 7.0,
            }
        ],
    )
    inv_rsp = client.get("/inventory", headers=auth_headers(token_a))
    inventory_item_id = int(inv_rsp.json()["items"][0]["inventory_copy_id"])
    inv_row = session.get(InventoryCopy, inventory_item_id)
    assert inv_row is not None
    inv_row.current_fmv = Decimal("80.00")
    session.add(inv_row)
    session.commit()

    _seed_liquidity_snapshot(
        session,
        owner_user_id=owner_a,
        inventory_item_id=inventory_item_id,
        liquidity_status="LOW",
        sell_through_rate_pct=Decimal("20.00"),
        stale_listing_rate_pct=Decimal("70.00"),
        snapshot_date=date(2026, 5, 28),
    )

    first = client.post(
        "/concentration-risk/generate",
        headers=auth_headers(token_a),
        json={"replay_key": "conc-hist", "snapshot_date": str(date(2026, 5, 28))},
    )
    assert first.status_code == 201, first.text
    snapshot_id = int(first.json()["items"][0]["id"])
    history_before = session.exec(
        select(ConcentrationRiskHistory).where(ConcentrationRiskHistory.owner_user_id == owner_a)
    ).all()

    inv_row.current_fmv = Decimal("160.00")
    session.add(inv_row)
    session.commit()

    second = client.post(
        "/concentration-risk/generate",
        headers=auth_headers(token_a),
        json={"replay_key": "conc-hist", "snapshot_date": str(date(2026, 5, 28))},
    )
    assert second.status_code == 201, second.text
    history_after = session.exec(
        select(ConcentrationRiskHistory).where(ConcentrationRiskHistory.owner_user_id == owner_a)
    ).all()
    assert len(history_after) > len(history_before)

    peer_detail = client.get(f"/concentration-risk/{snapshot_id}", headers=auth_headers(token_b))
    assert peer_detail.status_code == 404

    ops_list = client.get("/ops/concentration-risk", headers=auth_headers(token_a))
    assert ops_list.status_code == 200, ops_list.text
    ops_evidence = client.get("/ops/concentration-risk-evidence", headers=auth_headers(token_a))
    assert ops_evidence.status_code == 200, ops_evidence.text
    ops_factors = client.get("/ops/concentration-risk-factors", headers=auth_headers(token_a))
    assert ops_factors.status_code == 200, ops_factors.text
    ops_history = client.get("/ops/concentration-risk-history", headers=auth_headers(token_a))
    assert ops_history.status_code == 200, ops_history.text


def test_concentration_risk_status_thresholds() -> None:
    assert _classify_status(
        concentration_score=Decimal("19.99"),
        primary_share_pct=Decimal("10"),
        liquidity_weighted_concentration=Decimal("10"),
    ) == "HEALTHY"
    assert _classify_status(
        concentration_score=Decimal("20.00"),
        primary_share_pct=Decimal("10"),
        liquidity_weighted_concentration=Decimal("10"),
    ) == "WATCH"
    assert _classify_status(
        concentration_score=Decimal("35.00"),
        primary_share_pct=Decimal("10"),
        liquidity_weighted_concentration=Decimal("10"),
    ) == "CONCENTRATED"
    assert _classify_status(
        concentration_score=Decimal("50.00"),
        primary_share_pct=Decimal("10"),
        liquidity_weighted_concentration=Decimal("10"),
    ) == "OVEREXPOSED"
    assert _classify_status(
        concentration_score=Decimal("60.00"),
        primary_share_pct=Decimal("55.00"),
        liquidity_weighted_concentration=Decimal("10"),
    ) == "CRITICAL"
