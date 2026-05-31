from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import InventoryCopy, User
from app.services.acquisition_dashboard import get_acquisition_dashboard
from app.services.acquisition_opportunities import persist_acquisition_opportunities
from app.services.collection_gaps import persist_collection_gaps
from app.services.marketplace_acquisitions import ensure_marketplace_acquisition_sources
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


def _seed_battle_beast_stack(client: TestClient, session: Session, email: str) -> str:
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token, items=_battle_beast_items(["1", "2", "4", "5"]))
    copies = list(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).all())
    for copy in copies:
        copy.current_fmv = Decimal("25.00")
        session.add(copy)
    session.commit()
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
    persist_collection_gaps(session, owner_user_id=owner_id)
    persist_acquisition_opportunities(session, owner_user_id=owner_id)
    manual_id = next(s for s in ensure_marketplace_acquisition_sources(session) if s.source_type == "MANUAL").id
    created = client.post(
        "/api/v1/marketplace-acquisitions",
        headers=auth_headers(token),
        json={
            "marketplace_source_id": int(manual_id or 0),
            "title": "Battle Beast #3",
            "publisher": "Image",
            "series_name": "Battle Beast",
            "issue_number": "3",
            "total_price": 10.0,
        },
    )
    cand_id = created.json()["data"]["id"]
    client.post(f"/api/v1/marketplace-acquisitions/{cand_id}/evaluate", headers=auth_headers(token))
    watch = client.post(
        "/api/v1/marketplace-acquisitions",
        headers=auth_headers(token),
        json={
            "marketplace_source_id": int(manual_id or 0),
            "title": "Unknown #99",
            "series_name": "Unknown",
            "issue_number": "99",
        },
    )
    watch_id = watch.json()["data"]["id"]
    client.post(f"/api/v1/marketplace-acquisitions/{watch_id}/evaluate", headers=auth_headers(token))
    return token


def test_dashboard_sections(client: TestClient, session: Session) -> None:
    token = _seed_battle_beast_stack(client, session, "ad-dash@example.com")
    resp = client.get("/api/v1/acquisition-dashboard", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    summary = data["summary"]
    assert summary["critical_want_list_items"] >= 1
    assert summary["open_collection_gaps"] >= 1
    assert summary["high_priority_opportunities"] >= 1
    assert summary["buy_candidates"] >= 1
    assert summary["below_target_candidates"] >= 1
    assert summary["review_required_candidates"] >= 1
    assert any(i["issue_number"] == "3" for i in data["top_want_list_items"])
    assert any(i["issue_number"] == "3" for i in data["top_collection_gaps"])
    assert any(i["issue_number"] == "3" for i in data["top_opportunities"])
    assert any(i["recommendation"] == "BUY" for i in data["marketplace_candidates"])
    assert len(data["below_target_price"]) >= 1
    assert len(data["review_required"]) >= 1


def test_deterministic_ordering(client: TestClient, session: Session) -> None:
    token = _seed_battle_beast_stack(client, session, "ad-order@example.com")
    owner_id = _owner_id(session, "ad-order@example.com")
    a = get_acquisition_dashboard(session, owner_user_id=owner_id)
    b = get_acquisition_dashboard(session, owner_user_id=owner_id)
    assert [i.item_id for i in a.top_opportunities] == [i.item_id for i in b.top_opportunities]
    assert [i.item_id for i in a.marketplace_candidates] == [i.item_id for i in b.marketplace_candidates]


def test_owner_isolation(client: TestClient, session: Session) -> None:
    token_a = _seed_battle_beast_stack(client, session, "ad-a@example.com")
    token_b = register_and_login(client, "ad-b@example.com")
    b = client.get("/api/v1/acquisition-dashboard", headers=auth_headers(token_b))
    assert b.json()["data"]["summary"]["total_want_list_items"] == 0
    a = client.get("/api/v1/acquisition-dashboard/summary", headers=auth_headers(token_a))
    assert a.json()["data"]["buy_candidates"] >= 1
    actions = client.get("/api/v1/acquisition-dashboard/actions", headers=auth_headers(token_a))
    assert len(actions.json()["data"]["urgent_acquisition_actions"]) >= 1


def test_dashboard_api_filters(client: TestClient, session: Session) -> None:
    token = _seed_battle_beast_stack(client, session, "ad-filter@example.com")
    filtered = client.get(
        "/api/v1/acquisition-dashboard",
        headers=auth_headers(token),
        params={"publisher": "Image", "recommendation": "BUY"},
    )
    assert filtered.status_code == 200
    items = filtered.json()["data"]["marketplace_candidates"]
    assert all(i.get("recommendation") == "BUY" for i in items)
