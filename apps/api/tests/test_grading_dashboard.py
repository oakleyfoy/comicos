from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlmodel import Session, select

from app.models import InventoryCopy, User
from app.models.market_pricing_engine import P68MarketPriceSnapshot
from app.services.grading_dashboard import build_grading_dashboard
from test_inventory import create_order, register_and_login
from fastapi.testclient import TestClient


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_dashboard_includes_p72_decision_engine(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p72-dash@example.com")
    assert token
    owner_id = _owner_id(session, "p72-dash@example.com")
    create_order(client, token)
    copy = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).one()
    copy.grade_status = "raw"
    copy.current_fmv = Decimal("22.00")
    copy.release_year = 2024
    session.add(copy)
    session.add(
        P68MarketPriceSnapshot(
            owner_user_id=owner_id,
            generated_at=datetime.now(timezone.utc),
            inventory_copy_id=int(copy.id or 0),
            title="Absolute Batman",
            publisher="DC",
            issue_number="1",
            raw_fmv=22.0,
            blended_fmv=22.0,
            graded_fmv=95.0,
            sales_count=8,
            liquidity_score=50.0,
            confidence=0.65,
            primary_provider="EBAY_SOLD",
            metadata_json={},
        )
    )
    session.commit()

    dash = build_grading_dashboard(session, owner_user_id=owner_id)
    assert dash.decision_engine is not None
    assert dash.decision_engine.candidate_count >= 1
    assert dash.decision_engine.top_grade_candidates
    row = dash.decision_engine.top_grade_candidates[0]
    assert row.raw_fmv == 22.0
    assert row.expected_graded_fmv > 0
    assert row.recommendation


def test_p72_candidates_api(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p72-api@example.com")
    owner_id = _owner_id(session, "p72-api@example.com")
    create_order(client, token)
    copy = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).one()
    copy.grade_status = "raw"
    copy.current_fmv = Decimal("15.00")
    session.add(copy)
    session.commit()

    resp = client.get(
        "/api/v1/grading-intelligence/candidates",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert "items" in body
    assert len(body["items"]) >= 1


def test_dashboard_includes_p72_operations_engine(client: TestClient, session: Session) -> None:
    from app.schemas.p72_grading_operations import P72GradingQueueEnqueuePayload
    from app.services.grading_queue_service import enqueue_queue_entries
    from app.services.p72_grading_operations_dashboard import build_operations_dashboard

    token = register_and_login(client, "p72-ops-dash@example.com")
    owner_id = _owner_id(session, "p72-ops-dash@example.com")
    create_order(client, token)
    copy = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).one()
    enqueue_queue_entries(
        session,
        owner_user_id=owner_id,
        payload=P72GradingQueueEnqueuePayload(inventory_copy_ids=[int(copy.id or 0)]),
    )

    ops = build_operations_dashboard(session, owner_user_id=owner_id)
    assert ops.metrics.waiting_count >= 1

    resp = client.get(
        "/api/v1/grading-intelligence/dashboard",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data.get("operations_engine") is not None
    assert data["operations_engine"]["metrics"]["waiting_count"] >= 1
