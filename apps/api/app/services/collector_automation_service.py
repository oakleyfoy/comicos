"""P65-03 Collector automation — scheduled delivery of intelligence."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models.collector_experience import (
    AUTOMATION_STATUS_FAILED,
    AUTOMATION_STATUS_RUNNING,
    AUTOMATION_STATUS_SUCCESS,
    DELIVERY_DIGEST,
    DELIVERY_IN_APP,
    AutomationRun,
    AutomationSubscription,
    utc_now,
)
from app.services.collector_narrative_service import build_collector_narratives
from app.services.collector_workspace_service import build_collector_tasks
from app.services.notification_center_service import build_notifications

KIND_WEEKLY_BRIEFING = "WEEKLY_BRIEFING"
KIND_DAILY_DIGEST = "DAILY_OPPORTUNITY_DIGEST"
KIND_FOC_REMINDER = "FOC_REMINDER"
KIND_SELL_REMINDER = "SELL_SIGNAL_REMINDER"
KIND_ACQUISITION_REMINDER = "ACQUISITION_REMINDER"

DEFAULT_SUBSCRIPTIONS = (
    (KIND_WEEKLY_BRIEFING, DELIVERY_IN_APP),
    (KIND_DAILY_DIGEST, DELIVERY_DIGEST),
    (KIND_FOC_REMINDER, DELIVERY_IN_APP),
    (KIND_SELL_REMINDER, DELIVERY_IN_APP),
    (KIND_ACQUISITION_REMINDER, DELIVERY_IN_APP),
)


def ensure_default_subscriptions(session: Session, *, owner_user_id: int) -> list[AutomationSubscription]:
    existing = list(
        session.exec(select(AutomationSubscription).where(AutomationSubscription.owner_user_id == owner_user_id)).all()
    )
    kinds = {s.automation_kind for s in existing}
    created: list[AutomationSubscription] = list(existing)
    for kind, delivery in DEFAULT_SUBSCRIPTIONS:
        if kind in kinds:
            continue
        sub = AutomationSubscription(
            owner_user_id=owner_user_id,
            automation_kind=kind,
            delivery_type=delivery,
            enabled=True,
            config_json={},
        )
        session.add(sub)
        created.append(sub)
    session.commit()
    for sub in created:
        session.refresh(sub)
    return created


def list_subscriptions(session: Session, *, owner_user_id: int) -> list[AutomationSubscription]:
    return list(
        session.exec(
            select(AutomationSubscription)
            .where(AutomationSubscription.owner_user_id == owner_user_id)
            .order_by(AutomationSubscription.automation_kind.asc())
        ).all()
    )


def list_recent_runs(session: Session, *, owner_user_id: int, limit: int = 20) -> list[AutomationRun]:
    return list(
        session.exec(
            select(AutomationRun)
            .where(AutomationRun.owner_user_id == owner_user_id)
            .order_by(AutomationRun.started_at.desc(), AutomationRun.id.desc())
            .limit(limit)
        ).all()
    )


def _start_run(
    session: Session,
    *,
    owner_user_id: int,
    kind: str,
    delivery: str,
    subscription_id: int | None,
) -> AutomationRun:
    run = AutomationRun(
        owner_user_id=owner_user_id,
        subscription_id=subscription_id,
        automation_kind=kind,
        delivery_type=delivery,
        status=AUTOMATION_STATUS_RUNNING,
        details_json={},
    )
    session.add(run)
    session.flush()
    return run


def run_automation(session: Session, *, owner_user_id: int, automation_kind: str) -> AutomationRun:
    ensure_default_subscriptions(session, owner_user_id=owner_user_id)
    sub = session.exec(
        select(AutomationSubscription)
        .where(AutomationSubscription.owner_user_id == owner_user_id)
        .where(AutomationSubscription.automation_kind == automation_kind)
    ).first()
    delivery = sub.delivery_type if sub else DELIVERY_IN_APP
    sub_id = int(sub.id or 0) if sub else None
    run = _start_run(
        session,
        owner_user_id=owner_user_id,
        kind=automation_kind,
        delivery=delivery,
        subscription_id=sub_id,
    )
    try:
        details: dict = {}
        if automation_kind == KIND_WEEKLY_BRIEFING:
            narr = build_collector_narratives(session, owner_user_id=owner_user_id)
            details["narrative_snapshot_id"] = int(narr.id or 0)
        elif automation_kind == KIND_DAILY_DIGEST:
            tasks = build_collector_tasks(session, owner_user_id=owner_user_id)
            notif = build_notifications(session, owner_user_id=owner_user_id)
            details["task_snapshot_id"] = int(tasks.id or 0)
            details["notification_snapshot_id"] = int(notif.id or 0)
        elif automation_kind in (KIND_FOC_REMINDER, KIND_SELL_REMINDER, KIND_ACQUISITION_REMINDER):
            notif = build_notifications(session, owner_user_id=owner_user_id)
            details["notification_snapshot_id"] = int(notif.id or 0)
            details["reminder_kind"] = automation_kind
        else:
            raise ValueError(f"unknown automation_kind: {automation_kind}")
        run.status = AUTOMATION_STATUS_SUCCESS
        run.finished_at = datetime.now(timezone.utc)
        run.details_json = details
    except Exception as exc:  # noqa: BLE001 — record automation failure
        run.status = AUTOMATION_STATUS_FAILED
        run.finished_at = datetime.now(timezone.utc)
        run.details_json = {"error": str(exc)}
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def run_all_enabled_automations(session: Session, *, owner_user_id: int) -> list[AutomationRun]:
    subs = list_subscriptions(session, owner_user_id=owner_user_id)
    runs: list[AutomationRun] = []
    for sub in subs:
        if not sub.enabled:
            continue
        runs.append(run_automation(session, owner_user_id=owner_user_id, automation_kind=sub.automation_kind))
    return runs
