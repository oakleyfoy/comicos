from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import (
    ConventionEvent,
    ConventionInventoryAssignment,
    ConventionInventoryMovement,
    ConventionPriceSnapshot,
    ConventionSaleSession,
)
from app.services.convention_operations import resolve_convention_price
from test_inventory import auth_headers, create_order, register_and_login


def _inventory_copy_id(client: TestClient, token: str) -> int:
    response = client.get("/inventory", headers=auth_headers(token))
    assert response.status_code == 200
    return int(response.json()["items"][0]["inventory_copy_id"])


def _create_event(client: TestClient, token: str, *, replay_key: str, name: str = "Metro Show") -> int:
    response = client.post(
        "/convention-events",
        json={
            "name": name,
            "venue": "Center Hall",
            "city": "Chicago",
            "state": "IL",
            "country": "US",
            "start_date": "2026-06-01",
            "end_date": "2026-06-02",
            "event_type": "convention",
            "notes": "Dealer floor",
            "replay_key": replay_key,
        },
        headers=auth_headers(token),
    )
    assert response.status_code == 201
    return int(response.json()["id"])


def test_convention_event_assignment_price_and_session_replay(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "conv-replay@example.com")
    create_order(client, token)
    inventory_copy_id = _inventory_copy_id(client, token)
    event_id = _create_event(client, token, replay_key="conv-event-rk")

    replay = client.post(
        "/convention-events",
        json={
            "name": "Metro Show",
            "venue": "Center Hall",
            "city": "Chicago",
            "state": "IL",
            "country": "US",
            "start_date": "2026-06-01",
            "end_date": "2026-06-02",
            "event_type": "convention",
            "notes": "Dealer floor",
            "replay_key": "conv-event-rk",
        },
        headers=auth_headers(token),
    )
    assert replay.status_code == 200
    assert int(replay.json()["id"]) == event_id

    activated = client.post(
        f"/convention-events/{event_id}/activate",
        json={"replay_key": "conv-event-activate"},
        headers=auth_headers(token),
    )
    assert activated.status_code == 200
    assert activated.json()["status"] == "ACTIVE"

    assignment = client.post(
        "/convention-assignments",
        json={
            "convention_event_id": event_id,
            "inventory_item_id": inventory_copy_id,
            "assignment_type": "wall",
            "local_price_amount": "22.50",
            "local_price_currency": "usd",
            "display_location": "Front wall",
            "priority_rank": 1,
            "replay_key": "conv-assign-rk",
        },
        headers=auth_headers(token),
    )
    assert assignment.status_code == 201
    assignment_id = int(assignment.json()["id"])

    assignment_replay = client.post(
        "/convention-assignments",
        json={
            "convention_event_id": event_id,
            "inventory_item_id": inventory_copy_id,
            "assignment_type": "wall",
            "local_price_amount": "22.50",
            "local_price_currency": "usd",
            "display_location": "Front wall",
            "priority_rank": 1,
            "replay_key": "conv-assign-rk",
        },
        headers=auth_headers(token),
    )
    assert assignment_replay.status_code == 200
    assert int(assignment_replay.json()["id"]) == assignment_id

    movement = client.post(
        "/convention-movements",
        json={
            "convention_event_id": event_id,
            "inventory_item_id": inventory_copy_id,
            "movement_type": "MOVED",
            "from_location": "Front wall",
            "to_location": "Showcase 2",
            "notes": "Moved to glass case",
            "replay_key": "conv-movement-rk",
        },
        headers=auth_headers(token),
    )
    assert movement.status_code == 201

    movement_replay = client.post(
        "/convention-movements",
        json={
            "convention_event_id": event_id,
            "inventory_item_id": inventory_copy_id,
            "movement_type": "MOVED",
            "from_location": "Front wall",
            "to_location": "Showcase 2",
            "notes": "Moved to glass case",
            "replay_key": "conv-movement-rk",
        },
        headers=auth_headers(token),
    )
    assert movement_replay.status_code == 200
    assert int(movement_replay.json()["id"]) == int(movement.json()["id"])

    price_one = client.post(
        "/convention-price-snapshots",
        json={
            "convention_event_id": event_id,
            "inventory_item_id": inventory_copy_id,
            "price_amount": "25.00",
            "currency": "usd",
            "pricing_source": "convention_override",
            "replay_key": "conv-price-rk-1",
        },
        headers=auth_headers(token),
    )
    assert price_one.status_code == 201
    price_two = client.post(
        "/convention-price-snapshots",
        json={
            "convention_event_id": event_id,
            "inventory_item_id": inventory_copy_id,
            "price_amount": "27.00",
            "currency": "usd",
            "pricing_source": "negotiated",
            "replay_key": "conv-price-rk-2",
        },
        headers=auth_headers(token),
    )
    assert price_two.status_code == 201

    event_row = session.get(ConventionEvent, event_id)
    assert event_row is not None
    resolved = resolve_convention_price(
        session,
        owner_user_id=int(event_row.owner_user_id),
        inventory_item_id=inventory_copy_id,
        convention_event_id=event_id,
    )
    assert resolved["source"] == "negotiated"
    assert str(resolved["price_amount"]) == "27.00"

    session_create = client.post(
        "/convention-sale-sessions",
        json={"convention_event_id": event_id, "notes": "Main selling window", "replay_key": "conv-session-rk"},
        headers=auth_headers(token),
    )
    assert session_create.status_code == 201
    session_id = int(session_create.json()["id"])

    session_replay = client.post(
        "/convention-sale-sessions",
        json={"convention_event_id": event_id, "notes": "Main selling window", "replay_key": "conv-session-rk"},
        headers=auth_headers(token),
    )
    assert session_replay.status_code == 200
    assert int(session_replay.json()["id"]) == session_id

    close = client.post(
        f"/convention-sale-sessions/{session_id}/close",
        json={"replay_key": "conv-session-close"},
        headers=auth_headers(token),
    )
    assert close.status_code == 200
    assert close.json()["status"] == "CLOSED"

    event_rows = session.exec(select(ConventionEvent)).all()
    assignment_rows = session.exec(select(ConventionInventoryAssignment)).all()
    movement_rows = session.exec(select(ConventionInventoryMovement)).all()
    price_rows = session.exec(select(ConventionPriceSnapshot)).all()
    session_rows = session.exec(select(ConventionSaleSession)).all()
    assert len(event_rows) == 1
    assert len(assignment_rows) == 1
    assert len(movement_rows) == 1
    assert len(price_rows) == 2
    assert len(session_rows) == 1


