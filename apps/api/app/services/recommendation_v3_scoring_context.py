"""P62 — batch-loaded P61 demand context for Recommendation V3 preview."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.demand_intelligence import (
    DemandVelocitySnapshot,
    IssueDemandObservation,
    IssueDemandSnapshot,
    SpecOpportunityRow,
    SpecOpportunitySnapshot,
)
from app.models.external_catalog import ExternalCatalogMatch
from app.services.external_catalog.crosswalk import MATCH_MATCHED
from app.services.spec_opportunity_service import get_latest_spec_snapshot

P62_DEMAND_STALE_HOURS = 36
P62_V3_PRIMARY_VELOCITY_WINDOW = 7


@dataclass(frozen=True)
class IssueDemandIntelStatus:
    release_issue_id: int
    status: str
    external_issue_id: int | None = None
    demand_refreshed_at: datetime | None = None
    trend_label: str | None = None
    observation_count_28d: int = 0


@dataclass(frozen=True)
class RecommendationV3ReadinessDiagnostic:
    ready: bool
    reason_codes: tuple[str, ...] = ()
    demand_snapshot_count: int = 0
    velocity_snapshot_count: int = 0
    spec_snapshot_present: bool = False
    spec_row_count: int = 0
    demand_median_age_hours: float | None = None


@dataclass
class RecommendationV3ScoringContext:
    owner_user_id: int
    demand_by_release_issue_id: dict[int, IssueDemandSnapshot] = field(default_factory=dict)
    demand_by_external_issue_id: dict[int, IssueDemandSnapshot] = field(default_factory=dict)
    velocity_by_release_issue_id: dict[int, DemandVelocitySnapshot] = field(default_factory=dict)
    velocity_by_external_issue_id: dict[int, DemandVelocitySnapshot] = field(default_factory=dict)
    spec_by_release_issue_id: dict[int, SpecOpportunityRow] = field(default_factory=dict)
    external_id_by_release_issue_id: dict[int, int] = field(default_factory=dict)
    observation_depth_by_external_issue_id: dict[int, int] = field(default_factory=dict)
    issue_status_by_release_issue_id: dict[int, IssueDemandIntelStatus] = field(default_factory=dict)
    readiness: RecommendationV3ReadinessDiagnostic = field(
        default_factory=lambda: RecommendationV3ReadinessDiagnostic(ready=False)
    )

    def demand_for_issue(self, release_issue_id: int) -> IssueDemandSnapshot | None:
        row = self.demand_by_release_issue_id.get(release_issue_id)
        if row is not None:
            return row
        ext = self.external_id_by_release_issue_id.get(release_issue_id)
        if ext is not None:
            return self.demand_by_external_issue_id.get(ext)
        return None

    def velocity_for_issue(self, release_issue_id: int) -> DemandVelocitySnapshot | None:
        row = self.velocity_by_release_issue_id.get(release_issue_id)
        if row is not None:
            return row
        ext = self.external_id_by_release_issue_id.get(release_issue_id)
        if ext is not None:
            return self.velocity_by_external_issue_id.get(ext)
        return None

    def spec_for_issue(self, release_issue_id: int) -> SpecOpportunityRow | None:
        return self.spec_by_release_issue_id.get(release_issue_id)

    def status_for_issue(self, release_issue_id: int) -> IssueDemandIntelStatus:
        return self.issue_status_by_release_issue_id.get(
            release_issue_id,
            IssueDemandIntelStatus(release_issue_id=release_issue_id, status="NOT_MATCHED"),
        )


def _median_age_hours(rows: list[IssueDemandSnapshot]) -> float | None:
    if not rows:
        return None
    now = datetime.now(timezone.utc)
    ages = []
    for row in rows:
        ts = row.refreshed_at
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        ages.append((now - ts).total_seconds() / 3600.0)
    ages.sort()
    mid = len(ages) // 2
    return round(ages[mid], 2)


def build_recommendation_v3_readiness(
    _session: Session | None,
    *,
    owner_user_id: int,
    demand_rows: list[IssueDemandSnapshot],
    velocity_count: int,
    spec_snapshot: SpecOpportunitySnapshot | None,
    spec_rows: list[SpecOpportunityRow],
) -> RecommendationV3ReadinessDiagnostic:
    reasons: list[str] = []
    if not demand_rows:
        reasons.append("NO_DEMAND_SNAPSHOTS")
    if velocity_count <= 0:
        reasons.append("NO_VELOCITY_SNAPSHOTS")
    if spec_snapshot is None:
        reasons.append("NO_SPEC_OPPORTUNITY_SNAPSHOT")
    median_age = _median_age_hours(demand_rows)
    if median_age is not None and median_age > P62_DEMAND_STALE_HOURS:
        reasons.append("STALE_DEMAND")
    ready = bool(demand_rows) and velocity_count > 0 and "STALE_DEMAND" not in reasons
    return RecommendationV3ReadinessDiagnostic(
        ready=ready,
        reason_codes=tuple(reasons),
        demand_snapshot_count=len(demand_rows),
        velocity_snapshot_count=velocity_count,
        spec_snapshot_present=spec_snapshot is not None,
        spec_row_count=len(spec_rows),
        demand_median_age_hours=median_age,
    )


def build_recommendation_v3_scoring_context(
    session: Session,
    *,
    owner_user_id: int,
    issue_ids: list[int],
) -> RecommendationV3ScoringContext:
    issue_id_set = sorted({iid for iid in issue_ids if iid > 0})
    ctx = RecommendationV3ScoringContext(owner_user_id=owner_user_id)

    if issue_id_set:
        for row in session.exec(
            select(IssueDemandSnapshot).where(IssueDemandSnapshot.release_issue_id.in_(issue_id_set))
        ).all():
            if row.release_issue_id is not None:
                ctx.demand_by_release_issue_id[int(row.release_issue_id)] = row
            ctx.demand_by_external_issue_id[int(row.external_issue_id)] = row

        match_stmt = select(ExternalCatalogMatch).where(
            ExternalCatalogMatch.release_issue_id.in_(issue_id_set),
            ExternalCatalogMatch.match_status == MATCH_MATCHED,
        )
        for match in session.exec(match_stmt).all():
            if match.release_issue_id is not None:
                ctx.external_id_by_release_issue_id[int(match.release_issue_id)] = int(match.external_issue_id)

        external_ids = sorted(set(ctx.external_id_by_release_issue_id.values()))
        missing_ext = [eid for eid in external_ids if eid not in ctx.demand_by_external_issue_id]
        if missing_ext:
            for row in session.exec(
                select(IssueDemandSnapshot).where(IssueDemandSnapshot.external_issue_id.in_(missing_ext))
            ).all():
                ctx.demand_by_external_issue_id[int(row.external_issue_id)] = row

        vel_stmt = select(DemandVelocitySnapshot).where(
            DemandVelocitySnapshot.window_days == P62_V3_PRIMARY_VELOCITY_WINDOW,
            DemandVelocitySnapshot.release_issue_id.in_(issue_id_set),
        )
        for vel in session.exec(vel_stmt).all():
            if vel.release_issue_id is not None:
                ctx.velocity_by_release_issue_id[int(vel.release_issue_id)] = vel
            ctx.velocity_by_external_issue_id[int(vel.external_issue_id)] = vel

        if external_ids:
            for vel in session.exec(
                select(DemandVelocitySnapshot).where(
                    DemandVelocitySnapshot.window_days == P62_V3_PRIMARY_VELOCITY_WINDOW,
                    DemandVelocitySnapshot.external_issue_id.in_(external_ids),
                )
            ).all():
                if vel.release_issue_id is not None and int(vel.release_issue_id) not in ctx.velocity_by_release_issue_id:
                    ctx.velocity_by_release_issue_id[int(vel.release_issue_id)] = vel
                ctx.velocity_by_external_issue_id[int(vel.external_issue_id)] = vel

        cutoff = datetime.now(timezone.utc) - timedelta(days=28)
        if external_ids:
            for ext_id, count in session.exec(
                select(IssueDemandObservation.external_issue_id, func.count())
                .where(
                    IssueDemandObservation.external_issue_id.in_(external_ids),
                    IssueDemandObservation.observed_at >= cutoff,
                )
                .group_by(IssueDemandObservation.external_issue_id)
            ).all():
                ctx.observation_depth_by_external_issue_id[int(ext_id)] = int(count)

    spec_snapshot = get_latest_spec_snapshot(session, owner_user_id=owner_user_id)
    spec_rows: list[SpecOpportunityRow] = []
    if spec_snapshot is not None and spec_snapshot.id is not None and issue_id_set:
        spec_rows = list(
            session.exec(
                select(SpecOpportunityRow).where(
                    SpecOpportunityRow.snapshot_id == int(spec_snapshot.id),
                    SpecOpportunityRow.release_issue_id.in_(issue_id_set),
                )
            ).all()
        )
        for row in spec_rows:
            ctx.spec_by_release_issue_id[int(row.release_issue_id)] = row

    now = datetime.now(timezone.utc)
    stale_cutoff = now - timedelta(hours=P62_DEMAND_STALE_HOURS)
    for iid in issue_id_set:
        demand = ctx.demand_for_issue(iid)
        velocity = ctx.velocity_for_issue(iid)
        ext = ctx.external_id_by_release_issue_id.get(iid)
        obs = ctx.observation_depth_by_external_issue_id.get(ext or 0, 0) if ext else 0
        status = "NOT_MATCHED"
        refreshed_at = None
        if demand is not None:
            refreshed_at = demand.refreshed_at
            ts = refreshed_at if refreshed_at.tzinfo else refreshed_at.replace(tzinfo=timezone.utc)
            if ts < stale_cutoff:
                status = "STALE"
            else:
                status = "MATCHED"
        ctx.issue_status_by_release_issue_id[iid] = IssueDemandIntelStatus(
            release_issue_id=iid,
            status=status,
            external_issue_id=ext,
            demand_refreshed_at=refreshed_at,
            trend_label=velocity.trend_label if velocity else None,
            observation_count_28d=obs,
        )

    global_demand_count = session.exec(select(func.count()).select_from(IssueDemandSnapshot)).one()
    global_velocity_count = session.exec(select(func.count()).select_from(DemandVelocitySnapshot)).one()
    sample_demand = list(ctx.demand_by_release_issue_id.values())
    if not sample_demand and global_demand_count:
        sample_demand = list(session.exec(select(IssueDemandSnapshot).limit(50)).all())

    ctx.readiness = build_recommendation_v3_readiness(
        session,
        owner_user_id=owner_user_id,
        demand_rows=sample_demand if sample_demand else [],
        velocity_count=int(global_velocity_count or 0),
        spec_snapshot=spec_snapshot,
        spec_rows=spec_rows,
    )
    if global_demand_count == 0:
        ctx.readiness = RecommendationV3ReadinessDiagnostic(
            ready=False,
            reason_codes=("NO_DEMAND_SNAPSHOTS",),
            demand_snapshot_count=0,
            velocity_snapshot_count=int(global_velocity_count or 0),
            spec_snapshot_present=spec_snapshot is not None,
            spec_row_count=len(spec_rows),
        )

    return ctx
