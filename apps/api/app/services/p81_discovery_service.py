"""P81-01 discovery feed, registry, and dashboard."""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.p81_discovery import P81DiscoveryOpportunity, P81DiscoverySnapshot, utc_now
from app.schemas.p81_discovery import (
    P81DiscoveryDashboardRead,
    P81DiscoveryFeedRead,
    P81DiscoveryOpportunityListResponse,
    P81DiscoveryOpportunityRead,
)
from app.services.p81_discovery_ingestion import ingest_discovery_opportunities


def _to_read(row: P81DiscoveryOpportunity) -> P81DiscoveryOpportunityRead:
    return P81DiscoveryOpportunityRead(
        id=int(row.id or 0),
        opportunity_type=row.opportunity_type,  # type: ignore[arg-type]
        registry_status=row.registry_status,  # type: ignore[arg-type]
        title=row.title,
        summary=row.summary,
        publisher=row.publisher,
        series_name=row.series_name,
        issue_number=row.issue_number,
        variant_label=row.variant_label,
        discovery_date=row.discovery_date,
        release_date=row.release_date,
        discovery_score=float(row.discovery_score),
        score_category=row.score_category,  # type: ignore[arg-type]
        signals=list(row.signals_json or []),
        creator_metadata=dict(row.creator_metadata_json or {}),
        source_type=row.source_type,
        release_issue_id=row.release_issue_id,
        external_catalog_issue_id=row.external_catalog_issue_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _published_rows(session: Session, *, owner_user_id: int) -> list[P81DiscoveryOpportunity]:
    rows = list(
        session.exec(
            select(P81DiscoveryOpportunity)
            .where(P81DiscoveryOpportunity.owner_user_id == owner_user_id)
            .order_by(P81DiscoveryOpportunity.discovery_score.desc(), P81DiscoveryOpportunity.updated_at.desc())
        ).all()
    )
    return [r for r in rows if r.registry_status == "PUBLISHED" or r.discovery_score >= 50]


def _persist_snapshot(session: Session, *, owner_user_id: int, rows: list[P81DiscoveryOpportunity]) -> int:
    counts: dict[str, int] = {}
    for r in rows:
        counts[r.score_category] = counts.get(r.score_category, 0) + 1
        counts[r.opportunity_type] = counts.get(r.opportunity_type, 0) + 1
    metrics = {
        "total_opportunities": len(rows),
        "must_watch": counts.get("MUST_WATCH", 0),
        "high_opportunity": counts.get("HIGH_OPPORTUNITY", 0),
        "watch": counts.get("WATCH", 0),
        "low_priority": counts.get("LOW_PRIORITY", 0),
        "avg_score": round(sum(r.discovery_score for r in rows) / max(1, len(rows)), 1),
    }
    snap = P81DiscoverySnapshot(
        owner_user_id=owner_user_id,
        snapshot_date=date.today(),
        metrics_json=metrics,
        created_at=utc_now(),
    )
    session.add(snap)
    session.flush()
    return int(snap.id or 0)


def refresh_discovery(session: Session, *, owner_user_id: int) -> int:
    return ingest_discovery_opportunities(session, owner_user_id=owner_user_id)


def list_opportunities(
    session: Session,
    *,
    owner_user_id: int,
    opportunity_type: str | None = None,
    score_category: str | None = None,
    limit: int = 50,
    offset: int = 0,
    refresh: bool = False,
) -> P81DiscoveryOpportunityListResponse:
    if refresh:
        ingest_discovery_opportunities(session, owner_user_id=owner_user_id)
    lim = max(1, min(limit, 200))
    off = max(0, offset)
    stmt = select(P81DiscoveryOpportunity).where(P81DiscoveryOpportunity.owner_user_id == owner_user_id)
    if opportunity_type:
        stmt = stmt.where(P81DiscoveryOpportunity.opportunity_type == opportunity_type.strip().upper())
    if score_category:
        stmt = stmt.where(P81DiscoveryOpportunity.score_category == score_category.strip().upper())
    rows = list(session.exec(stmt.order_by(P81DiscoveryOpportunity.discovery_score.desc(), P81DiscoveryOpportunity.id.desc())).all())
    page = [_to_read(r) for r in rows[off : off + lim]]
    return P81DiscoveryOpportunityListResponse(items=page, total_items=len(rows), limit=lim, offset=off)


def get_opportunity(session: Session, *, owner_user_id: int, opportunity_id: int) -> P81DiscoveryOpportunityRead:
    row = session.get(P81DiscoveryOpportunity, opportunity_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Discovery opportunity not found.")
    return _to_read(row)


def build_discovery_feed(session: Session, *, owner_user_id: int, refresh: bool = True) -> P81DiscoveryFeedRead:
    if refresh:
        ingest_discovery_opportunities(session, owner_user_id=owner_user_id)
    rows = _published_rows(session, owner_user_id=owner_user_id)
    reads = [_to_read(r) for r in rows]
    snap_id = _persist_snapshot(session, owner_user_id=owner_user_id, rows=rows)
    by_score = sorted(reads, key=lambda x: x.discovery_score, reverse=True)
    return P81DiscoveryFeedRead(
        new_discoveries=sorted(reads, key=lambda x: x.discovery_date, reverse=True)[:12],
        top_opportunities=by_score[:10],
        new_number_ones=[r for r in reads if r.opportunity_type in {"NEW_1", "NEW_SERIES"}][:12],
        milestone_issues=[r for r in reads if r.opportunity_type == "MILESTONE"][:12],
        creator_projects=[r for r in reads if r.opportunity_type == "CREATOR_PROJECT"][:12],
        new_variants=[r for r in reads if r.opportunity_type == "VARIANT_EXPANSION"][:12],
        snapshot_id=snap_id,
    )


def build_discovery_dashboard(session: Session, *, owner_user_id: int, refresh: bool = False) -> P81DiscoveryDashboardRead:
    if refresh:
        ingest_discovery_opportunities(session, owner_user_id=owner_user_id)
    rows = _published_rows(session, owner_user_id=owner_user_id)
    reads = [_to_read(r) for r in rows]
    snap_id = _persist_snapshot(session, owner_user_id=owner_user_id, rows=rows) if refresh else None
    recent = sorted(reads, key=lambda x: x.created_at, reverse=True)[:15]
    return P81DiscoveryDashboardRead(
        must_watch=[r for r in reads if r.score_category == "MUST_WATCH"][:20],
        high_opportunity=[r for r in reads if r.score_category == "HIGH_OPPORTUNITY"][:20],
        watch=[r for r in reads if r.score_category == "WATCH"][:20],
        recently_added=recent,
        counts={
            "must_watch": sum(1 for r in reads if r.score_category == "MUST_WATCH"),
            "high_opportunity": sum(1 for r in reads if r.score_category == "HIGH_OPPORTUNITY"),
            "watch": sum(1 for r in reads if r.score_category == "WATCH"),
            "total": len(reads),
        },
        snapshot_id=snap_id,
    )
