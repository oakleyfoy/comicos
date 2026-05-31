from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import InventoryCopy, User
from app.models.sell_candidate import SellCandidateRecommendation
from app.services.sell_candidate_engine import generate_sell_candidates
from app.services.sell_candidates import generate_sell_candidate_recommendations
from test_inventory import auth_headers, create_order, register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def _set_fmv(session: Session, *, owner_id: int, fmv: str) -> list[InventoryCopy]:
    copies = list(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).all())
    for copy in copies:
        copy.current_fmv = Decimal(fmv)
        session.add(copy)
    session.commit()
    return copies


def test_duplicate_copies_trigger_sell(client: TestClient, session: Session) -> None:
    email = "sc-dup@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(
        client,
        token,
        items=[
            {
                "title": "Amazing Spider-Man",
                "publisher": "Marvel",
                "issue_number": "300",
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
    results = generate_sell_candidates(session, owner_user_id=owner_id)
    assert len(results) == 5
    sell_recs = [r for r in results if r.recommendation in {"SELL", "STRONG_SELL"}]
    assert len(sell_recs) >= 3
    assert any("Owns 5 copies" in r.rationale or "Excess duplicate" in r.rationale for r in sell_recs)


def test_single_copy_no_gain_holds(client: TestClient, session: Session) -> None:
    email = "sc-hold@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token)
    _set_fmv(session, owner_id=owner_id, fmv="4.00")
    results = generate_sell_candidates(session, owner_user_id=owner_id)
    assert len(results) == 1
    assert results[0].recommendation == "HOLD"
    assert results[0].confidence_score > 0


def test_idempotent_generate(client: TestClient, session: Session) -> None:
    email = "sc-idem@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token, items=[{"title": "Saga", "publisher": "Image", "issue_number": "1", "cover_name": "Cover A", "printing": None, "ratio": None, "variant_type": None, "cover_artist": None, "quantity": 2, "raw_item_price": 5.00}])
    _set_fmv(session, owner_id=owner_id, fmv="12.00")
    first = generate_sell_candidate_recommendations(session, owner_user_id=owner_id)
    assert first == 2
    second = generate_sell_candidate_recommendations(session, owner_user_id=owner_id)
    assert second == 0


def test_deterministic_outputs(client: TestClient, session: Session) -> None:
    email = "sc-det@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token)
    _set_fmv(session, owner_id=owner_id, fmv="15.00")
    r1 = generate_sell_candidates(session, owner_user_id=owner_id)
    r2 = generate_sell_candidates(session, owner_user_id=owner_id)
    assert [(x.inventory_item_id, x.recommendation, x.estimated_profit) for x in r1] == [
        (x.inventory_item_id, x.recommendation, x.estimated_profit) for x in r2
    ]


def test_api_owner_isolation(client: TestClient, session: Session) -> None:
    token_a = register_and_login(client, "sc-a@example.com")
    token_b = register_and_login(client, "sc-b@example.com")
    owner_a = _owner_id(session, "sc-a@example.com")
    create_order(client, token_a)
    _set_fmv(session, owner_id=owner_a, fmv="20.00")
    client.post("/api/v1/sell-candidates/generate", headers=auth_headers(token_a))
    list_a = client.get("/api/v1/sell-candidates", headers=auth_headers(token_a))
    list_b = client.get("/api/v1/sell-candidates", headers=auth_headers(token_b))
    assert len(list_a.json()["data"]["items"]) == 1
    assert len(list_b.json()["data"]["items"]) == 0


def test_profit_triggers_sell_recommendation(client: TestClient, session: Session) -> None:
    email = "sc-profit@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token, items=[{"title": "X-Men", "publisher": "Marvel", "issue_number": "1", "cover_name": "Cover A", "printing": None, "ratio": None, "variant_type": None, "cover_artist": None, "quantity": 1, "raw_item_price": 5.00}])
    copy = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).one()
    copy.current_fmv = Decimal("20.00")
    copy.grade_status = "cgc_9.8"
    session.add(copy)
    session.commit()
    results = generate_sell_candidates(session, owner_user_id=owner_id)
    assert results[0].recommendation in {"SELL", "STRONG_SELL"}
    assert results[0].estimated_profit > 0
