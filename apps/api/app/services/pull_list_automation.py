from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlmodel import Session, select

from app.models.pull_list import PullList, PullListAutomationRun, PullListIssue
from app.models.release_intelligence import ReleaseIssue
from app.models.recommendation_v2 import RecommendationScoreV2
from app.services.foc_dashboard import get_foc_dashboard
from app.services.foc_dates import utc_today
from app.services.pull_list import sync_pull_list_issue_action_states
from app.services.pull_list_decisions import generate_pull_list_decisions
from app.services.recommendation_v2_engine import _latest_scores_by_issue

logger = logging.getLogger(__name__)

AUTOMATION_STATUS_SUCCESS = "SUCCESS"
AUTOMATION_STATUS_FAILED = "FAILED"
AUTOMATION_STATUS_PARTIAL = "PARTIAL"


@dataclass(frozen=True)
class OwnerRefreshResult:
    owner_user_id: int
    releases_processed: int
    decisions_created: int
    actions_generated: int
    issue_states_updated: int
    error: str | None = None


def _collect_owner_ids(session: Session) -> list[int]:
    owner_ids: set[int] = set()
    for owner_user_id in session.exec(select(ReleaseIssue.owner_user_id).distinct()).all():
        owner_ids.add(int(owner_user_id))
    for owner_user_id in session.exec(select(PullList.owner_user_id).distinct()).all():
        owner_ids.add(int(owner_user_id))
    for owner_user_id in session.exec(select(RecommendationScoreV2.owner_user_id).distinct()).all():
        owner_ids.add(int(owner_user_id))
    return sorted(owner_ids)


def _count_releases_for_owner(session: Session, *, owner_user_id: int) -> int:
    return len(session.exec(select(ReleaseIssue.id).where(ReleaseIssue.owner_user_id == owner_user_id)).all())


def refresh_owner_pull_list(
    session: Session,
    *,
    owner_user_id: int,
    today: date | None = None,
) -> OwnerRefreshResult:
    """Deterministic per-owner pipeline steps 1–6 (read-only on releases and recommendations)."""
    ref = today or utc_today()
    releases_processed = _count_releases_for_owner(session, owner_user_id=owner_user_id)
    try:
        _ = _latest_scores_by_issue(session, owner_user_id=owner_user_id)
        _ = session.exec(select(PullList).where(PullList.owner_user_id == owner_user_id)).all()
        decisions_created = generate_pull_list_decisions(session, owner_user_id=owner_user_id)
        issue_states_updated = sync_pull_list_issue_action_states(
            session, owner_user_id=owner_user_id, today=ref
        )
        dashboard = get_foc_dashboard(session, owner_user_id=owner_user_id, today=ref)
        actions_generated = dashboard.summary.action_required_count + dashboard.summary.upcoming_foc_count
        return OwnerRefreshResult(
            owner_user_id=owner_user_id,
            releases_processed=releases_processed,
            decisions_created=decisions_created,
            actions_generated=actions_generated,
            issue_states_updated=issue_states_updated,
        )
    except Exception as exc:  # noqa: BLE001 — record per-owner failure without aborting platform run
        logger.exception("Pull list refresh failed for owner %s", owner_user_id)
        session.rollback()
        return OwnerRefreshResult(
            owner_user_id=owner_user_id,
            releases_processed=releases_processed,
            decisions_created=0,
            actions_generated=0,
            issue_states_updated=0,
            error=str(exc),
        )


def run_pull_list_refresh(
    session: Session,
    *,
    today: date | None = None,
    owner_user_ids: list[int] | None = None,
) -> PullListAutomationRun:
    """Platform pull-list refresh: decisions, FOC states, and action queue materialization."""
    started = datetime.now(timezone.utc)
    run = PullListAutomationRun(status=AUTOMATION_STATUS_SUCCESS, started_at=started)
    session.add(run)
    session.commit()
    session.refresh(run)

    owners = owner_user_ids if owner_user_ids is not None else _collect_owner_ids(session)
    total_releases = 0
    total_decisions = 0
    total_actions = 0
    failures: list[str] = []

    try:
        for owner_id in owners:
            result = refresh_owner_pull_list(session, owner_user_id=owner_id, today=today)
            total_releases += result.releases_processed
            total_decisions += result.decisions_created
            total_actions += result.actions_generated
            if result.error:
                failures.append(f"owner={owner_id}: {result.error}")

        if failures and len(failures) < len(owners):
            run.status = AUTOMATION_STATUS_PARTIAL
            run.error_message = "; ".join(failures[:20])
        elif failures:
            run.status = AUTOMATION_STATUS_FAILED
            run.error_message = "; ".join(failures[:20])
        else:
            run.status = AUTOMATION_STATUS_SUCCESS
            run.error_message = ""

        run.owners_processed = len(owners)
        run.releases_processed = total_releases
        run.decisions_created = total_decisions
        run.actions_generated = total_actions
    except Exception as exc:  # noqa: BLE001
        logger.exception("Pull list refresh run failed")
        session.rollback()
        run = session.get(PullListAutomationRun, int(run.id or 0))
        if run is None:
            raise
        run.status = AUTOMATION_STATUS_FAILED
        run.error_message = str(exc)
        run.owners_processed = len(owners)
        run.releases_processed = total_releases
        run.decisions_created = total_decisions
        run.actions_generated = total_actions
    finally:
        completed = datetime.now(timezone.utc)
        run.completed_at = completed
        run.runtime_ms = max(0, int((completed - started).total_seconds() * 1000))
        session.add(run)
        session.commit()
        session.refresh(run)

    return run
