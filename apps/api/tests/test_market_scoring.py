from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import (
    AcquisitionPrioritySnapshot,
    ComicIssue,
    ComicTitle,
    ConcentrationRiskSnapshot,
    InventoryCopy,
    MarketAcquisitionCandidate,
    MarketAcquisitionNormalizedCandidate,
    MarketAcquisitionScore,
    MarketAcquisitionScoreEvidence,
    MarketAcquisitionScoreHistory,
    MarketAcquisitionScoreSnapshot,
    Order,
    OrderItem,
    PortfolioExposureSnapshot,
    PortfolioLiquiditySnapshot,
    Publisher,
    User,
    Variant,
)
from app.services import market_scoring as scoring_svc
from test_inventory import auth_headers, register_and_login


def _ingestion_payload() -> dict[str, object]:
    return {
        "batch_source_type": "csv_import",
        "batch_file_name": "score-batch.csv",
        "records": [
            {
                "title": "The Amazing Spider-Man",
                "publisher": "Marvel Comics",
                "issue_number": "#12",
                "variant": "Cover A",
                "condition_raw": "VF/NM",
                "asking_price": "25.99",
                "currency": "USD",
                "external_fmv_estimate": "40.00",
            },
            {
                "title": "Unknown Indie Book",
                "publisher": "Small Press",
                "issue_number": "1",
                "variant": "Mystery",
                "condition_raw": "GOOD",
                "asking_price": "8.50",
                "currency": "USD",
                "external_fmv_estimate": "9.00",
            },
        ],
    }


