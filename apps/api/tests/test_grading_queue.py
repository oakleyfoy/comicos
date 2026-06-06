from __future__ import annotations

from sqlmodel import Session, select

from app.models import InventoryCopy, User
from app.schemas.p72_grading_operations import P72GradingQueueEnqueuePayload
from app.services.grading_queue_service import STATUS_CANDIDATE, enqueue_queue_entries, list_queue_entries
from test_inventory import create_order, register_and_login
from fastapi.testclient import TestClient


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_enqueue_and_list_queue(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p72-queue@example.com")
    owner_id = _owner_id(session, "p72-queue@example.com")
    create_order(client, token)
    copy = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).one()
    cid = int(copy.id or 0)

    rows = enqueue_queue_entries(
        session,
        owner_user_id=owner_id,
        payload=P72GradingQueueEnqueuePayload(inventory_copy_ids=[cid], target_grader="CGC"),
    )
    assert len(rows) == 1
    assert rows[0].status == STATUS_CANDIDATE
    assert rows[0].inventory_copy_id == cid

    listed = list_queue_entries(session, owner_user_id=owner_id, status=STATUS_CANDIDATE)
    assert listed.total_items >= 1

    resp = client.get(
        "/api/v1/grading-intelligence/queue",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()["data"]["items"]) >= 1
