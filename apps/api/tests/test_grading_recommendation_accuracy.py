from __future__ import annotations

from datetime import date

from sqlmodel import Session, select

from app.models import InventoryCopy, User
from app.schemas.p72_grading_operations import P72GradingQueueEnqueuePayload, P72GradingQueueStatusPayload
from app.services.grading_outcome_service import list_outcomes
from app.services.grading_queue_service import (
    STATUS_AT_CGC,
    STATUS_GRADING_COMPLETE,
    STATUS_READY,
    STATUS_RETURNED,
    STATUS_SUBMITTED,
    enqueue_queue_entries,
    update_queue_status,
)
from app.services.p72_grading_analytics_service import build_recommendation_accuracy
from test_inventory import create_order, register_and_login
from fastapi.testclient import TestClient


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_recommendation_accuracy_payload(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p72-rec-acc@example.com")
    owner_id = _owner_id(session, "p72-rec-acc@example.com")
    create_order(client, token)
    copy = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).one()
    q = enqueue_queue_entries(
        session,
        owner_user_id=owner_id,
        payload=P72GradingQueueEnqueuePayload(inventory_copy_ids=[int(copy.id or 0)]),
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
            actual_grade="9.8",
            final_grading_cost=30.0,
            actual_completion_date=date.today(),
        ),
    )
    assert list_outcomes(session, owner_user_id=owner_id)
    acc = build_recommendation_accuracy(session, owner_user_id=owner_id)
    assert acc.sample_count >= 1
    assert acc.overall_accuracy_pct >= 0

    dash = client.get(
        "/api/v1/grading-intelligence/analytics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert dash.status_code == 200
    assert dash.json()["data"]["recommendation_accuracy"]["sample_count"] >= 1
