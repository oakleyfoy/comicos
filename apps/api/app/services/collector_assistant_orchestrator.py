"""P64 Collector Assistant build orchestrator."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models.collector_assistant import (
    COLLECTOR_LANES,
    RUN_STATUS_NOT_READY,
    RUN_STATUS_SUCCESS,
    CollectorAssistantRun,
    CollectorBriefingSnapshot,
    CollectorExecutiveBundle,
    CollectorHealthSnapshot,
    CollectorOpportunityAlert,
    CollectorOpportunityAlertSnapshot,
    CollectorRecommendationItem,
    CollectorRecommendationSnapshot,
    ITEM_STATUS_NEW,
    utc_now,
)
from app.services.collector_assistant_context_service import load_collector_assistant_context
from app.services.collector_lane_builder_service import (
    build_alert_drafts,
    build_briefing_json,
    build_health_from_context,
    build_lane_drafts,
)
from app.services.p64_feature_flags import p64_llm_narration_enabled


def get_latest_run(session: Session, *, owner_user_id: int) -> CollectorAssistantRun | None:
    return session.exec(
        select(CollectorAssistantRun)
        .where(CollectorAssistantRun.owner_user_id == owner_user_id)
        .order_by(CollectorAssistantRun.started_at.desc(), CollectorAssistantRun.id.desc())
    ).first()


def get_latest_briefing(session: Session, *, owner_user_id: int) -> CollectorBriefingSnapshot | None:
    return session.exec(
        select(CollectorBriefingSnapshot)
        .where(CollectorBriefingSnapshot.owner_user_id == owner_user_id)
        .order_by(CollectorBriefingSnapshot.generated_at.desc(), CollectorBriefingSnapshot.id.desc())
    ).first()


def get_latest_health(session: Session, *, owner_user_id: int) -> CollectorHealthSnapshot | None:
    return session.exec(
        select(CollectorHealthSnapshot)
        .where(CollectorHealthSnapshot.owner_user_id == owner_user_id)
        .order_by(CollectorHealthSnapshot.generated_at.desc(), CollectorHealthSnapshot.id.desc())
    ).first()


def get_latest_executive(session: Session, *, owner_user_id: int) -> CollectorExecutiveBundle | None:
    return session.exec(
        select(CollectorExecutiveBundle)
        .where(CollectorExecutiveBundle.owner_user_id == owner_user_id)
        .order_by(CollectorExecutiveBundle.generated_at.desc(), CollectorExecutiveBundle.id.desc())
    ).first()


def get_latest_alert_snapshot(session: Session, *, owner_user_id: int) -> CollectorOpportunityAlertSnapshot | None:
    return session.exec(
        select(CollectorOpportunityAlertSnapshot)
        .where(CollectorOpportunityAlertSnapshot.owner_user_id == owner_user_id)
        .order_by(CollectorOpportunityAlertSnapshot.generated_at.desc(), CollectorOpportunityAlertSnapshot.id.desc())
    ).first()


def list_alerts_for_snapshot(session: Session, *, alert_snapshot_id: int) -> list[CollectorOpportunityAlert]:
    return list(
        session.exec(
            select(CollectorOpportunityAlert)
            .where(CollectorOpportunityAlert.alert_snapshot_id == alert_snapshot_id)
            .order_by(CollectorOpportunityAlert.severity.asc(), CollectorOpportunityAlert.id.asc())
        ).all()
    )


def list_lane_snapshots_for_run(session: Session, *, run_id: int) -> list[CollectorRecommendationSnapshot]:
    return list(
        session.exec(
            select(CollectorRecommendationSnapshot).where(CollectorRecommendationSnapshot.run_id == run_id)
        ).all()
    )


def list_items_for_lane_snapshot(session: Session, *, snapshot_id: int) -> list[CollectorRecommendationItem]:
    return list(
        session.exec(
            select(CollectorRecommendationItem)
            .where(CollectorRecommendationItem.snapshot_id == snapshot_id)
            .order_by(CollectorRecommendationItem.priority_score.desc(), CollectorRecommendationItem.id.asc())
        ).all()
    )


def list_all_recommendations_for_run(session: Session, *, run_id: int) -> dict[str, list[CollectorRecommendationItem]]:
    out: dict[str, list[CollectorRecommendationItem]] = {lane: [] for lane in COLLECTOR_LANES}
    for snap in list_lane_snapshots_for_run(session, run_id=run_id):
        items = list_items_for_lane_snapshot(session, snapshot_id=int(snap.id or 0))
        out[snap.lane] = items
    return out


def _persist_lanes(
    session: Session,
    *,
    run: CollectorAssistantRun,
    owner_user_id: int,
    lane_drafts: dict,
) -> dict[str, int]:
    lane_ids: dict[str, int] = {}
    for lane in COLLECTOR_LANES:
        drafts = lane_drafts.get(lane, [])
        snap = CollectorRecommendationSnapshot(
            run_id=int(run.id or 0),
            owner_user_id=owner_user_id,
            lane=lane,
            total_items=len(drafts),
            metadata_json={},
        )
        session.add(snap)
        session.flush()
        for d in drafts:
            session.add(
                CollectorRecommendationItem(
                    snapshot_id=int(snap.id or 0),
                    owner_user_id=owner_user_id,
                    lane=lane,
                    priority_score=d.priority_score,
                    confidence=d.confidence,
                    title=d.title,
                    publisher=d.publisher,
                    issue_number=d.issue_number,
                    release_issue_id=d.release_issue_id,
                    external_catalog_issue_id=d.external_catalog_issue_id,
                    inventory_copy_id=d.inventory_copy_id,
                    recommended_action=d.recommended_action,
                    reason_codes_json=d.reason_codes,
                    explanation=d.explanation,
                    provenance_json=d.provenance_json,
                    status=ITEM_STATUS_NEW,
                )
            )
        lane_ids[lane] = int(snap.id or 0)
    return lane_ids


def run_collector_assistant_build(
    session: Session,
    *,
    owner_user_id: int,
    scope: str = "full",
) -> CollectorAssistantRun:
    run = CollectorAssistantRun(owner_user_id=owner_user_id, started_at=utc_now(), steps_json={})
    session.add(run)
    session.flush()

    ctx = load_collector_assistant_context(session, owner_user_id=owner_user_id)
    run.upstream_fingerprint_json = {"fingerprint": ctx.fingerprint, "freshness": ctx.freshness}

    if not ctx.ready:
        run.status = RUN_STATUS_NOT_READY
        run.finished_at = datetime.now(timezone.utc)
        run.steps_json = {"context": RUN_STATUS_NOT_READY, "reason": ctx.readiness_reason}
        session.add(run)
        briefing = CollectorBriefingSnapshot(
            run_id=int(run.id or 0),
            owner_user_id=owner_user_id,
            week_start=datetime.now(timezone.utc).date(),
            readiness_status=RUN_STATUS_NOT_READY,
            briefing_json={"reason": ctx.readiness_reason},
            source_versions_json={},
        )
        session.add(briefing)
        health = CollectorHealthSnapshot(
            run_id=int(run.id or 0),
            owner_user_id=owner_user_id,
            readiness_status=RUN_STATUS_NOT_READY,
            health_score=0.0,
            health_band="AT_RISK",
            metrics_json={"reason": ctx.readiness_reason},
        )
        session.add(health)
        exec_row = CollectorExecutiveBundle(
            run_id=int(run.id or 0),
            owner_user_id=owner_user_id,
            readiness_status=RUN_STATUS_NOT_READY,
            platform_ready=False,
            dashboard_json={"reason": ctx.readiness_reason},
            freshness_json=ctx.freshness,
        )
        session.add(exec_row)
        session.commit()
        session.refresh(run)
        return run

    lane_drafts = build_lane_drafts(ctx)
    lane_ids: dict[str, int] = {}
    if scope in ("full", "lanes", "recommendations"):
        lane_ids = _persist_lanes(session, run=run, owner_user_id=owner_user_id, lane_drafts=lane_drafts)
        run.steps_json = {**run.steps_json, "lanes": "OK"}

    health_id: int | None = None
    if scope in ("full", "health"):
        score, band, metrics, risks = build_health_from_context(ctx)
        health = CollectorHealthSnapshot(
            run_id=int(run.id or 0),
            owner_user_id=owner_user_id,
            health_score=score,
            health_band=band,
            metrics_json=metrics,
            risk_flags_json=risks,
        )
        session.add(health)
        session.flush()
        health_id = int(health.id or 0)
        run.steps_json = {**run.steps_json, "health": "OK"}

    if scope in ("full", "alerts"):
        alert_snap = CollectorOpportunityAlertSnapshot(
            run_id=int(run.id or 0),
            owner_user_id=owner_user_id,
            metadata_json={},
        )
        session.add(alert_snap)
        session.flush()
        alert_drafts = build_alert_drafts(ctx)
        critical = 0
        for ad in alert_drafts:
            if ad["severity"] == "CRITICAL":
                critical += 1
            exp = ad.get("expires_at")
            expires = datetime.fromisoformat(exp) if isinstance(exp, str) else None
            session.add(
                CollectorOpportunityAlert(
                    alert_snapshot_id=int(alert_snap.id or 0),
                    owner_user_id=owner_user_id,
                    alert_type=ad["alert_type"],
                    severity=ad["severity"],
                    title=ad["title"],
                    message=ad["message"],
                    expires_at=expires,
                    action_deep_link=ad["action_deep_link"],
                    provenance_json=ad["provenance_json"],
                )
            )
        alert_snap.alert_count = len(alert_drafts)
        alert_snap.critical_count = critical
        session.add(alert_snap)
        run.steps_json = {**run.steps_json, "alerts": "OK"}

    if scope in ("full", "briefing"):
        bjson = build_briefing_json(ctx, run_id=int(run.id or 0), lane_snapshot_ids=lane_ids, health_id=health_id)
        md = ""
        if not p64_llm_narration_enabled():
            md = f"# {bjson.get('headline', 'Briefing')}\n"
        session.add(
            CollectorBriefingSnapshot(
                run_id=int(run.id or 0),
                owner_user_id=owner_user_id,
                week_start=datetime.fromisoformat(bjson["week_start"]).date(),
                briefing_json=bjson,
                briefing_markdown=md,
                source_versions_json={"p64": "P64-A"},
            )
        )
        run.steps_json = {**run.steps_json, "briefing": "OK"}

    if scope == "full":
        lane_totals = {lane: len(lane_drafts.get(lane, [])) for lane in COLLECTOR_LANES}
        exec_row = CollectorExecutiveBundle(
            run_id=int(run.id or 0),
            owner_user_id=owner_user_id,
            readiness_status=RUN_STATUS_SUCCESS,
            platform_ready=True,
            dashboard_json={
                "lane_totals": lane_totals,
                "lane_snapshot_ids": lane_ids,
                "health_snapshot_id": health_id,
                "headline": build_briefing_json(ctx, run_id=int(run.id or 0), lane_snapshot_ids=lane_ids, health_id=health_id).get(
                    "headline"
                ),
            },
            freshness_json=ctx.freshness,
        )
        session.add(exec_row)
        run.steps_json = {**run.steps_json, "executive": "OK"}

    run.status = RUN_STATUS_SUCCESS
    run.finished_at = datetime.now(timezone.utc)
    session.add(run)
    session.commit()
    session.refresh(run)
    return run
