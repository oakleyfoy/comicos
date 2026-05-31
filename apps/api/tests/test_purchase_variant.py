from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import ReleaseIssue, ReleaseSeries, User
from app.models.purchase_quantity import PurchaseQuantityRecommendation
from app.models.purchase_variant import PurchaseVariantRecommendation
from app.models.release_intelligence import ReleaseVariant
from app.models.recommendation_v2 import RecommendationRunV2, RecommendationScoreV2
from app.schemas.purchase_profile import PurchasePreferenceRead, PurchaseProfileRead
from app.schemas.purchase_profile import PurchaseProfileUpdate
from app.services.purchase_profiles import set_purchase_profile
from app.services.purchase_quantities import generate_purchase_quantities
from app.services.purchase_variant_classifier import classify_purchase_variant_type, parse_ratio_denominator
from app.services.purchase_variant_engine import evaluate_variant_recommendation
from app.services.purchase_variants import generate_purchase_variants
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


def _seed_issue(session: Session, *, owner_user_id: int) -> ReleaseIssue:
    series = ReleaseSeries(
        owner_user_id=owner_user_id,
        publisher="Marvel",
        series_name="Variant Test",
        series_type="ONGOING",
        status="ACTIVE",
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    issue = ReleaseIssue(
        owner_user_id=owner_user_id,
        release_uuid=f"pv-{owner_user_id}",
        series_id=int(series.id or 0),
        issue_number="1",
        title="Variant Test #1",
        release_status="SCHEDULED",
        release_date=date.today() + timedelta(days=14),
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)
    return issue


def _seed_v2_and_qty(
    session: Session,
    *,
    owner_user_id: int,
    issue: ReleaseIssue,
    tier: str = "MUST_BUY",
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
            total_score=90.0,
            recommendation_tier=tier,
            recommendation_type="NEW_OPPORTUNITY",
            confidence_score=0.88,
        )
    )
    session.commit()
    generate_purchase_quantities(session, owner_user_id=owner_user_id)


