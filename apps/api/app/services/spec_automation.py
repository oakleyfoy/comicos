from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models.spec_automation import SpecAutomationRun
from app.schemas.spec_automation import SpecAutomationOpsPanelRead, SpecAutomationRunRead
from app.services.ai_spec_engine import generate_ai_spec_evaluations
from app.services.spec_baseline_engine import generate_spec_baseline_scores
from app.services.spec_input_builder import build_spec_inputs
from app.services.top_spec_pick_engine import generate_top_spec_picks
from app.services.weekly_spec_dashboard import build_weekly_spec_dashboard

logger = logging.getLogger(__name__)

STATUS_SUCCESS = "SUCCESS"
STATUS_FAILED = "FAILED"
STATUS_NO_CHANGE = "NO_CHANGE"


def _to_read(row: SpecAutomationRun) -> SpecAutomationRunRead:
    return SpecAutomationRunRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        started_at=row.started_at,
        completed_at=row.completed_at,
        status=row.status,
        inputs_processed=int(row.inputs_processed),
        baseline_scores_created=int(row.baseline_scores_created),
        ai_evaluations_created=int(row.ai_evaluations_created),
        top_picks_created=int(row.top_picks_created),
        runtime_ms=int(row.runtime_ms),
        error_message=row.error_message,
    )


def _latest_run(session: Session, *, owner_user_id: int) -> SpecAutomationRun | None:
    return session.exec(
        select(SpecAutomationRun)
        .where(SpecAutomationRun.owner_user_id == owner_user_id)
        .order_by(SpecAutomationRun.started_at.desc(), SpecAutomationRun.id.desc())
    ).first()


def run_spec_refresh(session: Session, *, owner_user_id: int) -> SpecAutomationRun:
    started = datetime.now(timezone.utc)
    run = SpecAutomationRun(owner_user_id=owner_user_id, started_at=started, status=STATUS_SUCCESS)
    session.add(run)
    session.commit()
    session.refresh(run)

    try:
        inputs = build_spec_inputs(session, owner_user_id=owner_user_id)
        run.inputs_processed = int(inputs.created + inputs.updated)

        baseline = generate_spec_baseline_scores(session, owner_user_id=owner_user_id)
        run.baseline_scores_created = int(baseline.computed + baseline.updated)

        ai = generate_ai_spec_evaluations(session, owner_user_id=owner_user_id)
        run.ai_evaluations_created = int(ai.computed + ai.updated)

        top = generate_top_spec_picks(session, owner_user_id=owner_user_id, limit=20)
        run.top_picks_created = int(top.computed)

        build_weekly_spec_dashboard(session, owner_user_id=owner_user_id)

        if (
            run.inputs_processed == 0
            and run.baseline_scores_created == 0
            and run.ai_evaluations_created == 0
            and run.top_picks_created == 0
            and top.skipped
        ):
            run.status = STATUS_NO_CHANGE
        else:
            run.status = STATUS_SUCCESS
    except Exception as exc:  # noqa: BLE001
        logger.exception("Spec automation refresh failed for owner %s", owner_user_id)
        session.rollback()
        run = session.get(SpecAutomationRun, run.id)
        assert run is not None
        run.status = STATUS_FAILED
        run.error_message = str(exc)[:2000]
        session.add(run)
        session.commit()
        session.refresh(run)
        completed = datetime.now(timezone.utc)
        run.completed_at = completed
        run.runtime_ms = int((completed - started).total_seconds() * 1000)
        session.add(run)
        session.commit()
        session.refresh(run)
        return run

    completed = datetime.now(timezone.utc)
    run.completed_at = completed
    run.runtime_ms = int((completed - started).total_seconds() * 1000)
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def list_spec_automation_runs(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[SpecAutomationRunRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = session.exec(
        select(SpecAutomationRun)
        .where(SpecAutomationRun.owner_user_id == owner_user_id)
        .order_by(SpecAutomationRun.started_at.desc(), SpecAutomationRun.id.desc())
    ).all()
    total = len(rows)
    page = rows[offset : offset + limit]
    return [_to_read(row) for row in page], total


def get_latest_spec_automation_run(session: Session, *, owner_user_id: int) -> SpecAutomationRunRead | None:
    row = _latest_run(session, owner_user_id=owner_user_id)
    if row is None:
        return None
    return _to_read(row)


def build_spec_automation_ops_panel(session: Session, *, owner_user_id: int) -> SpecAutomationOpsPanelRead:
    row = _latest_run(session, owner_user_id=owner_user_id)
    if row is None:
        return SpecAutomationOpsPanelRead()
    return SpecAutomationOpsPanelRead(
        last_run=row.completed_at or row.started_at,
        status=row.status,
        runtime_ms=int(row.runtime_ms),
        inputs_processed=int(row.inputs_processed),
        baseline_scores_created=int(row.baseline_scores_created),
        ai_evaluations_created=int(row.ai_evaluations_created),
        top_picks_created=int(row.top_picks_created),
    )


def trigger_spec_refresh_after_upstream(session: Session, *, owner_user_id: int) -> None:
    """Run spec pipeline after industry scanner or future release refresh; never raises."""
    try:
        run_spec_refresh(session, owner_user_id=owner_user_id)
    except Exception:  # noqa: BLE001
        logger.exception("Downstream spec refresh failed for owner %s", owner_user_id)
