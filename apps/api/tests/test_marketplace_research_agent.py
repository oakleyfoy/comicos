from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from agent_security_test_utils import grant_agent_execute
from app.models import (
    AgentDefinition,
    DraftImport,
    InventoryCopy,
    InventoryFmvSnapshot,
    MarketFmvSnapshot,
    MarketTrendSnapshot,
    User,
)
from app.services.agent_registry import enable_agent
from app.services.agent_seed import seed_foundational_agents
from app.services.marketplace_research_agent import run_marketplace_research_agent
from test_imports import seed_import
from test_inventory import create_order, register_and_login


def _enabled_marketplace_agent(session: Session) -> None:
    seed_foundational_agents(session)
    row = session.exec(select(AgentDefinition).where(AgentDefinition.code == "marketplace_research_agent")).first()
    assert row is not None and row.id is not None
    enable_agent(session, agent_id=int(row.id))
    grant_agent_execute(session, agent_id=int(row.id))


def _owner(session: Session, email: str) -> User:
    row = session.exec(select(User).where(User.email == email)).one()
    assert row.id is not None
    return row


def _seed_marketplace_inventory(client: TestClient, session: Session, *, email: str) -> User:
    token = register_and_login(client, email)
    create_order(
        client,
        token,
        order_date="2026-05-01",
        items=[
            {
                "title": "Invincible",
                "publisher": "Image",
                "issue_number": "1",
                "release_year": 2024,
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 12.00,
            },
            {
                "title": "Saga",
                "publisher": "Image",
                "issue_number": "1",
                "release_year": 2024,
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 8.00,
            },
        ],
    )
    user = _owner(session, email)
    copies = session.exec(
        select(InventoryCopy).where(InventoryCopy.user_id == user.id).order_by(InventoryCopy.id.asc())
    ).all()
    assert len(copies) == 2

    first = copies[0]
    second = copies[1]
    first.metadata_identity_key = "Image|Invincible|1|Cover A"
    first.current_fmv = Decimal("28.00")
    first.received_at = datetime.now(timezone.utc) - timedelta(days=120)
    first.order_status = "received"
    second.metadata_identity_key = "Image|Saga|1|Cover A"
    second.current_fmv = None
    second.order_status = "received"
    session.add(first)
    session.add(second)
    session.commit()
    session.refresh(first)
    session.refresh(second)

    session.add(
        InventoryFmvSnapshot(
            inventory_copy_id=int(first.id or 0),
            previous_fmv=Decimal("24.00"),
            new_fmv=Decimal("28.00"),
            changed_at=datetime.now(timezone.utc) - timedelta(days=7),
            source="ops",
        )
    )
    session.add(
        MarketFmvSnapshot(
            canonical_issue_id=None,
            metadata_identity_key=first.metadata_identity_key,
            snapshot_scope="raw",
            grading_company=None,
            normalized_grade=None,
            currency_code="USD",
            snapshot_date=date(2026, 5, 20),
            comp_count=4,
            valuation_method="weighted_recent_sales",
            estimated_fmv=Decimal("30.00"),
            confidence_bucket="high",
            liquidity_bucket="medium",
            volatility_bucket="moderate",
            stale_data=False,
            evidence_json={"comp_ids": [1, 2, 3, 4]},
        )
    )
    session.add(
        MarketTrendSnapshot(
            canonical_issue_id=None,
            metadata_identity_key=first.metadata_identity_key,
            snapshot_scope="raw",
            grading_company=None,
            normalized_grade=None,
            currency_code="USD",
            trend_window="30d",
            trend_direction="up",
            trend_strength="high",
            liquidity_direction="up",
            comp_count=4,
            percent_change=Decimal("18.50"),
            volatility_score=0.42,
            stale_data=False,
            evidence_json={"market_fmv_snapshot_id": 1},
        )
    )
    session.commit()

    seed_import(
        session,
        user_id=int(user.id),
        raw_text="Draft import awaiting review",
        status="draft",
        created_at=datetime.now(timezone.utc) - timedelta(days=2),
        updated_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    return user


def _inventory_state(session: Session, *, owner_user_id: int) -> list[tuple]:
    rows = session.exec(
        select(InventoryCopy)
        .where(InventoryCopy.user_id == owner_user_id)
        .order_by(InventoryCopy.id.asc())
    ).all()
    return [
        (
            int(row.id or 0),
            str(row.current_fmv) if row.current_fmv is not None else None,
            row.hold_status,
            row.order_status,
            row.metadata_identity_key,
        )
        for row in rows
    ]


def _normalized_projection(detail) -> list[tuple]:
    projection: list[tuple] = []
    for finding in detail.findings:
        evidence_projection = [
            (evidence.evidence_type, evidence.source_name, evidence.source_payload_json)
            for evidence in finding.evidence
        ]
        projection.append(
            (
                finding.finding_code,
                finding.finding_type,
                finding.title,
                finding.recommendation_json,
                evidence_projection,
            )
        )
    return projection


def test_marketplace_research_agent_produces_deterministic_read_only_findings(
    client: TestClient,
    session: Session,
) -> None:
    _enabled_marketplace_agent(session)
    user = _seed_marketplace_inventory(client, session, email="marketplace-research-owner@example.com")

    before_inventory_state = _inventory_state(session, owner_user_id=int(user.id or 0))
    before_counts = {
        "inventory": len(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == user.id)).all()),
        "inventory_fmv": len(session.exec(select(InventoryFmvSnapshot)).all()),
        "market_fmv": len(session.exec(select(MarketFmvSnapshot)).all()),
        "market_trend": len(session.exec(select(MarketTrendSnapshot)).all()),
        "draft_import": len(session.exec(select(DraftImport).where(DraftImport.user_id == user.id)).all()),
    }

    first = run_marketplace_research_agent(session, current_user=user)
    second = run_marketplace_research_agent(session, current_user=user)

    assert first.snapshot.agent_execution_id != second.snapshot.agent_execution_id
    assert first.snapshot.status == "COMPLETED"
    assert second.snapshot.status == "COMPLETED"
    assert _normalized_projection(first) == _normalized_projection(second)
    assert {row.finding_type for row in first.findings} >= {
        "possible_underpriced_item",
        "stale_inventory_candidate",
        "grading_candidate",
        "high_interest_series",
        "marketplace_research_needed",
    }

    after_inventory_state = _inventory_state(session, owner_user_id=int(user.id or 0))
    after_counts = {
        "inventory": len(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == user.id)).all()),
        "inventory_fmv": len(session.exec(select(InventoryFmvSnapshot)).all()),
        "market_fmv": len(session.exec(select(MarketFmvSnapshot)).all()),
        "market_trend": len(session.exec(select(MarketTrendSnapshot)).all()),
        "draft_import": len(session.exec(select(DraftImport).where(DraftImport.user_id == user.id)).all()),
    }
    assert before_inventory_state == after_inventory_state
    assert before_counts == after_counts
