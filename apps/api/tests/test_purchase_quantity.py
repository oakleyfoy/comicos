from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import ReleaseIssue, ReleaseSeries, User
from app.models.purchase_quantity import PurchaseQuantityRecommendation
from app.models.recommendation_v2 import RecommendationRunV2, RecommendationScoreV2
from app.schemas.purchase_profile import PurchasePreferenceRead, PurchaseProfileRead
from app.services.purchase_profiles import set_purchase_profile
from app.schemas.purchase_profile import PurchaseProfileUpdate
from app.services.purchase_quantity_engine import (
    ALLOWED_QUANTITIES,
    TIER_QUANTITY_BOUNDS,
    compute_quantity_bias,
    compute_quantity_recommendation,
    pick_quantity_for_tier,
)
from app.services.purchase_quantities import generate_purchase_quantities
from test_inventory import auth_headers, register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def _collector_profile() -> PurchaseProfileRead:
    return PurchaseProfileRead(
        id=1,
        owner_id=1,
        profile_type="COLLECTOR",
        display_name="Collector",
        description="",
        is_active=True,
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )


def _collector_prefs() -> PurchasePreferenceRead:
    return PurchasePreferenceRead(
        id=1,
        owner_id=1,
        preferred_copy_count=1,
        risk_tolerance=0.5,
        variant_interest=0.5,
        grading_interest=0.5,
        completionist_score=0.5,
        speculation_score=0.5,
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )


