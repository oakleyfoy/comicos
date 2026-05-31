from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db.session import get_engine
from app.models import User
from app.services.continue_run_planning import build_continue_run_planning
from release_platform_test_helpers import seed_release_platform_horizons
from release_planning_test_helpers import seed_inventory_issues, seed_release_issue
from test_inventory import register_and_login
from sqlmodel import select

from app.services.opportunity_intelligence import build_opportunity_intelligence
from app.services.opportunity_scoring import COMPONENT_HORIZON_PLANNING
from app.services.release_horizon_engine import HORIZON_NEXT_90, build_release_horizons


def test_continue_run_planning_read_only(client: TestClient) -> None:
    with Session(get_engine()) as session:
        owner = User(email="run-plan@example.com", password_hash="x", is_active=True)
        session.add(owner)
        session.commit()
        session.refresh(owner)
        owner_user_id = int(owner.id or 0)
        seed_release_platform_horizons(session, owner_user_id=owner_user_id)

        plans = build_continue_run_planning(session, owner_user_id=owner_user_id)
        assert any(plan.plan_type == "NEW_OPPORTUNITY" for plan in plans)
        assert all(
            plan.plan_type
            in {
                "CONTINUE_RUN",
                "START_FOLLOWING",
                "NEW_OPPORTUNITY",
                "COMPLETE_RUN",
                "WATCH",
                "PASS",
            }
            for plan in plans
        )


def test_continue_run_battle_beast_75_days(client: TestClient) -> None:
    email = "battle-beast@example.com"
    token = register_and_login(client, email)
    seed_inventory_issues(
        client,
        token,
        publisher="Image",
        title="Battle Beast",
        issue_numbers=[str(n) for n in range(1, 8)],
    )
    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == email)).one()
        owner_user_id = int(owner.id or 0)
        issue, _ = seed_release_issue(
            session,
            owner_user_id=owner_user_id,
            publisher="Image",
            series_name="Battle Beast",
            issue_number="8",
            title="Battle Beast #8",
            release_uuid="battle-beast-8",
            days_out=75,
        )
        plans = build_continue_run_planning(session, owner_user_id=owner_user_id)
        continue_plans = [plan for plan in plans if plan.series_name == "Battle Beast"]
        assert any(plan.plan_type == "CONTINUE_RUN" for plan in continue_plans)
        assert not any(plan.plan_type == "START_FOLLOWING" for plan in continue_plans)

        horizons = build_release_horizons(session, owner_user_id=owner_user_id)
        in_90 = [row for row in horizons.next_90_days if row.issue.id == issue.id]
        assert in_90
        assert in_90[0].horizon == HORIZON_NEXT_90


def test_start_following_jim_bob(client: TestClient) -> None:
    email = "jim-bob@example.com"
    token = register_and_login(client, email)
    seed_inventory_issues(client, token, publisher="Image", title="Jim Bob", issue_numbers=["15"])
    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == email)).one()
        owner_user_id = int(owner.id or 0)
        seed_release_issue(
            session,
            owner_user_id=owner_user_id,
            publisher="Image",
            series_name="Jim Bob",
            issue_number="16",
            title="Jim Bob #16",
            release_uuid="jim-bob-16",
            days_out=75,
        )
        plans = build_continue_run_planning(session, owner_user_id=owner_user_id)
        jim_plans = [plan for plan in plans if plan.series_name == "Jim Bob"]
        assert any(plan.plan_type == "START_FOLLOWING" for plan in jim_plans)
        assert not any(plan.plan_type == "CONTINUE_RUN" for plan in jim_plans)


def test_new_opportunity_unowned_number_one(client: TestClient) -> None:
    email = "new-image@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == email)).one()
        owner_user_id = int(owner.id or 0)
        issue, _ = seed_release_issue(
            session,
            owner_user_id=owner_user_id,
            publisher="Image",
            series_name="New Image Series",
            issue_number="1",
            title="New Image Series #1",
            release_uuid="new-image-1",
            days_out=75,
            signals=[("NEW_NUMBER_ONE", {"launch_type": "new"})],
        )
        plans = build_continue_run_planning(session, owner_user_id=owner_user_id)
        assert any(plan.plan_type == "NEW_OPPORTUNITY" and plan.release_issue_id == issue.id for plan in plans)

        opportunities = build_opportunity_intelligence(session, owner_user_id=owner_user_id)
        assert any(row.release_issue_id == issue.id for row in opportunities.top_new_opportunities)


