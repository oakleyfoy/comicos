"""P64 Collector Assistant certification."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, func, select

from app.models.buy_queue_intelligence import BuyQueueSnapshot
from app.models.collector_assistant import RUN_STATUS_SUCCESS, CollectorAssistantRun
from app.models.market_intelligence_platform import PortfolioPerformanceSnapshot
from app.services.collector_assistant_orchestrator import (
    get_latest_briefing,
    get_latest_executive,
    get_latest_run,
    list_all_recommendations_for_run,
    run_collector_assistant_build,
)
from app.services.p64_feature_flags import p64_collector_assistant_enabled


def _component(component: str, ok: bool, notes: list[str]) -> dict:
    return {
        "component": component,
        "certified": ok and p64_collector_assistant_enabled(),
        "status": "PASS" if ok else "NOT_READY",
        "summary": f"{component} certified" if ok else f"{component} not ready",
        "notes": notes,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def get_collector_assistant_platform_certification(session: Session, *, owner_user_id: int) -> dict:
    notes: list[str] = []
    bq_before = session.exec(select(func.count()).select_from(BuyQueueSnapshot)).one()
    p63_before = session.exec(select(func.count()).select_from(PortfolioPerformanceSnapshot)).one()

    run = run_collector_assistant_build(session, owner_user_id=owner_user_id, scope="full")
    bq_after = session.exec(select(func.count()).select_from(BuyQueueSnapshot)).one()
    p63_after = session.exec(select(func.count()).select_from(PortfolioPerformanceSnapshot)).one()
    no_mutation = bq_before == bq_after and p63_before == p63_after
    notes.append(f"upstream_unchanged={no_mutation}")

    ok_run = run.status == RUN_STATUS_SUCCESS
    briefing = get_latest_briefing(session, owner_user_id=owner_user_id)
    ok_brief = briefing is not None and briefing.readiness_status == RUN_STATUS_SUCCESS and bool(briefing.briefing_json)
    lanes = list_all_recommendations_for_run(session, run_id=int(run.id or 0)) if ok_run else {}
    ok_lanes = ok_run and any(len(v) > 0 for v in lanes.values())
    if ok_lanes:
        for lane, items in lanes.items():
            if len(items) > 1 and not all(items[i].priority_score >= items[i + 1].priority_score for i in range(len(items) - 1)):
                ok_lanes = False
                notes.append(f"lane_order_fail:{lane}")
    executive = get_latest_executive(session, owner_user_id=owner_user_id)
    ok_exec = executive is not None and executive.platform_ready

    briefing_c = _component("P64_BRIEFING", ok_brief and ok_run, notes + [f"run_status={run.status}"])
    lanes_c = _component("P64_LANES", ok_lanes, notes)
    exec_c = _component("P64_EXECUTIVE", ok_exec, notes)
    mut_c = _component("P64_NON_MUTATION", no_mutation, notes)

    ready = all(c["certified"] for c in (briefing_c, lanes_c, exec_c, mut_c)) and ok_run
    return {
        "platform_ready": ready,
        "briefing": briefing_c,
        "lanes": lanes_c,
        "executive": exec_c,
        "non_mutation": mut_c,
        "run_id": int(run.id or 0),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
