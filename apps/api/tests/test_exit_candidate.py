from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import InventoryCopy, User
from app.models.exit_candidate import ExitCandidate
from app.services.exit_candidate_engine import generate_exit_candidates
from app.services.exit_candidates import persist_exit_candidates
from test_inventory import auth_headers, create_order, register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def _set_fmv(session: Session, *, owner_id: int, fmv: str) -> None:
    copies = list(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).all())
    for copy in copies:
        copy.current_fmv = Decimal(fmv)
        session.add(copy)
    session.commit()


def test_duplicate_inventory_generates_candidate(client: TestClient, session: Session) -> None:
    email = "ec-dup@example.com"
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
    _set_fmv(session, owner_id=owner_id, fmv="10.50")
    results = generate_exit_candidates(session, owner_user_id=owner_id)
    assert len(results) >= 3
    assert all(r.candidate_score > 0 for r in results)
    assert any(r.candidate_reason in {"DUPLICATE", "MULTIPLE_SIGNALS"} for r in results)
    persist_exit_candidates(session, owner_user_id=owner_id)
    rows = session.exec(select(ExitCandidate).where(ExitCandidate.owner_user_id == owner_id)).all()
    assert len(rows) >= 3


def test_profitable_inventory_generates_candidate(client: TestClient, session: Session) -> None:
    email = "ec-profit@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(
        client,
        token,
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
                "raw_item_price": 5.00,
            }
        ],
    )
    copy = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).one()
    copy.current_fmv = Decimal("20.00")
    copy.grade_status = "cgc_9.8"
    session.add(copy)
    session.commit()
    results = generate_exit_candidates(session, owner_user_id=owner_id)
    assert len(results) == 1
    assert results[0].candidate_reason in {"PROFITABLE", "GRADED", "MULTIPLE_SIGNALS", "OVEREXPOSED"}
    assert results[0].unrealized_gain > 0
    assert results[0].confidence_score > 0


def test_overexposed_inventory_generates_candidate(client: TestClient, session: Session) -> None:
    email = "ec-over@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token)
    _set_fmv(session, owner_id=owner_id, fmv="25.00")
    results = generate_exit_candidates(session, owner_user_id=owner_id)
    assert len(results) == 1
    assert results[0].candidate_reason in {"OVEREXPOSED", "CAPITAL_RECOVERY", "MULTIPLE_SIGNALS", "PROFITABLE"}
    assert results[0].candidate_score >= 20.0


def test_unrealized_gain_calculated(client: TestClient, session: Session) -> None:
    email = "ec-gain@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token, items=[{"title": "Saga", "publisher": "Image", "issue_number": "1", "cover_name": "Cover A", "printing": None, "ratio": None, "variant_type": None, "cover_artist": None, "quantity": 1, "raw_item_price": 8.00}])
    _set_fmv(session, owner_id=owner_id, fmv="18.00")
    row = generate_exit_candidates(session, owner_user_id=owner_id)[0]
    assert row.unrealized_gain == 10.0
    assert row.estimated_fmv == 18.0
    assert row.acquisition_cost == 8.0


def test_idempotency(client: TestClient, session: Session) -> None:
    email = "ec-idem@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(
        client,
        token,
        items=[{"title": "Battle Beast", "publisher": "Image", "issue_number": "1", "cover_name": "Cover A", "printing": None, "ratio": None, "variant_type": None, "cover_artist": None, "quantity": 3, "raw_item_price": 10.00}],
    )
    _set_fmv(session, owner_id=owner_id, fmv="10.50")
    first = persist_exit_candidates(session, owner_user_id=owner_id)
    assert first >= 1
    second = persist_exit_candidates(session, owner_user_id=owner_id)
    assert second == 0


def test_deterministic_outputs(client: TestClient, session: Session) -> None:
    email = "ec-det@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token)
    _set_fmv(session, owner_id=owner_id, fmv="15.00")
    r1 = generate_exit_candidates(session, owner_user_id=owner_id)
    r2 = generate_exit_candidates(session, owner_user_id=owner_id)
    assert [(x.inventory_item_id, x.candidate_score, x.candidate_reason) for x in r1] == [
        (x.inventory_item_id, x.candidate_score, x.candidate_reason) for x in r2
    ]


def test_api_owner_isolation(client: TestClient, session: Session) -> None:
    token_a = register_and_login(client, "ec-a@example.com")
    token_b = register_and_login(client, "ec-b@example.com")
    owner_a = _owner_id(session, "ec-a@example.com")
    create_order(client, token_a)
    _set_fmv(session, owner_id=owner_a, fmv="30.00")
    client.get("/api/v1/exit-candidates/latest", headers=auth_headers(token_a))
    list_a = client.get("/api/v1/exit-candidates", headers=auth_headers(token_a))
    list_b = client.get("/api/v1/exit-candidates", headers=auth_headers(token_b))
    assert len(list_a.json()["data"]["items"]) >= 1
    assert len(list_b.json()["data"]["items"]) == 0
