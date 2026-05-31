from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import InventoryCopy, User
from app.models.acquisition_opportunity import AcquisitionOpportunity
from app.services.acquisition_opportunity_engine import generate_acquisition_opportunities
from app.services.acquisition_opportunities import persist_acquisition_opportunities
from app.services.collection_gaps import persist_collection_gaps
from test_inventory import auth_headers, create_order, register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def _battle_beast_items(numbers: list[str]) -> list[dict]:
    return [
        {
            "title": "Battle Beast",
            "publisher": "Image",
            "issue_number": num,
            "cover_name": "Cover A",
            "printing": None,
            "ratio": None,
            "variant_type": None,
            "cover_artist": None,
            "quantity": 1,
            "raw_item_price": 5.00,
        }
        for num in numbers
    ]


def _set_series_fmv(session: Session, *, owner_id: int, fmv: str) -> None:
    copies = list(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).all())
    for copy in copies:
        copy.current_fmv = Decimal(fmv)
        session.add(copy)
    session.commit()


def test_critical_gap_high_priority_opportunity(client: TestClient, session: Session) -> None:
    email = "ao-gap@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token, items=_battle_beast_items(["1", "2", "4", "5"]))
    persist_collection_gaps(session, owner_user_id=owner_id)
    created = persist_acquisition_opportunities(session, owner_user_id=owner_id)
    assert created >= 1
    opps = generate_acquisition_opportunities(session, owner_user_id=owner_id)
    gap_opp = next((o for o in opps if o.issue_number == "3"), None)
    assert gap_opp is not None
    assert gap_opp.priority_score >= 90.0
    assert gap_opp.opportunity_type == "RUN_COMPLETION_TARGET"
    assert "80%" in gap_opp.rationale or "complete" in gap_opp.rationale.lower()


def test_want_list_item_opportunity(client: TestClient, session: Session) -> None:
    email = "ao-want@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    list_id = client.get("/api/v1/want-lists", headers=auth_headers(token)).json()["data"]["items"][0]["id"]
    client.post(
        f"/api/v1/want-lists/{list_id}/items",
        headers=auth_headers(token),
        json={
            "publisher": "Image",
            "series_name": "Battle Beast",
            "issue_number": "3",
            "priority": "CRITICAL",
        },
    )
    created = persist_acquisition_opportunities(session, owner_user_id=owner_id)
    assert created >= 1
    opps = generate_acquisition_opportunities(session, owner_user_id=owner_id)
    want_opp = next((o for o in opps if o.source_type == "WANT_LIST" and o.issue_number == "3"), None)
    assert want_opp is not None
    assert want_opp.priority_score >= 90.0
    assert want_opp.opportunity_type == "WANT_LIST_ITEM"
    assert "want-list" in want_opp.rationale.lower()


def test_target_price_at_eighty_percent_fmv(client: TestClient, session: Session) -> None:
    email = "ao-fmv@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token, items=_battle_beast_items(["1", "2", "4", "5"]))
    _set_series_fmv(session, owner_id=owner_id, fmv="25.00")
    persist_collection_gaps(session, owner_user_id=owner_id)
    persist_acquisition_opportunities(session, owner_user_id=owner_id)
    row = session.exec(select(AcquisitionOpportunity).where(AcquisitionOpportunity.owner_user_id == owner_id)).first()
    assert row is not None
    assert row.estimated_fmv == 25.0
    assert row.target_price == 20.0
    assert row.value_gap == 5.0
    assert "80%" in row.rationale


def test_null_fmv_does_not_crash(client: TestClient, session: Session) -> None:
    email = "ao-nofmv@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    list_id = client.get("/api/v1/want-lists", headers=auth_headers(token)).json()["data"]["items"][0]["id"]
    client.post(
        f"/api/v1/want-lists/{list_id}/items",
        headers=auth_headers(token),
        json={"series_name": "Obscure Series", "issue_number": "7", "priority": "LOW"},
    )
    created = persist_acquisition_opportunities(session, owner_user_id=owner_id)
    assert created >= 1
    row = session.exec(select(AcquisitionOpportunity).where(AcquisitionOpportunity.owner_user_id == owner_id)).one()
    assert row.target_price is None
    assert row.value_gap is None


def test_idempotent_persist(client: TestClient, session: Session) -> None:
    email = "ao-idem@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token, items=_battle_beast_items(["1", "2", "4", "5"]))
    persist_collection_gaps(session, owner_user_id=owner_id)
    first = persist_acquisition_opportunities(session, owner_user_id=owner_id)
    assert first >= 1
    second = persist_acquisition_opportunities(session, owner_user_id=owner_id)
    assert second == 0


def test_owner_isolation(client: TestClient, session: Session) -> None:
    token_a = register_and_login(client, "ao-a@example.com")
    token_b = register_and_login(client, "ao-b@example.com")
    create_order(client, token_a, items=_battle_beast_items(["1", "2", "4", "5"]))
    client.get("/api/v1/acquisition-opportunities/latest", headers=auth_headers(token_a))
    b_list = client.get("/api/v1/acquisition-opportunities", headers=auth_headers(token_b))
    assert b_list.status_code == 200
    assert b_list.json()["data"]["items"] == []