def _add_variant(
    session: Session,
    *,
    issue: ReleaseIssue,
    name: str,
    vtype: str = "COVER",
    ratio: int | None = None,
    incentive: bool = False,
) -> ReleaseVariant:
    row = ReleaseVariant(
        issue_id=int(issue.id or 0),
        variant_uuid=f"v-{issue.id}-{name}",
        variant_name=name,
        ratio_value=ratio,
        ratio_type="RATIO" if ratio else None,
        is_incentive_variant=incentive,
        variant_type=vtype,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def test_classifier_cover_a_and_ratio() -> None:
    cover = ReleaseVariant(
        issue_id=1,
        variant_uuid="a",
        variant_name="Cover A",
        variant_type="COVER",
        is_incentive_variant=False,
    )
    assert classify_purchase_variant_type(variant=cover)[0] == "COVER_A"
    ratio = ReleaseVariant(
        issue_id=1,
        variant_uuid="r",
        variant_name="1:100 Virgin",
        variant_type="RATIO",
        ratio_value=100,
        is_incentive_variant=False,
    )
    assert classify_purchase_variant_type(variant=ratio)[0] == "RATIO"
    assert parse_ratio_denominator(text="1:10 incentive", ratio_value=None) == 10


def test_cover_a_buy_when_quantity_positive() -> None:
    rec, conf, rationale = evaluate_variant_recommendation(
        variant_type="COVER_A",
        cover_label="Cover A",
        ratio_denominator=None,
        quantity_recommended=2,
        recommendation_tier="BUY",
        quantity_confidence=0.7,
        profile=_collector_profile(),
        preferences=_collector_prefs(),
    )
    assert rec == "BUY"
    assert conf > 0
    assert rationale


def test_open_order_watch_baseline() -> None:
    rec, _, _ = evaluate_variant_recommendation(
        variant_type="OPEN_ORDER",
        cover_label="Cover B",
        ratio_denominator=None,
        quantity_recommended=2,
        recommendation_tier="BUY",
        quantity_confidence=0.65,
        profile=_collector_profile(),
        preferences=_collector_prefs(),
    )
    assert rec == "WATCH"


def test_ratio_100_avoid_unless_elite() -> None:
    rec, _, _ = evaluate_variant_recommendation(
        variant_type="RATIO",
        cover_label="1:100",
        ratio_denominator=100,
        quantity_recommended=3,
        recommendation_tier="BUY",
        quantity_confidence=0.7,
        profile=_collector_profile(),
        preferences=_collector_prefs(),
    )
    assert rec == "AVOID"


def test_ratio_10_can_buy_on_strong_tier() -> None:
    rec, _, _ = evaluate_variant_recommendation(
        variant_type="RATIO",
        cover_label="1:10",
        ratio_denominator=10,
        quantity_recommended=3,
        recommendation_tier="MUST_BUY",
        quantity_confidence=0.85,
        profile=_collector_profile(),
        preferences=_collector_prefs(),
    )
    assert rec in {"BUY", "WATCH"}


def test_reader_avoids_open_order() -> None:
    reader = PurchaseProfileRead(
        id=1,
        owner_id=1,
        profile_type="READER",
        display_name="Reader",
        description="",
        is_active=True,
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )
    rec, _, _ = evaluate_variant_recommendation(
        variant_type="OPEN_ORDER",
        cover_label="Cover C",
        ratio_denominator=None,
        quantity_recommended=1,
        recommendation_tier="STRONG_BUY",
        quantity_confidence=0.8,
        profile=reader,
        preferences=_collector_prefs(),
    )
    assert rec == "AVOID"


def test_variant_hunter_tolerance(client: TestClient, session: Session) -> None:
    email = "pv-hunter@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    issue = _seed_issue(session, owner_user_id=owner_id)
    _add_variant(session, issue=issue, name="Cover B Open Order", vtype="OPEN_ORDER")
    _seed_v2_and_qty(session, owner_user_id=owner_id, issue=issue, tier="STRONG_BUY")
    set_purchase_profile(session, owner_user_id=owner_id, payload=PurchaseProfileUpdate(profile_type="VARIANT_HUNTER"))
    generate_purchase_variants(session, owner_user_id=owner_id)
    rows = session.exec(
        select(PurchaseVariantRecommendation).where(PurchaseVariantRecommendation.owner_user_id == owner_id)
    ).all()
    open_rows = [r for r in rows if r.variant_type == "OPEN_ORDER"]
    assert open_rows
    assert open_rows[0].recommendation == "BUY"


def test_generate_idempotent(client: TestClient, session: Session) -> None:
    email = "pv-idem@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    issue = _seed_issue(session, owner_user_id=owner_id)
    _add_variant(session, issue=issue, name="Cover A", vtype="COVER")
    _seed_v2_and_qty(session, owner_user_id=owner_id, issue=issue)
    first = generate_purchase_variants(session, owner_user_id=owner_id)
    assert first >= 1
    second = generate_purchase_variants(session, owner_user_id=owner_id)
    assert second == 0


def test_api_owner_isolation(client: TestClient, session: Session) -> None:
    token_a = register_and_login(client, "pv-a@example.com")
    token_b = register_and_login(client, "pv-b@example.com")
    owner_a = _owner_id(session, "pv-a@example.com")
    issue = _seed_issue(session, owner_user_id=owner_a)
    _seed_v2_and_qty(session, owner_user_id=owner_a, issue=issue)
    client.post("/api/v1/purchase-variants/generate", headers=auth_headers(token_a))
    list_a = client.get("/api/v1/purchase-variants", headers=auth_headers(token_a))
    list_b = client.get("/api/v1/purchase-variants", headers=auth_headers(token_b))
    assert len(list_a.json()["data"]["items"]) >= 1
    assert len(list_b.json()["data"]["items"]) == 0
