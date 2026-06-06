from __future__ import annotations

from datetime import date

from sqlmodel import Session, select

from app.models import InventoryCopy, User
from app.models.p72_grading_operations import P72InventoryGradingHistory
from app.schemas.p72_grading_operations import P72GradingQueueEnqueuePayload, P72GradingQueueStatusPayload
from app.services.grading_audit_log import list_audit_for_queue_entry
from app.services.grading_queue_service import (
    STATUS_AT_CGC,
    STATUS_CANDIDATE,
    STATUS_GRADING_COMPLETE,
    STATUS_LISTED,
    STATUS_READY,
    STATUS_RETURNED,
    STATUS_SUBMITTED,
    enqueue_queue_entries,
    update_queue_status,
)
from test_inventory import create_order, register_and_login
from fastapi.testclient import TestClient


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def _advance_to_submitted(session: Session, owner_id: int, qid: int) -> None:
    update_queue_status(
        session,
        owner_user_id=owner_id,
        queue_entry_id=qid,
        payload=P72GradingQueueStatusPayload(status=STATUS_READY),
    )
    update_queue_status(
        session,
        owner_user_id=owner_id,
        queue_entry_id=qid,
        payload=P72GradingQueueStatusPayload(status=STATUS_SUBMITTED, submission_date=date.today()),
    )


def test_full_status_workflow_and_return_processing(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p72-flow@example.com")
    owner_id = _owner_id(session, "p72-flow@example.com")
    create_order(client, token)
    copy = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).one()
    q = enqueue_queue_entries(
        session,
        owner_user_id=owner_id,
        payload=P72GradingQueueEnqueuePayload(inventory_copy_ids=[int(copy.id or 0)]),
    )
    qid = q[0].id
    assert q[0].status == STATUS_CANDIDATE

    _advance_to_submitted(session, owner_id, qid)
    for status in (STATUS_AT_CGC, STATUS_GRADING_COMPLETE):
        update_queue_status(
            session,
            owner_user_id=owner_id,
            queue_entry_id=qid,
            payload=P72GradingQueueStatusPayload(status=status),
        )
    returned = update_queue_status(
        session,
        owner_user_id=owner_id,
        queue_entry_id=qid,
        payload=P72GradingQueueStatusPayload(
            status=STATUS_RETURNED,
            actual_grade="9.6",
            certification_number="12345678",
            final_grading_cost=32.0,
            slab_notes="Clean slab",
            actual_completion_date=date.today(),
        ),
    )
    assert returned.actual_grade == "9.6"
    assert returned.certification_number == "12345678"

    hist = session.exec(
        select(P72InventoryGradingHistory).where(P72InventoryGradingHistory.queue_entry_id == qid)
    ).all()
    assert len(hist) == 1

    update_queue_status(
        session,
        owner_user_id=owner_id,
        queue_entry_id=qid,
        payload=P72GradingQueueStatusPayload(status=STATUS_LISTED),
    )
    logs = list_audit_for_queue_entry(session, owner_user_id=owner_id, queue_entry_id=qid, limit=20)
    assert any(log.new_status == STATUS_RETURNED for log in logs)

    resp = client.post(
        f"/api/v1/grading-intelligence/queue/{qid}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "SOLD"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "SOLD"
