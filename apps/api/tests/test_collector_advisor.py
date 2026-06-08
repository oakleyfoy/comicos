"""P90-03 / P90-04 Collector Advisor tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.schemas.p90_collector_advisor import P90AdvisorSignalDiagnosticsRead
from app.services.advisor_priority_service import rank_advisor_actions
from app.services.advisor_proposal_dedupe import dedupe_proposals
from app.services.advisor_proposal_gather import gather_advisor_proposals
from app.services.advisor_status import (
    ADVISOR_STATUS_EMPTY_GATHER_FAILED,
    ADVISOR_STATUS_EMPTY_NO_COLLECTION,
    ADVISOR_STATUS_EMPTY_NO_SIGNALS,
    ADVISOR_STATUS_NO_SNAPSHOT,
    ADVISOR_STATUS_OK,
    resolve_advisor_dashboard_status,
)
from app.services.automation_engine_service import _Proposal
from app.services.collector_advisor_service import generate_collector_advisor_snapshot
from app.services.portfolio_impact_service import compute_portfolio_impact
from test_inventory import auth_headers, create_order, register_and_login


def test_advisor_priority_orders_by_score() -> None:
    actions = [
        {"category": "BUY", "alert_type": "BUY_OPPORTUNITY", "confidence": "LOW", "severity": "LOW", "profit_signal": 1.0},
        {"category": "SELL", "alert_type": "SELL_OPPORTUNITY", "confidence": "HIGH", "severity": "HIGH", "profit_signal": 30.0},
    ]
    ranked = rank_advisor_actions(actions, limit=2)
    assert ranked[0]["priority_score"] >= ranked[1]["priority_score"]


def test_portfolio_impact_sums() -> None:
    impact = compute_portfolio_impact(
        buy_actions=[{"potential_upside": 10.0}],
        sell_actions=[{"profit_potential": 25.0}],
        grade_actions=[{"value_increase": 5.0}],
    )
    assert impact["portfolio_impact_total"] == 40.0
    assert impact["estimated_profit"] == 25.0
    assert impact["estimated_savings"] == 10.0


def test_collector_advisor_dry_run(client: TestClient, session: Session) -> None:
    from app.models import User
    from sqlmodel import select

    register_and_login(client, "advisor-dry@example.com")
    user = session.exec(select(User).where(User.email == "advisor-dry@example.com")).one()
    summary = generate_collector_advisor_snapshot(session, owner_user_id=int(user.id), dry_run=True)
    assert "buy_actions" in summary
    assert summary["dry_run"] is True


def test_collector_advisor_get_no_snapshot(client: TestClient) -> None:
    token = register_and_login(client, "advisor-no-snap@example.com")
    resp = client.get("/api/v1/collector-advisor", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == ADVISOR_STATUS_NO_SNAPSHOT
    assert data["plan"] is None
    assert "Generate your first Advisor plan" in data["message"]


def test_collector_advisor_generate_endpoint(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "advisor-generate@example.com")
    resp = client.post("/api/v1/collector-advisor/generate", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == ADVISOR_STATUS_EMPTY_NO_COLLECTION
    assert data["plan"] is not None
    assert data["plan"]["buy_actions"] == []
    assert data["message"] == "Import comics to unlock personalized recommendations."


def test_collector_advisor_generate_empty_no_signals(client: TestClient, session: Session) -> None:
    from app.models import User
    from sqlmodel import select

    token = register_and_login(client, "advisor-inv@example.com")
    create_order(client, token)
    user = session.exec(select(User).where(User.email == "advisor-inv@example.com")).one()
    assert user.id is not None
    resp = client.post("/api/v1/collector-advisor/generate", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == ADVISOR_STATUS_EMPTY_NO_SIGNALS
    assert "no ranked actions need attention" in data["message"]


def test_collector_advisor_generate_survives_gather_failure(client: TestClient, monkeypatch) -> None:
    import app.services.collector_advisor_service as advisor_service

    token = register_and_login(client, "advisor-gather-fail@example.com")

    def _all_fail(session, *, owner_user_id: int):
        from app.services.advisor_proposal_gather import ADVISOR_GATHER_SUBSYSTEMS, AdvisorGatherResult

        return AdvisorGatherResult(
            proposals=[],
            succeeded_subsystems=[],
            failed_subsystems=[name for name, _ in ADVISOR_GATHER_SUBSYSTEMS],
            errors=[{"subsystem": name, "message": "simulated"} for name, _ in ADVISOR_GATHER_SUBSYSTEMS],
        )

    monkeypatch.setattr(advisor_service, "gather_advisor_proposals_with_result", _all_fail)
    resp = client.post("/api/v1/collector-advisor/generate", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == ADVISOR_STATUS_EMPTY_GATHER_FAILED
    assert data["plan"] is not None
    assert data["plan"]["total_actions"] == 0


def test_advisor_partial_subsystem_failure_still_ok(client: TestClient, monkeypatch) -> None:
    import app.services.collector_advisor_service as advisor_service
    from app.services.automation_engine_service import _Proposal

    token = register_and_login(client, "advisor-partial@example.com")
    proposal = _Proposal(
        alert_type="SELL_OPPORTUNITY",
        severity="MEDIUM",
        title="Sell: Test",
        summary="x",
        source_system="P89",
        entity_type="sell_candidate",
        entity_id=1,
        confidence="MEDIUM",
        reason="Test",
        action_route="/sell",
        profit_signal=10.0,
    )

    real_gather = advisor_service.gather_advisor_proposals_with_result

    def _partial(session, *, owner_user_id: int):
        result = real_gather(session, owner_user_id=owner_user_id)
        result.failed_subsystems.append("marketplace_opportunities")
        result.succeeded_subsystems.append("sell_candidates")
        result.proposals = [proposal]
        return result

    monkeypatch.setattr(advisor_service, "gather_advisor_proposals_with_result", _partial)
    resp = client.post("/api/v1/collector-advisor/generate", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] != ADVISOR_STATUS_EMPTY_GATHER_FAILED


def test_collector_advisor_generate_never_500_on_persist_failure(client: TestClient, monkeypatch) -> None:
    import app.services.collector_advisor_service as advisor_service

    token = register_and_login(client, "advisor-persist-fail@example.com")

    def _boom(*_args, **_kwargs):
        raise RuntimeError("persist blew up")

    monkeypatch.setattr(advisor_service, "generate_collector_advisor_snapshot", _boom)
    resp = client.post("/api/v1/collector-advisor/generate", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == ADVISOR_STATUS_EMPTY_GATHER_FAILED


def test_collector_advisor_persist_and_api(client: TestClient, session: Session) -> None:
    from app.models import User
    from sqlmodel import select

    token = register_and_login(client, "advisor-api@example.com")
    user = session.exec(select(User).where(User.email == "advisor-api@example.com")).one()
    generate_collector_advisor_snapshot(session, owner_user_id=int(user.id), dry_run=False)
    session.commit()
    resp = client.get("/api/v1/collector-advisor", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] in {ADVISOR_STATUS_OK, ADVISOR_STATUS_EMPTY_NO_COLLECTION, ADVISOR_STATUS_EMPTY_NO_SIGNALS}
    if data["plan"]:
        assert "buy_actions" in data["plan"]
        assert "portfolio_impact" in data["plan"]


def test_advisor_includes_p90_collector_alert(client: TestClient, session: Session) -> None:
    from app.models import User
    from app.models.p90_collector_alert import P90CollectorAlert
    from sqlmodel import select

    register_and_login(client, "p90-alert@example.com")
    user = session.exec(select(User).where(User.email == "p90-alert@example.com")).one()
    uid = int(user.id)
    session.add(
        P90CollectorAlert(
            owner_user_id=uid,
            alert_type="BUY_OPPORTUNITY",
            severity="HIGH",
            title="Alert buy: Test Series #1",
            summary="Cached alert",
            source_system="P90",
            entity_type="series",
            entity_id=42,
            status="NEW",
            reason="Test",
            action_route="/buy-opportunities",
        )
    )
    session.commit()
    proposals = gather_advisor_proposals(session, owner_user_id=uid)
    assert any(p.entity_id == 42 and p.alert_type == "BUY_OPPORTUNITY" for p in proposals)


def test_advisor_deduplicates_proposals() -> None:
    base = _Proposal(
        alert_type="BUY_OPPORTUNITY",
        severity="HIGH",
        title="Buy: Same Book",
        summary="x",
        source_system="P88",
        entity_type="marketplace_acquisition",
        entity_id=7,
        confidence="HIGH",
        reason="Test",
        action_route="/buy-opportunities",
    )
    dup = _Proposal(
        alert_type="BUY_OPPORTUNITY",
        severity="MEDIUM",
        title="Buy: Same Book duplicate title",
        summary="y",
        source_system="P88",
        entity_type="marketplace_acquisition",
        entity_id=7,
        confidence="MEDIUM",
        reason="Test",
        action_route="/buy-opportunities",
    )
    out = dedupe_proposals([base, dup])
    assert len(out) == 1


def test_advisor_wider_buy_recommendations(client: TestClient, session: Session) -> None:
    from app.models import User
    from app.models.p82_p84_collector_expansion import MarketplaceAcquisitionOpportunity
    from sqlmodel import select

    register_and_login(client, "spec-buy@example.com")
    user = session.exec(select(User).where(User.email == "spec-buy@example.com")).one()
    uid = int(user.id)
    session.add(
        MarketplaceAcquisitionOpportunity(
            owner_user_id=uid,
            marketplace="EBAY",
            external_listing_id="spec-1",
            title="Spec Title #1",
            status="ACTIVE",
            recommendation="SPEC_BUY",
            opportunity_score=80.0,
            discount_to_fmv=12.0,
        )
    )
    session.commit()
    proposals = gather_advisor_proposals(session, owner_user_id=uid)
    assert any(p.entity_type == "marketplace_acquisition" for p in proposals)


def test_advisor_listing_draft_review_action(client: TestClient, session: Session) -> None:
    from app.models import User
    from app.models.asset_ledger import InventoryCopy
    from app.models.p89_listing_draft import P89ListingDraft
    from sqlmodel import select

    token = register_and_login(client, "draft-advisor@example.com")
    create_order(client, token)
    user = session.exec(select(User).where(User.email == "draft-advisor@example.com")).one()
    uid = int(user.id)
    copy = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == uid)).one()
    session.add(
        P89ListingDraft(
            owner_user_id=uid,
            inventory_copy_id=int(copy.id),
            title="Draft listing",
            status="DRAFT",
        )
    )
    session.commit()
    proposals = gather_advisor_proposals(session, owner_user_id=uid)
    assert any(p.entity_type == "listing_draft" for p in proposals)


def test_resolve_advisor_status_rules() -> None:
    empty_diag = P90AdvisorSignalDiagnosticsRead()
    assert (
        resolve_advisor_dashboard_status(
            has_snapshot=False,
            generation_status="",
            total_actions=0,
            diagnostics=empty_diag,
        )
        == ADVISOR_STATUS_NO_SNAPSHOT
    )
    assert (
        resolve_advisor_dashboard_status(
            has_snapshot=True,
            generation_status="GATHER_FAILED",
            total_actions=0,
            diagnostics=empty_diag,
        )
        == ADVISOR_STATUS_EMPTY_GATHER_FAILED
    )
    assert (
        resolve_advisor_dashboard_status(
            has_snapshot=True,
            generation_status="OK",
            total_actions=3,
            diagnostics=empty_diag,
        )
        == ADVISOR_STATUS_OK
    )
    assert (
        resolve_advisor_dashboard_status(
            has_snapshot=True,
            generation_status="OK",
            total_actions=0,
            diagnostics=empty_diag,
        )
        == ADVISOR_STATUS_EMPTY_NO_COLLECTION
    )
    with_inventory = P90AdvisorSignalDiagnosticsRead(inventory_count=5)
    assert (
        resolve_advisor_dashboard_status(
            has_snapshot=True,
            generation_status="OK",
            total_actions=0,
            diagnostics=with_inventory,
        )
        == ADVISOR_STATUS_EMPTY_NO_SIGNALS
    )
