from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import InventoryCopy, User
from app.models.hold_sell_intelligence import HoldSellRecommendation
from app.services.hold_sell_engine import generate_hold_sell_recommendations
from app.services.hold_sell_intelligence import persist_hold_sell_recommendations
from test_inventory import auth_headers, create_order, register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def _set_fmv(session: Session, *, owner_id: int, fmv: str) -> None:
    copies = list(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).all())
    for copy in copies:
        copy.current_fmv = Decimal(fmv)
        session.add(copy)
    session.commit()


def test_duplicate_profitable_copy_sell(client: TestClient, session: Session) -> None:
    email = "hs-dup@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(
        client,
        token,
        items=[
            {
                "title": "Battle Beast",
                "publisher": "Image",
                "issue_number": "1",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 5,
                "raw_item_price": 10.00,
            }
        ],
    )
    _set_fmv(session, owner_id=owner_id, fmv="40.00")
    results = generate_hold_sell_recommendations(session, owner_user_id=owner_id)
    sell_rows = [r for r in results if r.recommendation == "SELL"]
    assert len(sell_rows) >= 3
    assert all(r.conviction_score >= 70.0 for r in sell_rows)
    assert any("Duplicate" in r.rationale for r in sell_rows)


def test_overexposed_title_sell(client: TestClient, session: Session) -> None:
    email = "hs-over@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(
        client,
        token,
        items=[
            {
                "title": "Filler",
                "publisher": "Image",
                "issue_number": "1",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 2.00,
            },
            {
                "title": "Heavyweight",
                "publisher": "Marvel",
                "issue_number": "1",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 10.00,
            },
        ],
    )
    copies = list(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).all())
    for copy in copies:
        if "Heavyweight" in (copy.metadata_identity_key or ""):
            copy.current_fmv = Decimal("80.00")
        else:
            copy.current_fmv = Decimal("3.00")
        session.add(copy)
    session.commit()
    results = generate_hold_sell_recommendations(session, owner_user_id=owner_id)
    heavy = next(r for r in results if r.title == "Heavyweight")
    assert heavy.recommendation == "SELL"
    assert "overexposed" in heavy.rationale.lower() or heavy.conviction_score >= 70.0


def test_moderate_opportunity_watch(client: TestClient, session: Session) -> None:
    email = "hs-watch@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(
        client,
        token,
        items=[
            {
                "title": "Anchor",
                "publisher": "Marvel",
                "issue_number": "1",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 10,
                "raw_item_price": 5.00,
            },
            {
                "title": "Saga",
                "publisher": "Image",
                "issue_number": "1",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 2,
                "raw_item_price": 10.00,
            },
        ],
    )
    copies = list(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).all())
    for copy in copies:
        if "Saga" in (copy.metadata_identity_key or ""):
            copy.current_fmv = Decimal("14.00")
        else:
            copy.current_fmv = Decimal("15.00")
        session.add(copy)
    session.commit()
    results = generate_hold_sell_recommendations(session, owner_user_id=owner_id)
    assert any(r.recommendation == "WATCH" for r in results)
    watch = next(r for r in results if r.recommendation == "WATCH")
    assert 40.0 <= watch.conviction_score <= 69.0


def test_low_gain_strategic_hold(client: TestClient, session: Session) -> None:
    email = "hs-hold@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token)
    _set_fmv(session, owner_id=owner_id, fmv="4.00")
    results = generate_hold_sell_recommendations(session, owner_user_id=owner_id)
    assert len(results) == 1
    assert results[0].recommendation == "HOLD"
    assert results[0].conviction_score <= 39.0
    assert results[0].rationale


def test_conviction_and_confidence_scoring(client: TestClient, session: Session) -> None:
    email = "hs-scores@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token)
    _set_fmv(session, owner_id=owner_id, fmv="25.00")
    row = generate_hold_sell_recommendations(session, owner_user_id=owner_id)[0]
    assert 0.0 <= row.confidence_score <= 1.0
    assert 0.0 <= row.conviction_score <= 100.0


def test_idempotency(client: TestClient, session: Session) -> None:
    email = "hs-idem@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token)
    _set_fmv(session, owner_id=owner_id, fmv="20.00")
    first = persist_hold_sell_recommendations(session, owner_user_id=owner_id)
    assert first >= 1
    second = persist_hold_sell_recommendations(session, owner_user_id=owner_id)
    assert second == 0


def test_deterministic_outputs(client: TestClient, session: Session) -> None:
    email = "hs-det@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token)
    _set_fmv(session, owner_id=owner_id, fmv="18.00")
    r1 = generate_hold_sell_recommendations(session, owner_user_id=owner_id)
    r2 = generate_hold_sell_recommendations(session, owner_user_id=owner_id)
    assert [(x.inventory_item_id, x.recommendation, x.conviction_score) for x in r1] == [
        (x.inventory_item_id, x.recommendation, x.conviction_score) for x in r2
    ]


def test_api_owner_isolation(client: TestClient, session: Session) -> None:
    token_a = register_and_login(client, "hs-a@example.com")
    token_b = register_and_login(client, "hs-b@example.com")
    owner_a = _owner_id(session, "hs-a@example.com")
    create_order(client, token_a)
    _set_fmv(session, owner_id=owner_a, fmv="22.00")
    client.get("/api/v1/hold-sell/latest", headers=auth_headers(token_a))
    list_a = client.get("/api/v1/hold-sell", headers=auth_headers(token_a))
    list_b = client.get("/api/v1/hold-sell", headers=auth_headers(token_b))
    assert len(list_a.json()["data"]["items"]) >= 1
    assert len(list_b.json()["data"]["items"]) == 0


def test_battle_beast_manual_scenario(client: TestClient, session: Session) -> None:
    email = "hs-battle@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(
        client,
        token,
        items=[
            {
                "title": "Battle Beast",
                "publisher": "Image",
                "issue_number": "1",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 5,
                "raw_item_price": 10.00,
            }
        ],
    )
    _set_fmv(session, owner_id=owner_id, fmv="25.00")
    persist_hold_sell_recommendations(session, owner_user_id=owner_id)
    rows = session.exec(select(HoldSellRecommendation).where(HoldSellRecommendation.owner_user_id == owner_id)).all()
    assert len(rows) == 5
    sell = [r for r in rows if r.recommendation == "SELL"]
    assert len(sell) >= 3
    assert all(r.conviction_score >= 70.0 for r in sell)
