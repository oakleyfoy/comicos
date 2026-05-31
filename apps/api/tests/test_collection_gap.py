from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.models.collection_gap import CollectionGap
from app.services.collection_gap_engine import generate_collection_gaps, run_completion_for_numeric_owned
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


def test_run_completion_complete_and_missing() -> None:
    assert run_completion_for_numeric_owned([1, 2, 3, 4, 5]) == (100.0, [])
    pct, missing = run_completion_for_numeric_owned([1, 2, 4, 5])
    assert pct == 80.0
    assert missing == [3]


def test_complete_run_no_gaps(client: TestClient, session: Session) -> None:
    email = "cg-complete@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token, items=_battle_beast_items(["1", "2", "3", "4", "5"]))
    gaps = generate_collection_gaps(session, owner_user_id=owner_id)
    issue_gaps = [g for g in gaps if g.issue_number == "3"]
    assert issue_gaps == []
    created = persist_collection_gaps(session, owner_user_id=owner_id)
    assert created == 0


def test_missing_issue_gap_created(client: TestClient, session: Session) -> None:
    email = "cg-missing@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token, items=_battle_beast_items(["1", "2", "4", "5"]))
    gaps = generate_collection_gaps(session, owner_user_id=owner_id)
    gap3 = next((g for g in gaps if g.series_name == "Battle Beast" and g.issue_number == "3"), None)
    assert gap3 is not None
    assert gap3.completion_percent == 80.0
    assert gap3.priority in {"HIGH", "CRITICAL"}
    assert "missing issue" in gap3.rationale.lower() or "#3" in gap3.rationale
    created = persist_collection_gaps(session, owner_user_id=owner_id)
    assert created >= 1
    latest = client.get("/api/v1/collection-gaps/latest", headers=auth_headers(token))
    assert latest.status_code == 200
    items = latest.json()["data"]["items"]
    assert any(i["issue_number"] == "3" and i["completion_percent"] == 80.0 for i in items)


def test_idempotent_persist(client: TestClient, session: Session) -> None:
    email = "cg-idem@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token, items=_battle_beast_items(["1", "2", "4", "5"]))
    first = persist_collection_gaps(session, owner_user_id=owner_id)
    assert first >= 1
    second = persist_collection_gaps(session, owner_user_id=owner_id)
    assert second == 0
    rows = session.exec(select(CollectionGap).where(CollectionGap.owner_user_id == owner_id)).all()
    assert len(rows) == first


def test_owner_isolation(client: TestClient, session: Session) -> None:
    token_a = register_and_login(client, "cg-a@example.com")
    token_b = register_and_login(client, "cg-b@example.com")
    create_order(client, token_a, items=_battle_beast_items(["1", "2", "4", "5"]))
    client.get("/api/v1/collection-gaps/latest", headers=auth_headers(token_a))
    b_list = client.get("/api/v1/collection-gaps", headers=auth_headers(token_b))
    assert b_list.status_code == 200
    assert b_list.json()["data"]["items"] == []


def test_api_filters(client: TestClient, session: Session) -> None:
    email = "cg-filter@example.com"
    token = register_and_login(client, email)
    create_order(client, token, items=_battle_beast_items(["1", "2", "4", "5"]))
    client.get("/api/v1/collection-gaps/latest", headers=auth_headers(token))
    filtered = client.get(
        "/api/v1/collection-gaps",
        headers=auth_headers(token),
        params={"priority": "CRITICAL", "publisher": "Image"},
    )
    assert filtered.status_code == 200
    summary = client.get("/api/v1/collection-gaps/summary", headers=auth_headers(token))
    assert summary.status_code == 200
    assert summary.json()["data"]["total_gaps"] >= 1
