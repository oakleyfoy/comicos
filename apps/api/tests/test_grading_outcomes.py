from __future__ import annotations

from datetime import date

from sqlmodel import Session, select

from app.models.p72_grading_analytics import P72GradingOutcome
from app.models import InventoryCopy, User
from app.schemas.p72_grading_operations import P72GradingQueueEnqueuePayload, P72GradingQueueStatusPayload
from app.services.grading_outcome_service import list_outcomes, sync_outcomes_from_queue
from app.services.grading_queue_service import (
    STATUS_AT_CGC,
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


def _returned_workflow(session: Session, owner_id: int, copy_id: int) -> int:
    q = enqueue_queue_entries(
        session,
        owner_user_id=owner_id,
        payload=P72GradingQueueEnqueuePayload(inventory_copy_ids=[copy_id]),
    )
    qid = q[0].id
    for st in (STATUS_READY, STATUS_SUBMITTED, STATUS_AT_CGC, STATUS_GRADING_COMPLETE):
        update_queue_status(
            session,
            owner_user_id=owner_id,
            queue_entry_id=qid,
            payload=P72GradingQueueStatusPayload(status=st),
        )
    update_queue_status(
        session,
        owner_user_id=owner_id,
        queue_entry_id=qid,
        payload=P72GradingQueueStatusPayload(
            status=STATUS_RETURNED,
            actual_grade="9.6",
            certification_number="999",
            final_grading_cost=32.0,
            actual_completion_date=date.today(),
        ),
    )
    return qid


def test_outcome_recorded_on_return(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p72-out@example.com")
    owner_id = _owner_id(session, "p72-out@example.com")
    create_order(client, token)
    copy = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).one()
    qid = _returned_workflow(session, owner_id, int(copy.id or 0))
    rows = session.exec(select(P72GradingOutcome).where(P72GradingOutcome.queue_entry_id == qid)).all()
    assert len(rows) == 1
    assert rows[0].actual_grade == "9.6"
    assert float(rows[0].actual_grading_cost) == 32.0
    assert rows[0].expected_grade
    assert list_outcomes(session, owner_user_id=owner_id)


def test_outcomes_api(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p72-out-api@example.com")
    owner_id = _owner_id(session, "p72-out-api@example.com")
    create_order(client, token)
    copy = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).one()
    _returned_workflow(session, owner_id, int(copy.id or 0))
    sync_outcomes_from_queue(session, owner_user_id=owner_id)
    resp = client.get(
        "/api/v1/grading-intelligence/outcomes",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()["data"]["items"]) >= 1