def _seed_issue_and_context(session: Session, *, owner_user_id: int) -> int:
    publisher = Publisher(name="Marvel")
    session.add(publisher)
    session.flush()

    title = ComicTitle(publisher_id=int(publisher.id), name="Spider-Man")
    session.add(title)
    session.flush()

    issue = ComicIssue(comic_title_id=int(title.id), issue_number="12")
    session.add(issue)
    session.flush()

    variant = Variant(comic_issue_id=int(issue.id), cover_name="Cover A")
    session.add(variant)
    session.flush()

    order = Order(
        user_id=owner_user_id,
        retailer="Seed Shop",
        order_date=date(2026, 5, 26),
        source_type="manual",
        shipping_amount=Decimal("0.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("15.00"),
    )
    session.add(order)
    session.flush()

    order_item = OrderItem(
        order_id=int(order.id),
        variant_id=int(variant.id),
        quantity=1,
        raw_item_price=Decimal("15.00"),
        allocated_shipping=Decimal("0.00"),
        allocated_tax=Decimal("0.00"),
        all_in_unit_cost=Decimal("15.00"),
    )
    session.add(order_item)
    session.flush()

    session.add(
        InventoryCopy(
            user_id=owner_user_id,
            order_item_id=int(order_item.id),
            variant_id=int(variant.id),
            copy_number=1,
            acquisition_cost=Decimal("15.00"),
            release_status="released",
            order_status="received",
            grade_status="raw",
            hold_status="hold",
            current_fmv=Decimal("30.00"),
        )
    )

    title_key = scoring_svc._slug("Spider-Man::12")
    publisher_key = scoring_svc._slug("Marvel")

    session.add(
        PortfolioLiquiditySnapshot(
            owner_user_id=owner_user_id,
            portfolio_id=None,
            generation_scope_key="ALL_INVENTORY",
            replay_key="seed-liquidity",
            total_portfolio_fmv=Decimal("30.00"),
            liquid_portfolio_value=Decimal("20.00"),
            illiquid_portfolio_value=Decimal("10.00"),
            liquidity_weighted_value=Decimal("22.00"),
            liquidity_efficiency_score=Decimal("72.00"),
            liquidity_drag_score=Decimal("18.00"),
            concentration_risk_score=Decimal("25.00"),
            dead_capital_estimate=Decimal("10.00"),
            liquidity_balance_status="WATCH",
            high_liquidity_count=1,
            medium_liquidity_count=0,
            low_liquidity_count=0,
            illiquid_count=0,
            checksum="liq-seed-checksum",
            snapshot_date=date(2026, 5, 26),
        )
    )
    session.add(
        PortfolioExposureSnapshot(
            owner_user_id=owner_user_id,
            portfolio_id=None,
            generation_scope_key="ALL_INVENTORY",
            replay_key="seed-exp-publisher",
            generation_batch_checksum="exp-seed",
            exposure_type="publisher",
            exposure_key=publisher_key,
            item_count=1,
            total_fmv_amount=Decimal("30.00"),
            total_cost_basis_amount=Decimal("15.00"),
            total_realized_sales_amount=Decimal("0.00"),
            percentage_of_portfolio_value=Decimal("100.00"),
            percentage_of_portfolio_count=Decimal("100.00"),
            exposure_status="OVEREXPOSED",
            checksum="exp-publisher",
            snapshot_date=date(2026, 5, 26),
        )
    )
    session.add(
        PortfolioExposureSnapshot(
            owner_user_id=owner_user_id,
            portfolio_id=None,
            generation_scope_key="ALL_INVENTORY",
            replay_key="seed-exp-title",
            generation_batch_checksum="exp-seed",
            exposure_type="title",
            exposure_key=title_key,
            item_count=1,
            total_fmv_amount=Decimal("30.00"),
            total_cost_basis_amount=Decimal("15.00"),
            total_realized_sales_amount=Decimal("0.00"),
            percentage_of_portfolio_value=Decimal("100.00"),
            percentage_of_portfolio_count=Decimal("100.00"),
            exposure_status="WATCH",
            checksum="exp-title",
            snapshot_date=date(2026, 5, 26),
        )
    )
    session.add(
        ConcentrationRiskSnapshot(
            owner_user_id=owner_user_id,
            portfolio_id=None,
            concentration_type="publisher",
            concentration_key=publisher_key,
            replay_key="seed-conc-publisher",
            total_item_count=1,
            total_fmv_amount=Decimal("30.00"),
            percentage_of_portfolio=Decimal("100.00"),
            concentration_score=Decimal("72.00"),
            liquidity_weighted_concentration=Decimal("55.00"),
            exposure_status="CRITICAL",
            diversification_score=Decimal("10.00"),
            checksum="conc-publisher",
            snapshot_date=date(2026, 5, 26),
        )
    )
    session.add(
        ConcentrationRiskSnapshot(
            owner_user_id=owner_user_id,
            portfolio_id=None,
            concentration_type="title",
            concentration_key=title_key,
            replay_key="seed-conc-title",
            total_item_count=1,
            total_fmv_amount=Decimal("30.00"),
            percentage_of_portfolio=Decimal("100.00"),
            concentration_score=Decimal("58.00"),
            liquidity_weighted_concentration=Decimal("48.00"),
            exposure_status="OVEREXPOSED",
            diversification_score=Decimal("22.00"),
            checksum="conc-title",
            snapshot_date=date(2026, 5, 26),
        )
    )
    session.add(
        AcquisitionPrioritySnapshot(
            owner_user_id=owner_user_id,
            canonical_comic_issue_id=int(issue.id),
            acquisition_category="PORTFOLIO_GAP",
            acquisition_priority="HIGH",
            replay_key="seed-acq",
            portfolio_impact_score=Decimal("82.00"),
            diversification_impact=Decimal("68.00"),
            liquidity_impact=Decimal("66.00"),
            grading_upside_score=Decimal("74.00"),
            duplication_risk=Decimal("40.00"),
            concentration_reduction_score=Decimal("48.00"),
            estimated_capital_efficiency=Decimal("64.00"),
            recommendation_strength="STRONG",
            confidence_level="HIGH",
            risk_level="MEDIUM",
            rationale_summary="Seed deterministic context",
            warning_flags_json=[],
            checksum="acq-priority-seed",
            snapshot_date=date(2026, 5, 26),
        )
    )
    session.commit()
    return int(issue.id)


def _run_ingestion_and_normalization(client: TestClient, token: str) -> None:
    ingest = client.post("/market-ingestion/batch", headers=auth_headers(token), json=_ingestion_payload())
    assert ingest.status_code == 201, ingest.text
    batch_id = int(ingest.json()["id"])
    run = client.post(
        "/market-normalization/run",
        headers=auth_headers(token),
        json={"ingestion_batch_id": batch_id},
    )
    assert run.status_code in {200, 201}, run.text


def test_market_scoring_is_deterministic_replay_safe_and_non_mutating(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "ma-score-deterministic@example.com")
    owner_user_id = int(session.exec(select(User.id).where(User.email == "ma-score-deterministic@example.com")).one())
    _run_ingestion_and_normalization(client, token)
    _seed_issue_and_context(session, owner_user_id=owner_user_id)

    norm_count_before = len(session.exec(select(MarketAcquisitionNormalizedCandidate)).all())
    ingest_count_before = len(session.exec(select(MarketAcquisitionCandidate)).all())

    first = client.post("/market-scoring/run", headers=auth_headers(token), json={})
    assert first.status_code == 200, first.text
    payload_1 = first.json()
    assert payload_1["replayed"] is False
    assert payload_1["total_scores"] == 2

    second = client.post("/market-scoring/run", headers=auth_headers(token), json={})
    assert second.status_code == 200, second.text
    payload_2 = second.json()
    assert payload_2["replayed"] is True
    assert payload_1["snapshot"]["id"] == payload_2["snapshot"]["id"]
    assert payload_1["snapshot"]["checksum"] == payload_2["snapshot"]["checksum"]

    scores = session.exec(select(MarketAcquisitionScore)).all()
    evidence = session.exec(select(MarketAcquisitionScoreEvidence)).all()
    history = session.exec(select(MarketAcquisitionScoreHistory)).all()
    snapshots = session.exec(select(MarketAcquisitionScoreSnapshot)).all()
    assert len(scores) == 2
    assert len(evidence) == 10
    assert len(history) == 2
    assert len(snapshots) == 1
    assert len(session.exec(select(MarketAcquisitionNormalizedCandidate)).all()) == norm_count_before
    assert len(session.exec(select(MarketAcquisitionCandidate)).all()) == ingest_count_before


def test_market_scoring_label_thresholds() -> None:
    assert scoring_svc._recommendation_label(Decimal("85.00")) == "STRONG_BUY"
    assert scoring_svc._recommendation_label(Decimal("70.00")) == "BUY"
    assert scoring_svc._recommendation_label(Decimal("50.00")) == "WATCH"
    assert scoring_svc._recommendation_label(Decimal("49.99")) == "IGNORE"


def test_market_scoring_owner_ops_visibility_and_detail(
    client: TestClient,
    session: Session,
) -> None:
    token_a = register_and_login(client, "ma-score-owner-a@example.com")
    token_b = register_and_login(client, "ma-score-owner-b@example.com")
    owner_a = int(session.exec(select(User.id).where(User.email == "ma-score-owner-a@example.com")).one())
    _run_ingestion_and_normalization(client, token_a)
    _seed_issue_and_context(session, owner_user_id=owner_a)

    run = client.post("/market-scoring/run", headers=auth_headers(token_a), json={})
    assert run.status_code == 200, run.text

    scores = client.get("/market-scoring/scores", headers=auth_headers(token_a))
    assert scores.status_code == 200, scores.text
    score_id = int(scores.json()["items"][0]["id"])

    owner_detail = client.get(f"/market-scoring/scores/{score_id}", headers=auth_headers(token_a))
    assert owner_detail.status_code == 200, owner_detail.text
    assert len(owner_detail.json()["evidence"]) == 5

    other_owner_detail = client.get(f"/market-scoring/scores/{score_id}", headers=auth_headers(token_b))
    assert other_owner_detail.status_code == 404, other_owner_detail.text

    ops_scores = client.get(f"/ops/market-scoring/scores?owner_user_id={owner_a}", headers=auth_headers(token_a))
    assert ops_scores.status_code == 200, ops_scores.text
    assert any(int(row["id"]) == score_id for row in ops_scores.json()["items"])

    ops_detail = client.get(f"/ops/market-scoring/scores/{score_id}", headers=auth_headers(token_a))
    assert ops_detail.status_code == 200, ops_detail.text
    assert ops_detail.json()["score"]["owner_user_id"] == owner_a
