from __future__ import annotations

from datetime import date, timedelta

from sqlmodel import Session, func, select

from app.models import (
    InventoryCopy,
    Order,
    ReleaseIssue,
    ReleaseSeries,
    RetailerAccount,
    RetailerOrderSnapshot,
    User,
)
from app.models.recommendation_v2 import (
    RecommendationRunV2,
    RecommendationScoreComponentV2,
    RecommendationScoreV2,
)
from app.services.user_collection_reset import reset_user_collection_data
from test_inventory import create_order, register_and_login


def _seed_retailer_account(session: Session, *, user_id: int) -> RetailerAccount:
    account = RetailerAccount(
        owner_user_id=user_id,
        retailer="midtown",
        display_name="Midtown Comics",
        username="reset-test@example.com",
        encrypted_password="enc",
        credential_version=1,
        status="connected",
        sync_enabled=True,
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


def _seed_recommendation_score_with_component(session: Session, *, owner_user_id: int, tag: str) -> None:
    series = ReleaseSeries(
        owner_user_id=owner_user_id,
        publisher="DC",
        series_name=f"Reset Series {tag}",
        series_type="ONGOING",
        status="ACTIVE",
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    issue = ReleaseIssue(
        owner_user_id=owner_user_id,
        release_uuid=f"reset-rec-v2-{tag}",
        series_id=int(series.id or 0),
        issue_number="1",
        title=f"Issue 1 {tag}",
        release_status="SCHEDULED",
        release_date=date.today() + timedelta(days=14),
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)
    run = RecommendationRunV2(owner_user_id=owner_user_id, status="COMPLETED")
    session.add(run)
    session.commit()
    session.refresh(run)
    score = RecommendationScoreV2(
        owner_user_id=owner_user_id,
        recommendation_run_id=int(run.id or 0),
        release_issue_id=int(issue.id or 0),
        total_score=75.0,
        recommendation_tier="BUY",
        recommendation_type="CONTINUE_RUN",
        confidence_score=0.7,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    session.add(
        RecommendationScoreComponentV2(
            recommendation_score_id=int(score.id or 0),
            component_name="pull_momentum",
            component_score=10.0,
            component_weight=0.25,
            explanation="reset test",
        )
    )
    session.commit()


def test_reset_user_collection_data_dry_run_and_scoped_delete(client, session) -> None:
    victim_email = "reset-victim@example.com"
    other_email = "reset-other@example.com"
    victim_token = register_and_login(client, victim_email)
    other_token = register_and_login(client, other_email)

    create_order(client, victim_token)
    create_order(client, other_token)

    victim = session.exec(select(User).where(User.email == victim_email)).one()
    other = session.exec(select(User).where(User.email == other_email)).one()
    _seed_retailer_account(session, user_id=int(victim.id))
    session.add(
        RetailerOrderSnapshot(
            owner_user_id=int(victim.id),
            retailer_account_id=int(
                session.exec(
                    select(RetailerAccount.id).where(RetailerAccount.owner_user_id == victim.id)
                ).one()
            ),
            retailer="midtown",
            retailer_order_number="900001",
            order_status="Shipped",
            raw_snapshot_json={},
        )
    )
    session.commit()

    dry = reset_user_collection_data(session, user=victim, execute=False)
    assert dry.dry_run is True
    assert dry.total_rows > 0

    victim_inventory_before_other = len(
        session.exec(select(InventoryCopy.id).where(InventoryCopy.user_id == other.id)).all()
    )
    assert victim_inventory_before_other == 1

    reset_user_collection_data(session, user=victim, execute=True)

    assert session.exec(select(User).where(User.email == victim_email)).one() is not None
    assert session.exec(select(RetailerAccount).where(RetailerAccount.owner_user_id == victim.id)).one() is not None
    assert len(session.exec(select(InventoryCopy.id).where(InventoryCopy.user_id == victim.id)).all()) == 0
    assert len(session.exec(select(Order.id).where(Order.user_id == victim.id)).all()) == 0
    assert (
        len(session.exec(select(RetailerOrderSnapshot.id).where(RetailerOrderSnapshot.owner_user_id == victim.id)).all())
        == 0
    )

    assert len(session.exec(select(InventoryCopy.id).where(InventoryCopy.user_id == other.id)).all()) == 1
    assert len(session.exec(select(Order.id).where(Order.user_id == other.id)).all()) == 1


def test_reset_deletes_recommendation_score_v2_components_before_parent(client, session) -> None:
    victim_email = "reset-rec-victim@example.com"
    other_email = "reset-rec-other@example.com"
    register_and_login(client, victim_email)
    register_and_login(client, other_email)

    victim = session.exec(select(User).where(User.email == victim_email)).one()
    other = session.exec(select(User).where(User.email == other_email)).one()
    _seed_recommendation_score_with_component(session, owner_user_id=int(victim.id), tag="victim")
    _seed_recommendation_score_with_component(session, owner_user_id=int(other.id), tag="other")

    reset_user_collection_data(session, user=victim, execute=True)

    victim_score_count = session.exec(
        select(func.count())
        .select_from(RecommendationScoreV2)
        .where(RecommendationScoreV2.owner_user_id == victim.id)
    ).one()
    victim_component_count = session.exec(
        select(func.count())
        .select_from(RecommendationScoreComponentV2)
        .join(
            RecommendationScoreV2,
            RecommendationScoreComponentV2.recommendation_score_id == RecommendationScoreV2.id,
        )
        .where(RecommendationScoreV2.owner_user_id == victim.id)
    ).one()
    other_score_count = session.exec(
        select(func.count())
        .select_from(RecommendationScoreV2)
        .where(RecommendationScoreV2.owner_user_id == other.id)
    ).one()
    other_component_count = session.exec(
        select(func.count())
        .select_from(RecommendationScoreComponentV2)
        .join(
            RecommendationScoreV2,
            RecommendationScoreComponentV2.recommendation_score_id == RecommendationScoreV2.id,
        )
        .where(RecommendationScoreV2.owner_user_id == other.id)
    ).one()

    assert victim_score_count == 0
    assert victim_component_count == 0
    assert other_score_count == 1
    assert other_component_count == 1
