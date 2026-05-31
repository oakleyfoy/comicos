from __future__ import annotations

from sqlmodel import Session, select

from app.models.purchase_budget import PurchaseBudget, PurchaseBudgetAllocation
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.schemas.purchase_budget import (
    PurchaseBudgetAllocationRead,
    PurchaseBudgetRead,
    PurchaseBudgetSummaryRead,
    PurchaseBudgetUpdate,
)
from app.services.purchase_budget_engine import generate_budget_allocations


def _budget_to_read(row: PurchaseBudget) -> PurchaseBudgetRead:
    return PurchaseBudgetRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        monthly_budget=float(row.monthly_budget),
        weekly_budget=float(row.weekly_budget),
        is_active=bool(row.is_active),
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


def _default_budget(owner_user_id: int) -> PurchaseBudget:
    return PurchaseBudget(
        owner_user_id=owner_user_id,
        monthly_budget=0.0,
        weekly_budget=0.0,
        is_active=True,
    )


def get_purchase_budget_row(session: Session, *, owner_user_id: int) -> PurchaseBudget:
    row = session.exec(select(PurchaseBudget).where(PurchaseBudget.owner_user_id == owner_user_id)).first()
    if row is None:
        row = _default_budget(owner_user_id)
        session.add(row)
        session.commit()
        session.refresh(row)
    return row


def get_purchase_budget(session: Session, *, owner_user_id: int) -> PurchaseBudgetRead:
    return _budget_to_read(get_purchase_budget_row(session, owner_user_id=owner_user_id))


def update_purchase_budget(
    session: Session,
    *,
    owner_user_id: int,
    payload: PurchaseBudgetUpdate,
) -> PurchaseBudgetRead:
    from app.models.purchase_profile import utc_now

    row = get_purchase_budget_row(session, owner_user_id=owner_user_id)
    if payload.monthly_budget is not None:
        row.monthly_budget = max(0.0, float(payload.monthly_budget))
    if payload.weekly_budget is not None:
        row.weekly_budget = max(0.0, float(payload.weekly_budget))
    if payload.is_active is not None:
        row.is_active = bool(payload.is_active)
        if not row.is_active:
            raise ValueError("Purchase budget must remain active; one active budget per owner is required.")
    row.updated_at = utc_now()
    session.add(row)
    session.commit()
    session.refresh(row)
    return _budget_to_read(row)


def _latest_allocation_rows(session: Session, *, owner_user_id: int) -> dict[int, PurchaseBudgetAllocation]:
    rows = session.exec(
        select(PurchaseBudgetAllocation)
        .where(PurchaseBudgetAllocation.owner_user_id == owner_user_id)
        .order_by(PurchaseBudgetAllocation.created_at.desc(), PurchaseBudgetAllocation.id.desc())
    ).all()
    latest: dict[int, PurchaseBudgetAllocation] = {}
    for row in rows:
        if row.release_id not in latest:
            latest[row.release_id] = row
    return latest


def _allocation_to_read(session: Session, *, row: PurchaseBudgetAllocation) -> PurchaseBudgetAllocationRead:
    issue = session.get(ReleaseIssue, row.release_id)
    series = session.get(ReleaseSeries, issue.series_id) if issue else None
    return PurchaseBudgetAllocationRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        release_id=int(row.release_id),
        recommendation_tier=row.recommendation_tier,  # type: ignore[arg-type]
        allocated_amount=float(row.allocated_amount),
        priority_rank=int(row.priority_rank),
        rationale=row.rationale,
        created_at=row.created_at.isoformat(),
        title=issue.title if issue else "",
        issue_number=issue.issue_number if issue else "",
        publisher=series.publisher if series else "",
        series_name=series.series_name if series else "",
    )


def generate_purchase_budget_allocations(session: Session, *, owner_user_id: int) -> int:
    budget = get_purchase_budget_row(session, owner_user_id=owner_user_id)
    computed, _cap = generate_budget_allocations(session, owner_user_id=owner_user_id, budget=budget)
    latest = _latest_allocation_rows(session, owner_user_id=owner_user_id)
    created = 0
    for result in computed:
        prior = latest.get(result.release_id)
        if prior is not None:
            if (
                prior.recommendation_tier == result.recommendation_tier
                and abs(float(prior.allocated_amount) - float(result.allocated_amount)) < 1e-9
                and prior.priority_rank == result.priority_rank
                and prior.rationale == result.rationale
            ):
                continue
        session.add(
            PurchaseBudgetAllocation(
                owner_user_id=owner_user_id,
                release_id=result.release_id,
                recommendation_tier=result.recommendation_tier,
                allocated_amount=result.allocated_amount,
                priority_rank=result.priority_rank,
                rationale=result.rationale,
            )
        )
        created += 1
    session.commit()
    return created


def list_purchase_budget_allocations(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[PurchaseBudgetAllocationRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    latest = _latest_allocation_rows(session, owner_user_id=owner_user_id)
    items = [_allocation_to_read(session, row=row) for row in latest.values()]
    items.sort(key=lambda r: (r.priority_rank, r.release_id))
    total = len(items)
    return items[offset : offset + limit], total


def build_purchase_budget_summary(session: Session, *, owner_user_id: int) -> PurchaseBudgetSummaryRead:
    budget = get_purchase_budget_row(session, owner_user_id=owner_user_id)
    total_budget = round(float(budget.monthly_budget), 2)
    latest = _latest_allocation_rows(session, owner_user_id=owner_user_id)
    allocated_budget = round(sum(float(r.allocated_amount) for r in latest.values()), 2)
    remaining_budget = round(max(0.0, total_budget - allocated_budget), 2)
    pct = round((allocated_budget / total_budget * 100.0) if total_budget > 0 else 0.0, 2)
    return PurchaseBudgetSummaryRead(
        total_budget=total_budget,
        weekly_budget=round(float(budget.weekly_budget), 2),
        allocated_budget=allocated_budget,
        remaining_budget=remaining_budget,
        allocation_percentage=pct,
        is_active=bool(budget.is_active),
    )
