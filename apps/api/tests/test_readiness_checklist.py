from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db.session import get_engine
from app.services.readiness_checklist import generate_readiness_checklist, list_checklist_items_for_owner


def test_readiness_checklist_generates_eight_categories(client: TestClient) -> None:
    owner_user_id = 9002
    with Session(get_engine()) as session:
        items = generate_readiness_checklist(session, owner_user_id=owner_user_id)
        assert len(items) == 8
        categories = {item.checklist_category for item in items}
        assert categories == {
            "Marketplace Platform",
            "Forecast Platform",
            "Data Protection",
            "Operations Reliability",
            "Agent Platform",
            "Database Health",
            "Backup Validation",
            "Restore Validation",
        }
        listed, total = list_checklist_items_for_owner(session, owner_user_id=owner_user_id, limit=50, offset=0)
        assert total >= 8
        assert len(listed) >= 8

        second_run = generate_readiness_checklist(session, owner_user_id=owner_user_id)
        assert len(second_run) == 8
        _, total_after = list_checklist_items_for_owner(session, owner_user_id=owner_user_id, limit=200, offset=0)
        assert total_after >= 16
