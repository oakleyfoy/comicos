"""P72-02 grading operations dashboard and metrics."""

from __future__ import annotations

from decimal import Decimal

from sqlmodel import Session, func, select

from app.models.p72_grading_operations import P72GradingBatch, P72GradingQueueEntry
from app.schemas.p72_grading_operations import (
    P72GradingBatchRead,
    P72GradingOperationsDashboardRead,
    P72GradingOperationsMetricsRead,
    P72GradingQueueEntryRead,
)
from app.services.grading_queue_service import (
    IN_PROCESS_STATUSES,
    STATUS_AT_CGC,
    STATUS_LISTED,
    STATUS_RETURNED,
    STATUS_SOLD,
    STATUS_SUBMITTED,
    WAITING_STATUSES,
    COMPLETED_STATUSES,
)


def build_operations_dashboard(
    session: Session,
    *,
    owner_user_id: int,
) -> P72GradingOperationsDashboardRead:
    rows = list(
        session.exec(
            select(P72GradingQueueEntry).where(P72GradingQueueEntry.owner_user_id == owner_user_id)
        ).all()
    )
    waiting = sum(1 for r in rows if r.status in WAITING_STATUSES)
    submitted = sum(1 for r in rows if r.status == STATUS_SUBMITTED)
    at_cgc = sum(1 for r in rows if r.status == STATUS_AT_CGC)
    returned = sum(1 for r in rows if r.status == STATUS_RETURNED)
    listed = sum(1 for r in rows if r.status == STATUS_LISTED)
    sold = sum(1 for r in rows if r.status == STATUS_SOLD)
    in_process = sum(1 for r in rows if r.status in IN_PROCESS_STATUSES)
    completed = sum(1 for r in rows if r.status in COMPLETED_STATUSES)

    turnarounds = [r.turnaround_days for r in rows if r.turnaround_days is not None]
    avg_turn = round(sum(turnarounds) / len(turnarounds), 2) if turnarounds else 0.0

    costs = [float(r.final_grading_cost) for r in rows if r.final_grading_cost is not None]
    avg_cost = round(sum(costs) / len(costs), 2) if costs else 0.0
    total_spend = round(sum(costs), 2)

    total_submissions = sum(1 for r in rows if r.status not in WAITING_STATUSES and r.status != "CANDIDATE")

    batches = list(
        session.exec(
            select(P72GradingBatch)
            .where(P72GradingBatch.owner_user_id == owner_user_id)
            .order_by(P72GradingBatch.created_at.desc())
            .limit(10)
        ).all()
    )
    recent = sorted(rows, key=lambda r: r.updated_at, reverse=True)[:15]

    metrics = P72GradingOperationsMetricsRead(
        total_submissions=total_submissions,
        books_in_process=in_process,
        books_completed=completed,
        average_turnaround_days=avg_turn,
        average_grading_cost=avg_cost,
        total_grading_spend=total_spend,
        waiting_count=waiting,
        submitted_count=submitted,
        at_cgc_count=at_cgc,
        returned_count=returned,
        listed_count=listed,
        sold_count=sold,
    )
    return P72GradingOperationsDashboardRead(
        metrics=metrics,
        batch_summary=[P72GradingBatchRead.model_validate(b) for b in batches],
        recent_queue=[P72GradingQueueEntryRead.model_validate(r) for r in recent],
    )
