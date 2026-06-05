"""P61-01 Demand Refresh Engine."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.collector_market_intelligence import MarketDemandProfile
from app.models.demand_intelligence import (
    P61_SOURCE_VERSION,
    REFRESH_STATUS_FAILED,
    REFRESH_STATUS_SUCCESS,
    DemandRefreshRun,
    IssueDemandObservation,
    IssueDemandSnapshot,
    utc_now,
)
from app.models.external_catalog import ExternalCatalogIssue, ExternalCatalogMatch
from app.services.external_catalog.crosswalk import MATCH_MATCHED
from app.services.external_catalog.decision_signals import _demand_score
from app.services.external_catalog.league_of_comic_geeks import LOCG_SOURCE_NAME
from app.services.external_catalog.sync_service import refresh_upcoming_signals
from app.services.demand_velocity_service import count_velocity_snapshots
from app.services.market_demand_engine import market_demand_score, refresh_market_demand


def _entity_rollup_for_series(session: Session, *, series_name: str, publisher: str) -> float:
    needle = (series_name or "").strip().lower()
    if not needle:
        return 50.0
    profiles = session.exec(select(MarketDemandProfile).limit(500)).all()
    best = 50.0
    for profile in profiles:
        name = (profile.entity_name or "").lower()
        if needle in name or name in needle:
            best = max(best, float(profile.demand_score))
    pub = (publisher or "").strip().lower()
    if pub:
        pub_score = market_demand_score(session, entity_type="FRANCHISE", entity_name=publisher)
        best = max(best, pub_score)
    return round(min(best, 100.0), 2)


def _upsert_issue_snapshot(
    session: Session,
    *,
    issue: ExternalCatalogIssue,
    release_issue_id: int | None,
    entity_rollup: float,
) -> IssueDemandSnapshot:
    community, parts = _demand_score(issue.pull_count, issue.want_count)
    combined = round(min(100.0, community * 0.72 + entity_rollup * 0.28), 2)
    conf = 0.85 if issue.pull_count is not None and issue.want_count is not None else 0.45
    now = utc_now()
    existing = session.exec(
        select(IssueDemandSnapshot).where(
            IssueDemandSnapshot.source_name == issue.source_name,
            IssueDemandSnapshot.external_issue_id == int(issue.id or 0),
        )
    ).first()
    payload = {
        "release_issue_id": release_issue_id,
        "title": issue.title,
        "pull_count": issue.pull_count,
        "want_count": issue.want_count,
        "community_demand_score": community,
        "entity_rollup_score": entity_rollup,
        "combined_demand_score": combined,
        "confidence_score": conf,
        "signal_sources_json": {
            "sources": ["LOCG_PULL_WANT", "P51_ENTITY_ROLLUP"],
            "demand_components": parts,
        },
        "source_version": P61_SOURCE_VERSION,
        "refreshed_at": now,
    }
    if existing:
        for key, val in payload.items():
            setattr(existing, key, val)
        session.add(existing)
        row = existing
    else:
        row = IssueDemandSnapshot(
            source_name=issue.source_name,
            external_issue_id=int(issue.id or 0),
            **payload,
        )
        session.add(row)
    session.flush()
    session.add(
        IssueDemandObservation(
            external_issue_id=int(issue.id or 0),
            release_issue_id=release_issue_id,
            pull_count=issue.pull_count,
            want_count=issue.want_count,
            community_demand_score=community,
        )
    )
    return row


def _resolve_release_id(
    session: Session,
    *,
    external_issue_id: int,
    owner_user_id: int | None,
) -> int | None:
    stmt = select(ExternalCatalogMatch).where(
        ExternalCatalogMatch.external_issue_id == external_issue_id,
        ExternalCatalogMatch.match_status == MATCH_MATCHED,
    )
    if owner_user_id is not None:
        stmt = stmt.where(ExternalCatalogMatch.owner_user_id == owner_user_id)
    match = session.exec(stmt.order_by(ExternalCatalogMatch.id.desc())).first()
    if match and match.release_issue_id:
        return int(match.release_issue_id)
    return None


def run_demand_refresh(
    session: Session,
    *,
    scope: str = "ALL",
    days_forward: int = 90,
    owner_user_id: int | None = None,
    trigger_type: str = "API_REFRESH",
    refresh_locg: bool = False,
) -> DemandRefreshRun:
    scope_u = scope.strip().upper()
    run = DemandRefreshRun(
        trigger_type=trigger_type,
        scope=scope_u,
        owner_user_id=owner_user_id,
        status="RUNNING",
    )
    session.add(run)
    session.flush()

    profiles_updated = 0
    signals_appended = 0
    issues_refreshed = 0
    details: dict = {"days_forward": days_forward}

    try:
        if scope_u in {"ALL", "ENTITY"}:
            market_result = refresh_market_demand(session)
            profiles_updated = int(market_result.get("profiles_updated", 0))
            signals_appended = int(market_result.get("signals_appended", 0))
            details["market_demand"] = market_result

        if scope_u in {"ALL", "ISSUE_UPCOMING", "ISSUE"}:
            if refresh_locg:
                locg_summary = refresh_upcoming_signals(
                    session,
                    days_forward=days_forward,
                    refresh_details=False,
                )
                details["locg_refresh"] = locg_summary
            today = date.today()
            end = today + timedelta(days=max(1, days_forward))
            issues = session.exec(
                select(ExternalCatalogIssue).where(
                    ExternalCatalogIssue.source_name == LOCG_SOURCE_NAME,
                    ExternalCatalogIssue.release_date.is_not(None),
                    ExternalCatalogIssue.release_date >= today,
                    ExternalCatalogIssue.release_date <= end,
                )
            ).all()
            for issue in issues:
                ext_id = int(issue.id or 0)
                if ext_id <= 0:
                    continue
                release_id = _resolve_release_id(session, external_issue_id=ext_id, owner_user_id=owner_user_id)
                rollup = _entity_rollup_for_series(
                    session,
                    series_name=issue.series_name,
                    publisher=issue.publisher,
                )
                _upsert_issue_snapshot(
                    session,
                    issue=issue,
                    release_issue_id=release_id,
                    entity_rollup=rollup,
                )
                issues_refreshed += 1
            session.commit()

        run.profiles_updated = profiles_updated
        run.signals_appended = signals_appended
        run.issues_refreshed = issues_refreshed
        run.status = REFRESH_STATUS_SUCCESS
        run.finished_at = utc_now()
        run.details_json = details
        session.add(run)
        session.commit()
        session.refresh(run)
        return run
    except Exception as exc:  # noqa: BLE001
        run.status = REFRESH_STATUS_FAILED
        run.finished_at = utc_now()
        run.details_json = {**details, "error": str(exc)}
        session.add(run)
        session.commit()
        session.refresh(run)
        raise


def get_latest_refresh_run(session: Session) -> DemandRefreshRun | None:
    return session.exec(select(DemandRefreshRun).order_by(DemandRefreshRun.id.desc())).first()


def list_issue_demand_snapshots(
    session: Session,
    *,
    limit: int = 50,
    offset: int = 0,
    release_issue_id: int | None = None,
    min_combined_score: float | None = None,
) -> tuple[list[IssueDemandSnapshot], int]:
    stmt = select(IssueDemandSnapshot).order_by(
        IssueDemandSnapshot.combined_demand_score.desc(),
        IssueDemandSnapshot.id.desc(),
    )
    if release_issue_id is not None:
        stmt = stmt.where(IssueDemandSnapshot.release_issue_id == release_issue_id)
    if min_combined_score is not None:
        stmt = stmt.where(IssueDemandSnapshot.combined_demand_score >= float(min_combined_score))
    rows = session.exec(stmt).all()
    total = len(rows)
    page = rows[offset : offset + limit]
    return page, total


def count_issue_snapshots(session: Session) -> int:
    return int(session.exec(select(func.count()).select_from(IssueDemandSnapshot)).one())


def build_demand_dashboard(session: Session, *, top_limit: int = 10) -> dict:
    latest = get_latest_refresh_run(session)
    top, _ = list_issue_demand_snapshots(session, limit=top_limit, offset=0)
    return {
        "latest_refresh": latest,
        "issue_snapshot_count": count_issue_snapshots(session),
        "velocity_snapshot_count": count_velocity_snapshots(session),
        "top_demand_issues": top,
    }
