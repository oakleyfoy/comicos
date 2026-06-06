from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlmodel import Session, select

from app.models import InventoryCopy, User
from app.models.market_pricing_engine import P68MarketPriceSnapshot
from app.services.authoritative_fmv_service import get_authoritative_fmv
from app.services.inventory_fmv import build_inventory_fmv_attachment
from app.services.market_refresh_service import authoritative_fmv_consistent_for_copy
from app.services.p67_inventory_bridge import enrich_row_value, fmv_lookup_by_title, load_p67_inventory_context, p68_computed_fmv_for_copy
from test_inventory import create_order, register_and_login
from fastapi.testclient import TestClient


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_authoritative_fmv_and_bridge_agree(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "fmv-adopt@example.com")
    owner_id = _owner_id(session, "fmv-adopt@example.com")
    create_order(client, token)
    copy = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).one()
    copy.current_fmv = Decimal("9.99")
    session.add(copy)
    session.add(
        P68MarketPriceSnapshot(
            owner_user_id=owner_id,
            generated_at=datetime.now(timezone.utc),
            inventory_copy_id=int(copy.id or 0),
            title="Series",
            publisher="Marvel",
            issue_number="1",
            blended_fmv=42.5,
            sales_count=4,
            liquidity_score=55.0,
            confidence=0.72,
            primary_provider="EBAY_SOLD",
            metadata_json={"provider_breakdown": {"EBAY_SOLD": 4}, "last_comp_date": "2026-06-01"},
        )
    )
    session.commit()
    cid = int(copy.id or 0)
    auth = get_authoritative_fmv(session, owner_user_id=owner_id, inventory_copy_id=cid)
    assert auth is not None
    assert auth.authoritative_fmv == 42.5
    assert auth.provider_breakdown.get("EBAY_SOLD") == 4

    rows = load_p67_inventory_context(session, owner_user_id=owner_id)
    row = next(r for r in rows if r.copy_id == cid)
    p68 = p68_computed_fmv_for_copy(session, owner_user_id=owner_id, copy_id=cid)
    bridge = enrich_row_value(row, fmv_lookup_by_title(session, owner_user_id=owner_id), p68_computed=p68)
    assert bridge == 42.5
    assert authoritative_fmv_consistent_for_copy(session, owner_user_id=owner_id, inventory_copy_id=cid)

    attachment = build_inventory_fmv_attachment(
        session,
        row={
            "inventory_copy_id": cid,
            "metadata_identity_key": copy.metadata_identity_key,
            "canonical_issue_id": None,
            "title": "Series",
            "publisher": "Marvel",
            "issue_number": "1",
            "grade_status": "raw",
            "order_status": "received",
            "release_status": "released",
            "acquisition_cost": Decimal("10"),
            "ownership_state": "in_hand",
        },
        include_detail=False,
    )
    assert attachment.current_market_fmv == Decimal("42.50")
    assert attachment.valuation_evidence_json.get("p68_authoritative_fmv") == 42.5
