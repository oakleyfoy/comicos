from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.models.data_integrity import AuditEvent, ChangeRecord
from app.services.audit_trail import get_audit_event, list_audit_events, log_audit_event, log_change_record
from test_inventory import register_and_login


def test_audit_trail_is_append_only_and_change_records_remain_separate(client: TestClient) -> None:
    register_and_login(client, "audit-owner@example.com")

    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == "audit-owner@example.com")).one()
        owner_user_id = int(owner.id or 0)

        first = log_audit_event(
            session,
            owner_user_id=owner_user_id,
            actor_id=owner_user_id,
            actor_type="user",
            action_type="inventory_update",
            entity_type="inventory_copy",
            entity_id=101,
            source="unit_test",
            event_payload_json={"changed_field_count": 1},
        )
        change = log_change_record(
            session,
            audit_event_id=first.id,
            field_name="grade_status",
            before_value_json="raw",
            after_value_json="graded",
        )
        second = log_audit_event(
            session,
            owner_user_id=owner_user_id,
            actor_id=owner_user_id,
            actor_type="user",
            action_type="listing_publish",
            entity_type="marketplace_listing",
            entity_id=22,
            source="unit_test",
            event_payload_json={"changed_field_count": 0},
        )
        listing = list_audit_events(session, owner_user_id=owner_user_id, limit=10, offset=0)
        detail = get_audit_event(session, owner_user_id=owner_user_id, audit_event_id=first.id)
        events = session.exec(select(AuditEvent).where(AuditEvent.owner_user_id == owner_user_id)).all()
        changes = session.exec(select(ChangeRecord).where(ChangeRecord.audit_event_id == first.id)).all()

    assert first.id != second.id
    assert change.audit_event_id == first.id
    assert len(listing.items) == 2
    assert len(events) == 2
    assert len(changes) == 1
    assert detail.event.action_type == "inventory_update"
    assert detail.changes[0].field_name == "grade_status"
