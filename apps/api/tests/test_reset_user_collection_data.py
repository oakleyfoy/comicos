from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlmodel import Session, func, select

from app.models import (
    DraftImport,
    InventoryCopy,
    LunarFeedRawRow,
    LunarFeedRun,
    Order,
    OrderItem,
    OrganizationSecurityContext,
    Portfolio,
    PortfolioItem,
    ReleaseIssue,
    ReleaseSeries,
    RetailerAccount,
    RetailerOrderSnapshot,
    User,
    UserAuthSession,
    UserAuthSessionEvent,
)
from app.models.p92_import_health import P92ImportHealthEvent
from app.models.recommendation_v2 import (
    RecommendationRunV2,
    RecommendationScoreComponentV2,
    RecommendationScoreV2,
)
from app.models.release_intelligence import ReleaseVariant
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


def _seed_release_issue_with_variant(session: Session, *, owner_user_id: int, tag: str) -> tuple[ReleaseIssue, ReleaseVariant]:
    series = ReleaseSeries(
        owner_user_id=owner_user_id,
        publisher="Marvel",
        series_name=f"Catalog Series {tag}",
        series_type="ONGOING",
        status="ACTIVE",
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    issue = ReleaseIssue(
        owner_user_id=owner_user_id,
        release_uuid=f"reset-catalog-{tag}",
        series_id=int(series.id or 0),
        issue_number="1",
        title=f"Catalog Issue {tag}",
        release_status="SCHEDULED",
        release_date=date.today() + timedelta(days=21),
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)
    variant = ReleaseVariant(
        issue_id=int(issue.id or 0),
        variant_uuid=f"reset-var-{tag}",
        variant_name="Cover A",
        variant_type="STANDARD",
        source_item_code=f"CAT-{tag}",
    )
    session.add(variant)
    session.commit()
    session.refresh(variant)
    return issue, variant


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


def test_reset_preserves_release_catalog_issue_and_variant(client, session) -> None:
    victim_email = "reset-catalog-victim@example.com"
    victim_token = register_and_login(client, victim_email)
    create_order(client, victim_token)

    victim = session.exec(select(User).where(User.email == victim_email)).one()
    issue, variant = _seed_release_issue_with_variant(session, owner_user_id=int(victim.id), tag="victim")
    issue_id = int(issue.id or 0)
    variant_id = int(variant.id or 0)

    reset_user_collection_data(session, user=victim, execute=True)

    assert len(session.exec(select(InventoryCopy.id).where(InventoryCopy.user_id == victim.id)).all()) == 0
    assert len(session.exec(select(Order.id).where(Order.user_id == victim.id)).all()) == 0
    assert session.get(ReleaseIssue, issue_id) is not None
    assert session.get(ReleaseVariant, variant_id) is not None
    assert (
        session.exec(select(ReleaseIssue).where(ReleaseIssue.id == issue_id, ReleaseIssue.owner_user_id == victim.id)).one()
        is not None
    )


def test_reset_deletes_inventory_and_portfolio_before_order_items(client, session) -> None:
    email = "reset-inv-order-chain@example.com"
    token = register_and_login(client, email)
    create_order(client, token)

    user = session.exec(select(User).where(User.email == email)).one()
    order_id = session.exec(select(Order.id).where(Order.user_id == user.id)).one()
    order_item_id = session.exec(
        select(OrderItem.id).where(OrderItem.order_id == order_id)
    ).one()
    copy_id = session.exec(select(InventoryCopy.id).where(InventoryCopy.user_id == user.id)).one()
    copy = session.get(InventoryCopy, int(copy_id))
    assert copy is not None
    assert int(copy.order_item_id) == int(order_item_id)

    portfolio = Portfolio(
        owner_user_id=int(user.id),
        name="Reset chain",
        portfolio_type="collection",
        status="ACTIVE",
        replay_key="reset-inv-order-chain",
    )
    session.add(portfolio)
    session.flush()
    session.add(
        PortfolioItem(
            portfolio_id=int(portfolio.id),
            inventory_item_id=int(copy_id),
            allocation_role="holding",
        )
    )
    session.commit()
    portfolio_id = int(portfolio.id or 0)

    reset_user_collection_data(session, user=user, execute=True)

    assert session.get(Order, int(order_id)) is None
    assert session.get(OrderItem, int(order_item_id)) is None
    assert session.get(InventoryCopy, int(copy_id)) is None
    assert (
        len(
            session.exec(
                select(PortfolioItem).where(PortfolioItem.portfolio_id == portfolio_id)
            ).all()
        )
        == 0
    )
    assert len(session.exec(select(Portfolio).where(Portfolio.owner_user_id == user.id)).all()) == 0


def _seed_draft_import_with_health_event(session: Session, *, user_id: int, tag: str) -> int:
    draft = DraftImport(
        user_id=user_id,
        raw_text=f"draft {tag}",
        parsed_payload_json={"items": [], "retailer": "Test", "confidence_score": "0.5"},
        confidence_score=Decimal("0.5"),
        status="draft",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(draft)
    session.commit()
    session.refresh(draft)
    draft_id = int(draft.id or 0)
    session.add(
        P92ImportHealthEvent(
            owner_user_id=user_id,
            draft_import_id=draft_id,
            event_type="IMPORT_PARSED",
            payload_json={"tag": tag},
        )
    )
    session.commit()
    return draft_id


def test_reset_deletes_p92_import_health_event_before_draft_import(client, session) -> None:
    victim_email = "reset-draft-health-victim@example.com"
    other_email = "reset-draft-health-other@example.com"
    register_and_login(client, victim_email)
    register_and_login(client, other_email)

    victim = session.exec(select(User).where(User.email == victim_email)).one()
    other = session.exec(select(User).where(User.email == other_email)).one()
    victim_draft_id = _seed_draft_import_with_health_event(session, user_id=int(victim.id), tag="victim")
    other_draft_id = _seed_draft_import_with_health_event(session, user_id=int(other.id), tag="other")

    reset_user_collection_data(session, user=victim, execute=True)

    assert session.get(DraftImport, victim_draft_id) is None
    assert (
        session.exec(
            select(func.count())
            .select_from(P92ImportHealthEvent)
            .where(P92ImportHealthEvent.owner_user_id == victim.id)
        ).one()
        == 0
    )
    assert session.get(DraftImport, other_draft_id) is not None
    assert (
        session.exec(
            select(func.count())
            .select_from(P92ImportHealthEvent)
            .where(P92ImportHealthEvent.draft_import_id == other_draft_id)
        ).one()
        == 1
    )


def test_reset_preserves_lunar_feed_and_auth_session_infrastructure(client, session) -> None:
    email = "reset-preserve-infra@example.com"
    token = register_and_login(client, email)
    create_order(client, token)

    user = session.exec(select(User).where(User.email == email)).one()
    user_id = int(user.id)

    feed_run = LunarFeedRun(
        owner_user_id=user_id,
        source_type="WEEKLY",
        status="COMPLETED",
        file_name="lunar.csv",
    )
    session.add(feed_run)
    session.commit()
    session.refresh(feed_run)
    feed_run_id = int(feed_run.id or 0)
    session.add(
        LunarFeedRawRow(
            feed_run_id=feed_run_id,
            row_index=0,
            product_code="ABC123",
            row_payload_json={"title": "Test"},
        )
    )

    auth_session = UserAuthSession(
        user_id=user_id,
        session_token_hash="hash-reset-preserve",
        device_label="Laptop",
        device_type="web",
        session_status="active",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    session.add(auth_session)
    session.commit()
    session.refresh(auth_session)
    auth_session_id = int(auth_session.id or 0)
    session.add(
        UserAuthSessionEvent(
            auth_session_id=auth_session_id,
            user_id=user_id,
            event_type="login",
            event_payload_json={},
        )
    )
    if session.exec(
        select(OrganizationSecurityContext).where(OrganizationSecurityContext.user_id == user_id)
    ).first() is None:
        session.add(OrganizationSecurityContext(user_id=user_id, active_organization_id=None))
    session.commit()
    security_contexts_before = session.exec(
        select(func.count())
        .select_from(OrganizationSecurityContext)
        .where(OrganizationSecurityContext.user_id == user_id)
    ).one()
    assert security_contexts_before >= 1
    auth_sessions_before = session.exec(
        select(func.count()).select_from(UserAuthSession).where(UserAuthSession.user_id == user_id)
    ).one()
    auth_events_before = session.exec(
        select(func.count()).select_from(UserAuthSessionEvent).where(UserAuthSessionEvent.user_id == user_id)
    ).one()

    inventory_before = len(session.exec(select(InventoryCopy.id).where(InventoryCopy.user_id == user_id)).all())
    assert inventory_before >= 1

    reset_user_collection_data(session, user=user, execute=True)

    assert session.get(LunarFeedRun, feed_run_id) is not None
    assert (
        session.exec(
            select(func.count())
            .select_from(LunarFeedRawRow)
            .where(LunarFeedRawRow.feed_run_id == feed_run_id)
        ).one()
        == 1
    )
    assert session.get(UserAuthSession, auth_session_id) is not None
    assert (
        session.exec(
            select(func.count()).select_from(UserAuthSession).where(UserAuthSession.user_id == user_id)
        ).one()
        == auth_sessions_before
    )
    assert (
        session.exec(
            select(func.count())
            .select_from(UserAuthSessionEvent)
            .where(UserAuthSessionEvent.user_id == user_id)
        ).one()
        == auth_events_before
    )
    assert (
        session.exec(
            select(func.count())
            .select_from(OrganizationSecurityContext)
            .where(OrganizationSecurityContext.user_id == user_id)
        ).one()
        == security_contexts_before
    )

    assert len(session.exec(select(InventoryCopy.id).where(InventoryCopy.user_id == user_id)).all()) == 0
    assert len(session.exec(select(Order.id).where(Order.user_id == user_id)).all()) == 0