def test_convention_assignment_ordering_and_uniqueness(client: TestClient) -> None:
    token = register_and_login(client, "conv-order@example.com")
    create_order(client, token)
    create_order(client, token)
    first_copy = _inventory_copy_id(client, token)
    second_copy = int(client.get("/inventory", headers=auth_headers(token)).json()["items"][1]["inventory_copy_id"])
    event_id = _create_event(client, token, replay_key="conv-order-event")

    first = client.post(
        "/convention-assignments",
        json={
            "convention_event_id": event_id,
            "inventory_item_id": first_copy,
            "assignment_type": "showcase",
            "display_location": "Showcase B",
            "priority_rank": 2,
            "replay_key": "conv-order-assign-1",
        },
        headers=auth_headers(token),
    )
    assert first.status_code == 201

    second = client.post(
        "/convention-assignments",
        json={
            "convention_event_id": event_id,
            "inventory_item_id": second_copy,
            "assignment_type": "wall",
            "display_location": "Wall A",
            "priority_rank": 1,
            "replay_key": "conv-order-assign-2",
        },
        headers=auth_headers(token),
    )
    assert second.status_code == 201

    listing = client.get(
        "/convention-assignments",
        params={"convention_event_id": event_id, "limit": 10, "offset": 0},
        headers=auth_headers(token),
    )
    assert listing.status_code == 200
    rows = listing.json()["items"]
    assert [row["priority_rank"] for row in rows[:2]] == [1, 2]

    duplicate = client.post(
        "/convention-assignments",
        json={
            "convention_event_id": event_id,
            "inventory_item_id": first_copy,
            "assignment_type": "featured",
            "display_location": "Featured",
            "priority_rank": 3,
            "replay_key": "conv-order-assign-3",
        },
        headers=auth_headers(token),
    )
    assert duplicate.status_code == 409


def test_convention_owner_and_ops_scoping(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "conv-ops@example.com")
    get_settings.cache_clear()

    owner = register_and_login(client, "conv-owner@example.com")
    other = register_and_login(client, "conv-other@example.com")
    ops = register_and_login(client, "conv-ops@example.com")

    create_order(client, owner)
    event_id = _create_event(client, owner, replay_key="conv-scope-event")

    owner_lookup = client.get(f"/convention-events/{event_id}", headers=auth_headers(owner))
    assert owner_lookup.status_code == 200

    forbidden_lookup = client.get(f"/convention-events/{event_id}", headers=auth_headers(other))
    assert forbidden_lookup.status_code == 404

    ops_list = client.get(
        "/ops/convention-events",
        params={"owner_user_id": int(owner_lookup.json()["owner_user_id"]), "limit": 10, "offset": 0},
        headers=auth_headers(ops),
    )
    assert ops_list.status_code == 200
    assert ops_list.json()["total_items"] == 1

    assert client.get("/ops/convention-events", headers=auth_headers(other)).status_code == 403


def test_convention_movement_append_only_and_close_route(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "conv-movement@example.com")
    create_order(client, token)
    event_id = _create_event(client, token, replay_key="conv-move-event")
    copy_id = _inventory_copy_id(client, token)

    assignment = client.post(
        "/convention-assignments",
        json={
            "convention_event_id": event_id,
            "inventory_item_id": copy_id,
            "assignment_type": "reserve",
            "display_location": "Reserve case",
            "priority_rank": 1,
            "replay_key": "conv-move-assign",
        },
        headers=auth_headers(token),
    )
    assert assignment.status_code == 201

    move_one = client.post(
        "/convention-movements",
        json={
            "convention_event_id": event_id,
            "inventory_item_id": copy_id,
            "movement_type": "MOVED",
            "from_location": "Reserve case",
            "to_location": "Register tray",
            "replay_key": "conv-move-one",
        },
        headers=auth_headers(token),
    )
    assert move_one.status_code == 201

    move_two = client.post(
        "/convention-movements",
        json={
            "convention_event_id": event_id,
            "inventory_item_id": copy_id,
            "movement_type": "SOLD",
            "from_location": "Register tray",
            "to_location": "Sold",
            "replay_key": "conv-move-two",
        },
        headers=auth_headers(token),
    )
    assert move_two.status_code == 201

    assignment_row = session.exec(select(ConventionInventoryAssignment)).one()
    assert assignment_row.removed_at is not None

    movement_rows = session.exec(select(ConventionInventoryMovement)).all()
    assert len(movement_rows) == 2

    sale_session = client.post(
        "/convention-sale-sessions",
        json={"convention_event_id": event_id, "replay_key": "conv-close-session"},
        headers=auth_headers(token),
    )
    assert sale_session.status_code == 201
    session_id = int(sale_session.json()["id"])

    close_response = client.post(
        f"/convention-sale-sessions/{session_id}/close",
        json={"replay_key": "conv-close-session-final"},
        headers=auth_headers(token),
    )
    assert close_response.status_code == 200
    assert close_response.json()["status"] == "CLOSED"

