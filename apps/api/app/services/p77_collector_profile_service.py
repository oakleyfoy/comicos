"""P77-01 collector profile, goals, and budget persistence."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, delete, select

from app.models.p77_collector_profile import (
    P77CollectorBudget,
    P77CollectorGoal,
    P77CollectorInterest,
    P77CollectorProfile,
)
from app.schemas.p77_collector_profile import (
    P77BudgetAllocationRead,
    P77CollectorBudgetRead,
    P77CollectorBudgetUpdate,
    P77CollectorGoalCreate,
    P77CollectorGoalRead,
    P77CollectorGoalUpdate,
    P77CollectorProfileDashboardRead,
    P77CollectorProfileRead,
    P77CollectorProfileUpdate,
    P77InterestItemRead,
    P77InterestItemWrite,
)
from app.services.run_detection import run_detection_groups_for_user


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _completion_percent(*, target: float, progress: float) -> float:
    if target <= 0:
        return 0.0 if progress <= 0 else 100.0
    return round(min(100.0, max(0.0, 100.0 * progress / target)), 1)


def _allocations_from_json(rows: list) -> list[P77BudgetAllocationRead]:
    items: list[P77BudgetAllocationRead] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        amount = float(row.get("amount") or 0)
        items.append(P77BudgetAllocationRead(name=name, amount=amount))
    return items


def _allocations_to_json(items: list[P77BudgetAllocationRead] | None) -> list[dict]:
    if not items:
        return []
    return [{"name": item.name.strip(), "amount": float(item.amount)} for item in items if item.name.strip()]


def _ensure_profile(session: Session, *, owner_user_id: int) -> P77CollectorProfile:
    row = session.exec(select(P77CollectorProfile).where(P77CollectorProfile.owner_user_id == owner_user_id)).first()
    if row is not None:
        return row
    row = P77CollectorProfile(owner_user_id=owner_user_id)
    session.add(row)
    session.flush()
    return row


def _ensure_budget(session: Session, *, owner_user_id: int) -> P77CollectorBudget:
    row = session.exec(select(P77CollectorBudget).where(P77CollectorBudget.owner_user_id == owner_user_id)).first()
    if row is not None:
        return row
    row = P77CollectorBudget(owner_user_id=owner_user_id)
    session.add(row)
    session.flush()
    return row


def _interest_reads(session: Session, *, owner_user_id: int, interest_type: str) -> list[P77InterestItemRead]:
    rows = session.exec(
        select(P77CollectorInterest)
        .where(P77CollectorInterest.owner_user_id == owner_user_id)
        .where(P77CollectorInterest.interest_type == interest_type)
        .order_by(P77CollectorInterest.priority_rank.asc(), P77CollectorInterest.id.asc())
    ).all()
    return [
        P77InterestItemRead(
            id=int(r.id or 0),
            interest_type=r.interest_type,  # type: ignore[arg-type]
            label=r.label,
            priority_rank=r.priority_rank,
        )
        for r in rows
    ]


def _replace_interests(
    session: Session,
    *,
    owner_user_id: int,
    interest_type: str,
    items: list[P77InterestItemWrite] | None,
) -> None:
    if items is None:
        return
    session.exec(
        delete(P77CollectorInterest)
        .where(P77CollectorInterest.owner_user_id == owner_user_id)
        .where(P77CollectorInterest.interest_type == interest_type)
    )
    for item in items:
        session.add(
            P77CollectorInterest(
                owner_user_id=owner_user_id,
                interest_type=interest_type,
                label=item.label.strip(),
                priority_rank=item.priority_rank,
            )
        )
    session.flush()


def get_collector_profile(session: Session, *, owner_user_id: int) -> P77CollectorProfileRead:
    profile = _ensure_profile(session, owner_user_id=owner_user_id)
    return P77CollectorProfileRead(
        owner_id=owner_user_id,
        collector_type=profile.collector_type,  # type: ignore[arg-type]
        risk_profile=profile.risk_profile,  # type: ignore[arg-type]
        time_horizon=profile.time_horizon,  # type: ignore[arg-type]
        grading_preference=profile.grading_preference,  # type: ignore[arg-type]
        hold_preference=profile.hold_preference,  # type: ignore[arg-type]
        default_copy_count=profile.default_copy_count,
        key_issue_copy_count=profile.key_issue_copy_count,
        ratio_variant_copy_count=profile.ratio_variant_copy_count,
        publishers=_interest_reads(session, owner_user_id=owner_user_id, interest_type="PUBLISHER"),
        characters=_interest_reads(session, owner_user_id=owner_user_id, interest_type="CHARACTER"),
        creators=_interest_reads(session, owner_user_id=owner_user_id, interest_type="CREATOR"),
        updated_at=profile.updated_at,
    )


def update_collector_profile(
    session: Session,
    *,
    owner_user_id: int,
    payload: P77CollectorProfileUpdate,
) -> P77CollectorProfileRead:
    profile = _ensure_profile(session, owner_user_id=owner_user_id)
    data = payload.model_dump(exclude_unset=True, exclude={"publishers", "characters", "creators"})
    for key, value in data.items():
        setattr(profile, key, value)
    profile.updated_at = _utc_now()
    session.add(profile)
    _replace_interests(session, owner_user_id=owner_user_id, interest_type="PUBLISHER", items=payload.publishers)
    _replace_interests(session, owner_user_id=owner_user_id, interest_type="CHARACTER", items=payload.characters)
    _replace_interests(session, owner_user_id=owner_user_id, interest_type="CREATOR", items=payload.creators)
    session.flush()
    return get_collector_profile(session, owner_user_id=owner_user_id)


def get_collector_budget(session: Session, *, owner_user_id: int) -> P77CollectorBudgetRead:
    budget = _ensure_budget(session, owner_user_id=owner_user_id)
    return P77CollectorBudgetRead(
        owner_id=owner_user_id,
        monthly_budget=float(budget.monthly_budget),
        budget_period=budget.budget_period,  # type: ignore[arg-type]
        publisher_allocations=_allocations_from_json(budget.publisher_allocations_json),
        category_allocations=_allocations_from_json(budget.category_allocations_json),
        updated_at=budget.updated_at,
    )


def update_collector_budget(
    session: Session,
    *,
    owner_user_id: int,
    payload: P77CollectorBudgetUpdate,
) -> P77CollectorBudgetRead:
    budget = _ensure_budget(session, owner_user_id=owner_user_id)
    if payload.monthly_budget is not None:
        budget.monthly_budget = float(payload.monthly_budget)
    if payload.budget_period is not None:
        budget.budget_period = payload.budget_period
    if payload.publisher_allocations is not None:
        budget.publisher_allocations_json = _allocations_to_json(payload.publisher_allocations)
    if payload.category_allocations is not None:
        budget.category_allocations_json = _allocations_to_json(payload.category_allocations)
    budget.updated_at = _utc_now()
    session.add(budget)
    session.flush()
    return get_collector_budget(session, owner_user_id=owner_user_id)


def _sync_run_completion_progress(session: Session, *, owner_user_id: int, goal: P77CollectorGoal) -> None:
    if goal.goal_type != "RUN_COMPLETION":
        return
    meta = dict(goal.metadata_json or {})
    series_name = str(meta.get("series_name") or goal.title or "").strip()
    if not series_name:
        return
    groups = run_detection_groups_for_user(session, owner_user_id=owner_user_id)
    for group in groups:
        if group.title.strip().lower() == series_name.lower() or series_name.lower() in group.title.strip().lower():
            known = max(group.known_issue_count, group.distinct_issue_count, 1)
            goal.progress_value = float(group.distinct_issue_count)
            goal.target_value = float(known) if goal.target_value <= 0 else goal.target_value
            goal.completion_percent = _completion_percent(target=goal.target_value, progress=goal.progress_value)
            return


def _goal_to_read(goal: P77CollectorGoal) -> P77CollectorGoalRead:
    return P77CollectorGoalRead(
        id=int(goal.id or 0),
        goal_type=goal.goal_type,  # type: ignore[arg-type]
        title=goal.title,
        target_value=float(goal.target_value),
        progress_value=float(goal.progress_value),
        completion_percent=float(goal.completion_percent),
        metadata=dict(goal.metadata_json or {}),
        updated_at=goal.updated_at,
    )


def list_collector_goals(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[P77CollectorGoalRead], int]:
    lim = max(1, min(limit, 200))
    off = max(0, offset)
    rows = session.exec(
        select(P77CollectorGoal)
        .where(P77CollectorGoal.owner_user_id == owner_user_id)
        .order_by(P77CollectorGoal.updated_at.desc(), P77CollectorGoal.id.desc())
    ).all()
    for row in rows:
        _sync_run_completion_progress(session, owner_user_id=owner_user_id, goal=row)
    session.flush()
    items = [_goal_to_read(row) for row in rows]
    total = len(items)
    return items[off : off + lim], total


def create_collector_goal(
    session: Session,
    *,
    owner_user_id: int,
    payload: P77CollectorGoalCreate,
) -> P77CollectorGoalRead:
    completion = _completion_percent(target=payload.target_value, progress=payload.progress_value)
    row = P77CollectorGoal(
        owner_user_id=owner_user_id,
        goal_type=payload.goal_type,
        title=payload.title.strip(),
        target_value=float(payload.target_value),
        progress_value=float(payload.progress_value),
        completion_percent=completion,
        metadata_json=dict(payload.metadata),
    )
    session.add(row)
    session.flush()
    _sync_run_completion_progress(session, owner_user_id=owner_user_id, goal=row)
    session.add(row)
    session.flush()
    return _goal_to_read(row)


def update_collector_goal(
    session: Session,
    *,
    owner_user_id: int,
    goal_id: int,
    payload: P77CollectorGoalUpdate,
) -> P77CollectorGoalRead:
    row = session.get(P77CollectorGoal, goal_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Goal not found.")
    if payload.goal_type is not None:
        row.goal_type = payload.goal_type
    if payload.title is not None:
        row.title = payload.title.strip()
    if payload.target_value is not None:
        row.target_value = float(payload.target_value)
    if payload.progress_value is not None:
        row.progress_value = float(payload.progress_value)
    if payload.metadata is not None:
        row.metadata_json = dict(payload.metadata)
    row.completion_percent = _completion_percent(target=row.target_value, progress=row.progress_value)
    _sync_run_completion_progress(session, owner_user_id=owner_user_id, goal=row)
    row.updated_at = _utc_now()
    session.add(row)
    session.flush()
    return _goal_to_read(row)


def build_collector_profile_dashboard(session: Session, *, owner_user_id: int) -> P77CollectorProfileDashboardRead:
    profile = get_collector_profile(session, owner_user_id=owner_user_id)
    budget = get_collector_budget(session, owner_user_id=owner_user_id)
    goals, _ = list_collector_goals(session, owner_user_id=owner_user_id, limit=20, offset=0)
    avg_completion = round(sum(g.completion_percent for g in goals) / len(goals), 1) if goals else 0.0
    publisher_budget_total = sum(a.amount for a in budget.publisher_allocations)
    category_budget_total = sum(a.amount for a in budget.category_allocations)
    return P77CollectorProfileDashboardRead(
        profile=profile,
        budget=budget,
        goals=goals,
        goals_summary={
            "total_goals": len(goals),
            "average_completion_percent": avg_completion,
            "publisher_budget_allocated": publisher_budget_total,
            "category_budget_allocated": category_budget_total,
        },
    )