def test_milestone_tmnt_300(client: TestClient) -> None:
    email = "tmnt@example.com"
    token = register_and_login(client, email)
    seed_inventory_issues(
        client,
        token,
        publisher="IDW",
        title="TMNT",
        issue_numbers=["297", "298", "299"],
    )
    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == email)).one()
        owner_user_id = int(owner.id or 0)
        issue, _ = seed_release_issue(
            session,
            owner_user_id=owner_user_id,
            publisher="IDW",
            series_name="TMNT",
            issue_number="300",
            title="TMNT #300",
            release_uuid="tmnt-300",
            days_out=75,
            signals=[("MILESTONE_NUMBERING", {"milestone": 300})],
        )
        plans = build_continue_run_planning(session, owner_user_id=owner_user_id)
        tmnt_plans = [plan for plan in plans if plan.release_issue_id == issue.id]
        assert any(plan.plan_type == "COMPLETE_RUN" for plan in tmnt_plans)

        opportunities = build_opportunity_intelligence(session, owner_user_id=owner_user_id)
        milestone_row = next(row for row in opportunities.top_milestone_books if row.release_issue_id == issue.id)
        assert milestone_row.score_components.get("MILESTONE_SCORE", 0) > 0


def test_first_appearance_new_character_score(client: TestClient) -> None:
    email = "first-app@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == email)).one()
        owner_user_id = int(owner.id or 0)
        issue, _ = seed_release_issue(
            session,
            owner_user_id=owner_user_id,
            publisher="Marvel",
            series_name="Ghost Maker",
            issue_number="1",
            title="Ghost Maker First Appearance",
            release_uuid="ghost-maker-1",
            days_out=75,
            signals=[
                ("FIRST_APPEARANCE", {"character": "Ghost Maker"}),
                ("NEW_CHARACTER", {"character": "Ghost Maker"}),
            ],
        )
        plans = build_continue_run_planning(session, owner_user_id=owner_user_id)
        assert any(plan.plan_type == "NEW_OPPORTUNITY" for plan in plans if plan.release_issue_id == issue.id)

        opportunities = build_opportunity_intelligence(session, owner_user_id=owner_user_id)
        row = next(item for item in opportunities.top_first_appearances if item.release_issue_id == issue.id)
        assert row.score_components.get("FIRST_APPEARANCE_SCORE", 0) > 0
        assert row.score_components.get("NEW_CHARACTER_SCORE", 0) > 0


def test_horizon_priority_strong_75_day_beats_weak_release_week(client: TestClient) -> None:
    email = "horizon-priority@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == email)).one()
        owner_user_id = int(owner.id or 0)
        strong_issue, _ = seed_release_issue(
            session,
            owner_user_id=owner_user_id,
            publisher="Image",
            series_name="Strong Signal",
            issue_number="1",
            title="Strong Signal #1",
            release_uuid="strong-signal-1",
            days_out=75,
            signals=[("NEW_NUMBER_ONE", {}), ("FIRST_APPEARANCE", {})],
        )
        weak_issue, _ = seed_release_issue(
            session,
            owner_user_id=owner_user_id,
            publisher="Boom!",
            series_name="Weak Filler",
            issue_number="12",
            title="Weak Filler #12",
            release_uuid="weak-filler-12",
            days_out=10,
        )
        opportunities = build_opportunity_intelligence(session, owner_user_id=owner_user_id)
        ranked = opportunities.top_spec_opportunities
        strong_idx = next(i for i, row in enumerate(ranked) if row.release_issue_id == strong_issue.id)
        weak_idx = next(i for i, row in enumerate(ranked) if row.release_issue_id == weak_issue.id)
        assert strong_idx < weak_idx
        strong_row = ranked[strong_idx]
        weak_row = ranked[weak_idx]
        assert strong_row.score_components[COMPONENT_HORIZON_PLANNING] > weak_row.score_components[COMPONENT_HORIZON_PLANNING]
