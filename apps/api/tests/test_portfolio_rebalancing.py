from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import InventoryCopy, User
from app.services.portfolio_rebalancing import persist_portfolio_rebalancing_recommendations
from app.services.portfolio_rebalancing_engine import generate_portfolio_rebalancing_recommendations
from test_inventory import auth_headers, create_order, register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def _set_fmv(session: Session, *, owner_id: int, fmv: str) -> None:
    copies = list(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).all())
    for copy in copies:
        copy.current_fmv = Decimal(fmv)
        session.add(copy)
    session.commit()


def test_title_overexposure_generates_recommendation(client: TestClient, session: Session) -> None:
    email = "pr-title@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(
        client,
        token,
        items=[
            {
                "title": "Batman",
                "publisher": "DC",
                "issue_number": "1",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 10.00,
            },
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
        ],
    )
    copies = list(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).all())
    for copy in copies:
        if "Batman" in (copy.metadata_identity_key or ""):
            copy.current_fmv = Decimal("90.00")
        else:
            copy.current_fmv = Decimal("10.00")
        session.add(copy)
    session.commit()
    results = generate_portfolio_rebalancing_recommendations(session, owner_user_id=owner_id)
    title = next(r for r in results if r.rebalance_type == "TITLE_OVEREXPOSURE" and "Batman" in r.target_label)
    assert title.exposure_percent == 90.0
    assert title.priority_score >= 70.0
    assert title.recommended_action in {"REDUCE_EXPOSURE", "REVIEW_POSITION"}
    assert "90" in title.rationale or "Batman" in title.rationale


def test_publisher_overexposure_generates_recommendation(client: TestClient, session: Session) -> None:
    email = "pr-pub@example.com"
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
                "raw_item_price": 10.00,
            },
            {
                "title": "X-Men",
                "publisher": "Marvel",
                "issue_number": "2",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 10.00,
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
                "quantity": 1,
                "raw_item_price": 5.00,
            },
        ],
    )
    copies = list(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).all())
    for copy in copies:
        if "Marvel" in (copy.metadata_identity_key or ""):
            copy.current_fmv = Decimal("60.00")
        else:
            copy.current_fmv = Decimal("10.00")
        session.add(copy)
    session.commit()
    results = generate_portfolio_rebalancing_recommendations(session, owner_user_id=owner_id)
    pub = next(r for r in results if r.rebalance_type == "PUBLISHER_OVEREXPOSURE" and r.target_label == "Marvel")
    assert pub.exposure_percent >= 40.0
    assert pub.priority_score >= 70.0


def test_duplicate_capital_generates_recommendation(client: TestClient, session: Session) -> None:
    email = "pr-dup@example.com"
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
    _set_fmv(session, owner_id=owner_id, fmv="15.00")
    results = generate_portfolio_rebalancing_recommendations(session, owner_user_id=owner_id)
    dup = next(r for r in results if r.rebalance_type == "DUPLICATE_CAPITAL")
    assert dup.exposure_value >= 45.0
    assert dup.priority_score >= 72.0
    assert "duplicate" in dup.rationale.lower()


def test_low_efficiency_capital_generates_recommendation(client: TestClient, session: Session) -> None:
    email = "pr-low@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token)
    copy = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).one()
    copy.current_fmv = Decimal("8.00")
    copy.acquisition_cost = Decimal("10.00")
    session.add(copy)
    session.commit()
    results = generate_portfolio_rebalancing_recommendations(session, owner_user_id=owner_id)
    low = next((r for r in results if r.rebalance_type == "LOW_EFFICIENCY_CAPITAL"), None)
    assert low is not None
    assert 50.0 <= low.priority_score <= 70.0
    assert low.confidence_score > 0


def test_exposure_percent_calculated(client: TestClient, session: Session) -> None:
    email = "pr-pct@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token)
    _set_fmv(session, owner_id=owner_id, fmv="100.00")
    results = generate_portfolio_rebalancing_recommendations(session, owner_user_id=owner_id)
    assert any(r.exposure_percent == 100.0 for r in results if r.rebalance_type == "TITLE_OVEREXPOSURE")


def test_idempotency(client: TestClient, session: Session) -> None:
    email = "pr-idem@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token, items=[{"title": "Batman", "publisher": "DC", "issue_number": "1", "cover_name": "Cover A", "printing": None, "ratio": None, "variant_type": None, "cover_artist": None, "quantity": 3, "raw_item_price": 10.00}])
    _set_fmv(session, owner_id=owner_id, fmv="20.00")
    first = persist_portfolio_rebalancing_recommendations(session, owner_user_id=owner_id)
    assert first >= 1
    second = persist_portfolio_rebalancing_recommendations(session, owner_user_id=owner_id)
    assert second == 0


def test_api_owner_isolation(client: TestClient, session: Session) -> None:
    token_a = register_and_login(client, "pr-a@example.com")
    token_b = register_and_login(client, "pr-b@example.com")
    owner_a = _owner_id(session, "pr-a@example.com")
    create_order(client, token_a)
    _set_fmv(session, owner_id=owner_a, fmv="50.00")
    client.get("/api/v1/portfolio-rebalancing/latest", headers=auth_headers(token_a))
    list_a = client.get("/api/v1/portfolio-rebalancing", headers=auth_headers(token_a))
    list_b = client.get("/api/v1/portfolio-rebalancing", headers=auth_headers(token_b))
    assert len(list_a.json()["data"]["items"]) >= 1
    assert len(list_b.json()["data"]["items"]) == 0


def test_batman_portfolio_manual_scenario(client: TestClient, session: Session) -> None:
    email = "pr-batman@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(
        client,
        token,
        items=[
            {
                "title": "Batman",
                "publisher": "DC",
                "issue_number": "1",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 3,
                "raw_item_price": 10.00,
            },
            {
                "title": "Other",
                "publisher": "Image",
                "issue_number": "1",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 5.00,
            },
        ],
    )
    copies = list(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).all())
    for copy in copies:
        if "Batman" in (copy.metadata_identity_key or ""):
            copy.current_fmv = Decimal("40.00")
        else:
            copy.current_fmv = Decimal("10.00")
        session.add(copy)
    session.commit()
    results = generate_portfolio_rebalancing_recommendations(session, owner_user_id=owner_id)
    batman_title = next(r for r in results if r.rebalance_type == "TITLE_OVEREXPOSURE" and "Batman" in r.target_label)
    assert batman_title.exposure_percent >= 30.0
    assert batman_title.recommended_action in {"REDUCE_EXPOSURE", "REVIEW_POSITION"}
