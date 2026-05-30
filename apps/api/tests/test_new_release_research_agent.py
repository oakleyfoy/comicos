from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from agent_security_test_utils import grant_agent_execute
from app.models import AgentDefinition, InventoryCopy, User
from app.services.agent_registry import enable_agent
from app.services.agent_seed import seed_foundational_agents
from app.services.new_release_research_agent import run_new_release_research_agent
from test_inventory import create_order, register_and_login


def _enabled_new_release_agent(session: Session) -> None:
    seed_foundational_agents(session)
    row = session.exec(select(AgentDefinition).where(AgentDefinition.code == "new_release_research_agent")).first()
    assert row is not None and row.id is not None
    enable_agent(session, agent_id=int(row.id))
    grant_agent_execute(session, agent_id=int(row.id))


def _owner(session: Session, email: str) -> User:
    row = session.exec(select(User).where(User.email == email)).one()
    assert row.id is not None
    return row


def _seed_release_inventory(client: TestClient, session: Session, *, email: str) -> User:
    token = register_and_login(client, email)
    create_order(
        client,
        token,
        order_date="2026-05-01",
        items=[
            {
                "title": "Radiant Black",
                "publisher": "Image",
                "issue_number": "1",
                "release_date": (date.today() + timedelta(days=14)).isoformat(),
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 4.99,
            },
            {
                "title": "Monstress",
                "publisher": "Image",
                "issue_number": "2",
                "release_date": date.today().isoformat(),
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 5.99,
            },
            {
                "title": "Saga",
                "publisher": "Image",
                "issue_number": "5",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 6.99,
            },
        ],
    )
    user = _owner(session, email)
    copies = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == user.id).order_by(InventoryCopy.id.asc())).all()
    assert len(copies) == 3

    upcoming = copies[0]
    upcoming.order_status = "preordered"
    upcoming.release_status = "not_released_yet"
    upcoming.expected_ship_date = date.today() + timedelta(days=16)

    this_week = copies[1]
    this_week.order_status = "preordered"
    this_week.release_status = "not_released_yet"
    this_week.expected_ship_date = date.today() + timedelta(days=2)

    missing = copies[2]
    missing.order_status = "preordered"
    missing.release_status = "not_released_yet"
    missing.release_date = None
    missing.expected_ship_date = None

    session.add(upcoming)
    session.add(this_week)
    session.add(missing)
    session.commit()
    return user


def _release_state(session: Session, *, owner_user_id: int) -> list[tuple]:
    rows = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id).order_by(InventoryCopy.id.asc())).all()
    return [
        (
            int(row.id or 0),
            row.order_status,
            row.release_status,
            None if row.release_date is None else row.release_date.isoformat(),
            None if row.expected_ship_date is None else row.expected_ship_date.isoformat(),
        )
        for row in rows
    ]


def test_new_release_research_agent_creates_deterministic_evidence_backed_findings(
    client: TestClient,
    session: Session,
) -> None:
    _enabled_new_release_agent(session)
    user = _seed_release_inventory(client, session, email="new-release-research-owner@example.com")
    before_state = _release_state(session, owner_user_id=int(user.id or 0))

    first = run_new_release_research_agent(session, current_user=user)
    second = run_new_release_research_agent(session, current_user=user)

    assert first.snapshot.status == "COMPLETED"
    assert second.snapshot.status == "COMPLETED"
    assert [
        (row.finding_code, row.finding_type, row.recommendation_json, [e.source_payload_json for e in row.evidence])
        for row in first.findings
    ] == [
        (row.finding_code, row.finding_type, row.recommendation_json, [e.source_payload_json for e in row.evidence])
        for row in second.findings
    ]
    assert {row.finding_type for row in first.findings} >= {
        "upcoming_release_to_watch",
        "possible_spec_candidate",
        "release_this_week",
        "missing_market_data",
    }
    assert all(row.evidence for row in first.findings)
    assert before_state == _release_state(session, owner_user_id=int(user.id or 0))
