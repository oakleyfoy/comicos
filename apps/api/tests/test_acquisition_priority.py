"""P38-06 acquisition-priority engine deterministic behavior."""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import InventoryCopy, InventoryLiquiditySnapshot, User
from app.models.acquisition_priority import AcquisitionPriorityHistory
from app.services.acquisition_priority import (
    _IssueAggregate,
    _classify_category,
    _classify_confidence,
    _classify_priority,
    _classify_risk,
    _classify_strength,
)
from test_inventory import auth_headers, create_order, register_and_login


def _ck(label: str = "p38-06-test") -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _seed_liquidity_snapshot(
    session: Session,
    *,
    owner_user_id: int,
    inventory_item_id: int,
    issue_id: int,
    liquidity_status: str,
    sell_through_rate_pct: Decimal,
    stale_listing_rate_pct: Decimal,
    snapshot_date: date,
) -> None:
    session.add(
        InventoryLiquiditySnapshot(
            owner_user_id=owner_user_id,
            inventory_item_id=inventory_item_id,
            canonical_comic_issue_id=issue_id,
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


def test_acquisition_priority_replay_stable_checksum_no_fmv_mutation(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "acq-replay@example.com")
    owner_id = int(session.exec(select(User.id).where(User.email == "acq-replay@example.com")).one())

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
                "title": "Saga",
                "publisher": "Image",
                "issue_number": "1",
                "cover_name": "Cover B",
                "printing": None,
                "ratio": None,
                "variant_type": "Virgin",
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 12.0,
            },
        ],
    )

    inv_rsp = client.get("/inventory", headers=auth_headers(token))
    inventory_rows = inv_rsp.json()["items"]
    inventory_ids = [int(row["inventory_copy_id"]) for row in inventory_rows]
    for idx, inventory_item_id in enumerate(inventory_ids, start=1):
        inv = session.get(InventoryCopy, inventory_item_id)
        assert inv is not None
        inv.current_fmv = Decimal("100.00") + Decimal(str(idx * 20))
        session.add(inv)
    session.commit()

    for inventory_item_id in inventory_ids:
        # The acquisition engine only needs a deterministic latest liquidity row per copy.
        _seed_liquidity_snapshot(
            session,
            owner_user_id=owner_id,
            inventory_item_id=inventory_item_id,
            issue_id=inventory_item_id,
            liquidity_status="HIGH",
            sell_through_rate_pct=Decimal("45.00"),
            stale_listing_rate_pct=Decimal("8.00"),
            snapshot_date=date(2026, 5, 26),
        )

    before_fmv = [session.get(InventoryCopy, iid).current_fmv for iid in inventory_ids]
    body = {"replay_key": "acq-rk-1", "snapshot_date": str(date(2026, 5, 26))}
    r1 = client.post("/acquisition-priorities/generate", headers=auth_headers(token), json=body)
    assert r1.status_code == 201, r1.text
    r2 = client.post("/acquisition-priorities/generate", headers=auth_headers(token), json=body)
    assert r2.status_code == 200, r2.text
    js1 = r1.json()
    js2 = r2.json()
    assert js1["total"] > 0
    assert js1["total"] == js2["total"]
    assert [row["checksum"] for row in js1["items"]] == [row["checksum"] for row in js2["items"]]
    after_fmv = [session.get(InventoryCopy, iid).current_fmv for iid in inventory_ids]
    assert after_fmv == before_fmv


def test_acquisition_priority_detail_history_and_inventory_teaser(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "acq-detail@example.com")
    owner_id = int(session.exec(select(User.id).where(User.email == "acq-detail@example.com")).one())
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
    inv_row.current_fmv = Decimal("140.00")
    session.add(inv_row)
    session.commit()
    _seed_liquidity_snapshot(
        session,
        owner_user_id=owner_id,
        inventory_item_id=inventory_item_id,
        issue_id=inventory_item_id,
        liquidity_status="HIGH",
        sell_through_rate_pct=Decimal("55.00"),
        stale_listing_rate_pct=Decimal("5.00"),
        snapshot_date=date(2026, 5, 27),
    )

    gen = client.post(
        "/acquisition-priorities/generate",
        headers=auth_headers(token),
        json={"replay_key": "acq-detail", "snapshot_date": str(date(2026, 5, 27))},
    )
    assert gen.status_code == 201, gen.text
    snapshot_id = int(gen.json()["items"][0]["id"])
    detail = client.get(f"/acquisition-priorities/{snapshot_id}", headers=auth_headers(token))
    assert detail.status_code == 200, detail.text
    detail_body = detail.json()
    assert sorted(item["scenario_name"] for item in detail_body["scenarios"]) == [
        "baseline",
        "optimistic",
        "pessimistic",
    ]
    assert len(detail_body["evidence"]) >= 5
    assert len(detail_body["history"]) == 1

    inv_detail = client.get(f"/inventory/{inventory_item_id}", headers=auth_headers(token))
    assert inv_detail.status_code == 200, inv_detail.text
    assert inv_detail.json()["acquisition_priority"] is not None


