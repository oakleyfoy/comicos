from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import InventoryCopy, User
from app.models.p89_sell_candidate import P89SellCandidate
from app.services.sell_candidate_service import (
    build_p89_sell_candidate_summary,
    evaluate_inventory_copy,
    generate_evaluations,
    recalculate_sell_candidates,
)
from test_inventory import auth_headers, create_order, register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_evaluate_produces_scores_and_recommendation(session: Session, client: TestClient) -> None:
    email = "p89-eval@example.com"
    token = register_and_login(client, email)
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
                "quantity": 1,
                "raw_item_price": 5.0,
            }
        ],
    )
    copy = session.exec(select(InventoryCopy)).one()
    owner_id = int(copy.user_id)
    copy.current_fmv = Decimal("50.00")
    session.add(copy)
    session.commit()

    ev = evaluate_inventory_copy(
        session,
        owner_user_id=owner_id,
        copy=copy,
        group_size=1,
        copy_index=0,
        is_excess=False,
        concentration=0.1,
    )
    assert 0 <= ev.sell_score <= 100
    assert 0 <= ev.hold_score <= 100
    assert 0 <= ev.grade_first_score <= 100
    assert ev.recommendation in {"SELL_NOW", "HOLD", "GRADE_FIRST", "MONITOR"}
    assert ev.confidence in {"HIGH", "MEDIUM", "LOW"}
    assert ev.reason_summary
    assert ev.reasons


def test_recalculate_persists_and_summary(session: Session, client: TestClient) -> None:
    email = "p89-persist@example.com"
    token = register_and_login(client, email)
    create_order(client, token)
    copy = session.exec(select(InventoryCopy)).one()
    owner_id = int(copy.user_id)
    copy.current_fmv = Decimal("25.00")
    session.add(copy)
    session.commit()

    summary = recalculate_sell_candidates(session, owner_user_id=owner_id, dry_run=False)
    session.commit()
    assert summary["candidates"] >= 1
    rows = list(session.exec(select(P89SellCandidate).where(P89SellCandidate.owner_user_id == owner_id)).all())
    assert len(rows) >= 1

    api_summary = build_p89_sell_candidate_summary(session, owner_user_id=owner_id)
    assert api_summary.total_candidates >= 1


def test_api_list_and_generate(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p89-api@example.com")
    owner_id = _owner_id(session, "p89-api@example.com")
    create_order(client, token)
    copy = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).one()
    copy.current_fmv = Decimal("30.00")
    session.add(copy)
    session.commit()

    gen = client.post("/api/v1/sell-candidates/generate", headers=auth_headers(token))
    assert gen.status_code == 200
    assert gen.json()["data"]["candidates"] >= 1

    listing = client.get("/api/v1/sell-candidates", headers=auth_headers(token))
    assert listing.status_code == 200
    items = listing.json()["data"]["items"]
    assert len(items) >= 1
    assert "recommendation" in items[0]
    assert "sell_score" in items[0]

    summary = client.get("/api/v1/sell-candidates/summary", headers=auth_headers(token))
    assert summary.status_code == 200
    assert summary.json()["data"]["total_candidates"] >= 1


def test_dry_run_writes_nothing(session: Session, client: TestClient) -> None:
    email = "p89-dry@example.com"
    token = register_and_login(client, email)
    create_order(client, token)
    copy = session.exec(select(InventoryCopy)).one()
    owner_id = int(copy.user_id)
    before = len(list(session.exec(select(P89SellCandidate)).all()))
    recalculate_sell_candidates(session, owner_user_id=owner_id, dry_run=True)
    after = len(list(session.exec(select(P89SellCandidate)).all()))
    assert before == after
    assert len(generate_evaluations(session, owner_user_id=owner_id)) >= 1
