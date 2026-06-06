from __future__ import annotations

from sqlmodel import Session, select

from app.models import InventoryCopy, User
from app.schemas.p72_grading_operations import P72GradingBatchCreatePayload, P72GradingQueueEnqueuePayload
from app.services.grading_queue_service import enqueue_queue_entries
from app.services.grading_submission_batch import create_batch, list_batches
from test_inventory import create_order, register_and_login
from fastapi.testclient import TestClient


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_create_batch_with_assignment(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p72-batch@example.com")
    owner_id = _owner_id(session, "p72-batch@example.com")
    create_order(client, token)
    copy = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).one()
    q = enqueue_queue_entries(
        session,
        owner_user_id=owner_id,
        payload=P72GradingQueueEnqueuePayload(inventory_copy_ids=[int(copy.id or 0)]),
    )
    batch = create_batch(
        session,
        owner_user_id=owner_id,
        payload=P72GradingBatchCreatePayload(
            batch_name="CGC June 2026 Batch",
            queue_entry_ids=[q[0].id],
            estimated_cost=38.0,
        ),
    )
    assert batch.batch_name == "CGC June 2026 Batch"
    assert batch.book_count >= 1

    listed = list_batches(session, owner_user_id=owner_id)
    assert listed.total_items >= 1

    resp = client.post(
        "/api/v1/grading-intelligence/batches",
        headers={"Authorization": f"Bearer {token}"},
        json={"batch_name": "CGC SDCC Submission", "queue_entry_ids": []},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["batch_name"] == "CGC SDCC Submission"