def test_acquisition_priority_append_history_and_scoping(client: TestClient, session: Session) -> None:
    token_a = register_and_login(client, "acq-scope-a@example.com")
    token_b = register_and_login(client, "acq-scope-b@example.com")
    owner_a = int(session.exec(select(User.id).where(User.email == "acq-scope-a@example.com")).one())

    create_order(
        client,
        token_a,
        items=[
            {
                "title": "Invincible",
                "publisher": "Image",
                "issue_number": "1",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": "Regular",
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 20.0,
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
        issue_id=inventory_item_id,
        liquidity_status="LOW",
        sell_through_rate_pct=Decimal("15.00"),
        stale_listing_rate_pct=Decimal("75.00"),
        snapshot_date=date(2026, 5, 28),
    )

    first = client.post(
        "/acquisition-priorities/generate",
        headers=auth_headers(token_a),
        json={"replay_key": "acq-hist", "snapshot_date": str(date(2026, 5, 28))},
    )
    assert first.status_code == 201, first.text
    snapshot_id = int(first.json()["items"][0]["id"])
    history_before = session.exec(
        select(AcquisitionPriorityHistory).where(AcquisitionPriorityHistory.owner_user_id == owner_a)
    ).all()

    inv_row.current_fmv = Decimal("180.00")
    session.add(inv_row)
    session.commit()
    second = client.post(
        "/acquisition-priorities/generate",
        headers=auth_headers(token_a),
        json={"replay_key": "acq-hist", "snapshot_date": str(date(2026, 5, 28))},
    )
    assert second.status_code == 201, second.text
    history_after = session.exec(
        select(AcquisitionPriorityHistory).where(AcquisitionPriorityHistory.owner_user_id == owner_a)
    ).all()
    assert len(history_after) > len(history_before)

    peer_detail = client.get(f"/acquisition-priorities/{snapshot_id}", headers=auth_headers(token_b))
    assert peer_detail.status_code == 404
    assert client.get("/ops/acquisition-priorities", headers=auth_headers(token_a)).status_code == 200
    assert client.get("/ops/acquisition-priority-evidence", headers=auth_headers(token_a)).status_code == 200
    assert client.get("/ops/acquisition-priority-history", headers=auth_headers(token_a)).status_code == 200


def test_acquisition_priority_classification_helpers() -> None:
    assert _classify_priority(Decimal("80")) == "ELITE"
    assert _classify_priority(Decimal("60")) == "HIGH"
    assert _classify_priority(Decimal("35")) == "MEDIUM"
    assert _classify_priority(Decimal("34.99")) == "LOW"

    assert _classify_strength(Decimal("85")) == "ELITE"
    assert _classify_strength(Decimal("65")) == "STRONG"
    assert _classify_strength(Decimal("40")) == "MODERATE"
    assert _classify_strength(Decimal("39.99")) == "WEAK"

    assert _classify_confidence(Decimal("75")) == "HIGH"
    assert _classify_confidence(Decimal("50")) == "MEDIUM"
    assert _classify_confidence(Decimal("49.99")) == "LOW"

    assert _classify_risk(5) == "HIGH"
    assert _classify_risk(3) == "MEDIUM"
    assert _classify_risk(2) == "LOW"

    issue = _IssueAggregate(
        canonical_comic_issue_id=10,
        publisher_key="image",
        title_key="spawn-1",
        era_key="2020_plus",
        acquisition_source_key="manual-whatnot",
        acquisition_source_label="manual:whatnot",
        inventory_item_ids=[1],
        item_count=1,
        total_value=Decimal("125.00"),
        duplicate_overlap_count=0,
        graded_count=0,
        sell_through_rate_avg=Decimal("55.00"),
        stale_listing_rate_avg=Decimal("10.00"),
        active_listing_count=1,
        realized_sales_total=Decimal("60.00"),
        best_liquidity_status="HIGH",
        best_grading_action="GRADE",
        best_grading_strength="STRONG",
        best_grading_risk="LOW",
        best_grading_expected_roi=Decimal("80.00"),
        best_grading_liquidity_adjusted_roi=Decimal("70.00"),
        recommendation_actions=[],
        market_activity_count=1,
    )
    assert (
        _classify_category(
            issue=issue,
            diversification_impact=Decimal("82.00"),
            liquidity_impact=Decimal("78.00"),
            grading_upside_score=Decimal("90.00"),
            concentration_reduction_score=Decimal("68.00"),
            sales_velocity_score=Decimal("70.00"),
            duplication_risk=Decimal("10.00"),
        )
        == "GRADING_OPPORTUNITY"
    )
