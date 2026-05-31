from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.models.data_integrity import ChangeRecord
from app.services.change_tracking import diff_payloads, track_entity_change
from test_inventory import register_and_login


def test_diff_payloads_is_deterministic_and_tracks_entity_changes(client: TestClient) -> None:
    register_and_login(client, "change-owner@example.com")

    first = diff_payloads({"b": 2, "a": 1}, {"a": 3, "b": 2, "c": True})
    second = diff_payloads({"a": 1, "b": 2}, {"c": True, "a": 3, "b": 2})

    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == "change-owner@example.com")).one()
        owner_user_id = int(owner.id or 0)
        detail = track_entity_change(
            session,
            owner_user_id=owner_user_id,
            actor_id=owner_user_id,
            actor_type="user",
            action_type="update",
            entity_type="marketplace_listing",
            entity_id=5,
            source="unit_test",
            before_payload={"title": "Old", "price": 12},
            after_payload={"title": "New", "price": 15},
            event_payload_json={"changed_field_count": 2},
        )
        change_rows = session.exec(select(ChangeRecord).where(ChangeRecord.audit_event_id == detail.event.id)).all()

    assert first == second
    assert [item["field_name"] for item in first] == ["a", "c"]
    assert len(detail.changes) == 2
    assert len(change_rows) == 2