def _seed_issue(session: Session, *, owner_user_id: int, publisher: str = "Marvel") -> ReleaseIssue:
    series = ReleaseSeries(
        owner_user_id=owner_user_id,
        publisher=publisher,
        series_name="Test Series",
        series_type="ONGOING",
        status="ACTIVE",
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    issue = ReleaseIssue(
        owner_user_id=owner_user_id,
        release_uuid=f"pq-{owner_user_id}-{publisher}",
        series_id=int(series.id or 0),
        issue_number="1",
        title="Test #1",
        release_status="SCHEDULED",
        release_date=date.today() + timedelta(days=21),
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)
    return issue


def _seed_v2(
    session: Session,
    *,
    owner_user_id: int,
    issue: ReleaseIssue,
    tier: str,
    confidence: float = 0.75,
) -> None:
    run = RecommendationRunV2(owner_user_id=owner_user_id, status="COMPLETED")
    session.add(run)
    session.commit()
    session.refresh(run)
    session.add(
        RecommendationScoreV2(
            owner_user_id=owner_user_id,
            recommendation_run_id=int(run.id or 0),
            release_issue_id=int(issue.id or 0),
            total_score=80.0,
            recommendation_tier=tier,
            recommendation_type="NEW_OPPORTUNITY",
            confidence_score=confidence,
        )
    )
    session.commit()


def test_tier_quantity_bounds_respect_allowed_set() -> None:
    for tier, (lo, hi) in TIER_QUANTITY_BOUNDS.items():
        for bias in (0.0, 0.25, 0.5, 0.75, 1.0):
            q = pick_quantity_for_tier(recommendation_tier=tier, bias=bias)
            assert q in ALLOWED_QUANTITIES
            assert lo <= q <= hi


def test_pass_and_watch_quantities() -> None:
    assert pick_quantity_for_tier(recommendation_tier="PASS", bias=1.0) == 0
    assert pick_quantity_for_tier(recommendation_tier="WATCH", bias=0.0) == 1


def test_profile_influence_investor_vs_reader_must_buy() -> None:
    investor_bias = compute_quantity_bias(
        profile_type="INVESTOR",
        risk_tolerance=0.65,
        speculation_score=0.85,
        grading_interest=0.75,
        recommendation_tier="MUST_BUY",
    )
    reader_bias = compute_quantity_bias(
        profile_type="READER",
        risk_tolerance=0.35,
        speculation_score=0.20,
        grading_interest=0.25,
        recommendation_tier="MUST_BUY",
    )
    assert investor_bias > reader_bias
    inv_q = pick_quantity_for_tier(recommendation_tier="MUST_BUY", bias=investor_bias)
    read_q = pick_quantity_for_tier(recommendation_tier="MUST_BUY", bias=reader_bias)
    assert inv_q >= read_q
    assert inv_q in {3, 5}


def test_confidence_and_rationale_present() -> None:
    result = compute_quantity_recommendation(
        release_id=99,
        recommendation_tier="STRONG_BUY",
        v2_confidence=0.82,
        profile=_collector_profile(),
        preferences=_collector_prefs(),
        pull_decision="CONTINUE_RUN",
        pull_confidence=0.77,
        series_name="Test Series",
    )
    assert 0.0 <= result.confidence_score <= 1.0
    assert result.rationale
    assert result.quantity_recommended in {2, 3}


def test_generate_idempotent(client: TestClient, session: Session) -> None:
    email = "pq-idem@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    issue = _seed_issue(session, owner_user_id=owner_id)
    _seed_v2(session, owner_user_id=owner_id, issue=issue, tier="MUST_BUY")
    first = generate_purchase_quantities(session, owner_user_id=owner_id)
    assert first == 1
    second = generate_purchase_quantities(session, owner_user_id=owner_id)
    assert second == 0
    rows = session.exec(
        select(PurchaseQuantityRecommendation).where(PurchaseQuantityRecommendation.owner_user_id == owner_id)
    ).all()
    assert len(rows) == 1


def test_profile_switch_changes_quantity(client: TestClient, session: Session) -> None:
    email = "pq-profile@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    issue = _seed_issue(session, owner_user_id=owner_id)
    _seed_v2(session, owner_user_id=owner_id, issue=issue, tier="MUST_BUY", confidence=0.9)

    set_purchase_profile(session, owner_user_id=owner_id, payload=PurchaseProfileUpdate(profile_type="INVESTOR"))
    generate_purchase_quantities(session, owner_user_id=owner_id)
    inv_row = session.exec(
        select(PurchaseQuantityRecommendation).where(PurchaseQuantityRecommendation.owner_user_id == owner_id)
    ).one()
    inv_qty = inv_row.quantity_recommended

    set_purchase_profile(session, owner_user_id=owner_id, payload=PurchaseProfileUpdate(profile_type="READER"))
    generate_purchase_quantities(session, owner_user_id=owner_id)
    rows = session.exec(
        select(PurchaseQuantityRecommendation)
        .where(PurchaseQuantityRecommendation.owner_user_id == owner_id)
        .order_by(PurchaseQuantityRecommendation.id.desc())
    ).all()
    assert len(rows) == 2
    read_qty = rows[0].quantity_recommended
    assert read_qty <= inv_qty


def test_api_owner_isolation(client: TestClient, session: Session) -> None:
    token_a = register_and_login(client, "pq-a@example.com")
    token_b = register_and_login(client, "pq-b@example.com")
    owner_a = _owner_id(session, "pq-a@example.com")
    issue = _seed_issue(session, owner_user_id=owner_a)
    _seed_v2(session, owner_user_id=owner_a, issue=issue, tier="BUY")
    client.post("/api/v1/purchase-quantities/generate", headers=auth_headers(token_a))
    list_a = client.get("/api/v1/purchase-quantities", headers=auth_headers(token_a))
    list_b = client.get("/api/v1/purchase-quantities", headers=auth_headers(token_b))
    assert list_a.status_code == 200
    assert len(list_a.json()["data"]["items"]) == 1
    assert len(list_b.json()["data"]["items"]) == 0


def test_api_get_by_id(client: TestClient, session: Session) -> None:
    email = "pq-get@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    issue = _seed_issue(session, owner_user_id=owner_id)
    _seed_v2(session, owner_user_id=owner_id, issue=issue, tier="WATCH")
    client.post("/api/v1/purchase-quantities/generate", headers=auth_headers(token))
    row = session.exec(select(PurchaseQuantityRecommendation).where(PurchaseQuantityRecommendation.owner_user_id == owner_id)).one()
    resp = client.get(f"/api/v1/purchase-quantities/{row.id}", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["data"]["quantity_recommended"] == 1
