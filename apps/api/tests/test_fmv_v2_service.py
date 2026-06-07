"""P90 FMV V2 service tests."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.services.fmv_v2_service import generate_fmv_v2_snapshots, lookup_fmv_v2_display
from test_inventory import auth_headers, create_order, register_and_login


def test_fmv_v2_dry_run_no_persist(client: TestClient, session: Session) -> None:
    from app.models import User
    from sqlmodel import select

    register_and_login(client, "fmv-v2-dry@example.com")
    user = session.exec(select(User).where(User.email == "fmv-v2-dry@example.com")).one()
    with patch("app.services.p89_market_pricing_service.generate_market_price_snapshots") as gen:
        summary = generate_fmv_v2_snapshots(session, owner_user_id=int(user.id), dry_run=True)
    assert summary["snapshots_created"] >= 0
    gen.assert_not_called()


def test_fmv_v2_legacy_fallback(client: TestClient, session: Session) -> None:
    from app.models import User
    from app.models.asset_ledger import InventoryCopy
    from sqlmodel import select

    token = register_and_login(client, "fmv-v2-leg@example.com")
    create_order(client, token)
    user = session.exec(select(User).where(User.email == "fmv-v2-leg@example.com")).one()
    copy = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == int(user.id))).one()
    copy.current_fmv = 40.0
    copy.metadata_identity_key = "pub|Spider-Man|1"
    session.add(copy)
    session.commit()
    display = lookup_fmv_v2_display(session, owner_user_id=int(user.id), series="Spider-Man", issue_number="1")
    assert display is not None
    assert display.market_value == 40.0
    assert display.valuation_source == "LEGACY"


def test_fmv_intelligence_api(client: TestClient) -> None:
    token = register_and_login(client, "fmv-v2-api@example.com")
    resp = client.get("/api/v1/fmv-intelligence", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "portfolio" in data
    assert "highest_value" in data
