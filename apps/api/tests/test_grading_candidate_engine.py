from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlmodel import Session, select

from app.models import InventoryCopy, User
from app.models.market_pricing_engine import P68MarketPriceSnapshot
from app.services.grading_candidate_engine import (
    REC_DO_NOT_GRADE,
    REC_GRADE,
    REC_PRESS_AND_GRADE,
    REC_WATCH,
    discover_grading_candidates,
)
from test_inventory import create_order, register_and_login
from fastapi.testclient import TestClient


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_discover_grading_candidates_for_raw_copy(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p72-cand@example.com")
    assert token
    owner_id = _owner_id(session, "p72-cand@example.com")
    create_order(client, token)
    copy = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_id)).one()
    copy.grade_status = "raw"
    copy.current_fmv = Decimal("22.00")
    copy.release_year = 2024
    copy.condition_notes = "NM; light crease"
    copy.metadata_identity_key = "dc|absolute batman|1|"
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
            sales_count=12,
            liquidity_score=55.0,
            confidence=0.7,
            primary_provider="EBAY_SOLD",
            metadata_json={},
        )
    )
    session.commit()

    rows = discover_grading_candidates(session, owner_user_id=owner_id, limit=10)
    assert len(rows) >= 1
    top = rows[0]
    assert top.raw_fmv == 22.0
    assert top.recommendation in {REC_PRESS_AND_GRADE, REC_GRADE, REC_WATCH, REC_DO_NOT_GRADE}
    assert top.pressing_recommendation in {"PRESS", "DO_NOT_PRESS"}
    assert abs(sum(top.grade_probabilities.values()) - 1.0) < 0.02
    assert top.grading_score >= 0
    assert top.expected_total_cost > 0
