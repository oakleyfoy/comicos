"""P61-02 Demand Velocity Engine."""

from __future__ import annotations

from datetime import timedelta

from sqlmodel import Session, select

from app.models.demand_intelligence import (
    P61_SOURCE_VERSION,
    TREND_FALLING,
    TREND_INSUFFICIENT,
    TREND_RISING,
    TREND_STABLE,
    DemandVelocitySnapshot,
    IssueDemandObservation,
    IssueDemandSnapshot,
    utc_now,
)


def _trend_label(delta: float) -> str:
    if delta >= 5.0:
        return TREND_RISING
    if delta <= -5.0:
        return TREND_FALLING
    return TREND_STABLE


def _observation_at_or_before(
    session: Session,
    *,
    external_issue_id: int,
    cutoff,
) -> IssueDemandObservation | None:
    return session.exec(
        select(IssueDemandObservation)
        .where(
            IssueDemandObservation.external_issue_id == external_issue_id,
            IssueDemandObservation.observed_at <= cutoff,
        )
        .order_by(IssueDemandObservation.observed_at.desc())
    ).first()


def compute_demand_velocity(
    session: Session,
    *,
    window_days: int = 7,
) -> int:
    now = utc_now()
    cutoff = now - timedelta(days=window_days)
    snapshots = session.exec(select(IssueDemandSnapshot)).all()
    updated = 0
    for snap in snapshots:
        ext_id = int(snap.external_issue_id)
        prior = _observation_at_or_before(session, external_issue_id=ext_id, cutoff=cutoff)
        if prior is None:
            trend = TREND_INSUFFICIENT
            pull_delta = 0.0
            want_delta = 0.0
            score_delta = 0.0
            velocity = 50.0
            accel = 0.0
            conf = 0.25
        else:
            pull_delta = float((snap.pull_count or 0) - (prior.pull_count or 0))
            want_delta = float((snap.want_count or 0) - (prior.want_count or 0))
            score_delta = float(snap.community_demand_score) - float(prior.community_demand_score)
            velocity = round(min(100.0, max(0.0, 50.0 + score_delta * 2.0 + pull_delta * 0.05)), 2)
            accel = round(score_delta / max(window_days, 1), 4)
            trend = _trend_label(score_delta)
            conf = 0.75 if abs(score_delta) > 0.5 else 0.55

        existing = session.exec(
            select(DemandVelocitySnapshot).where(
                DemandVelocitySnapshot.external_issue_id == ext_id,
                DemandVelocitySnapshot.window_days == window_days,
            )
        ).first()
        payload = {
            "release_issue_id": snap.release_issue_id,
            "pull_delta": pull_delta,
            "want_delta": want_delta,
            "combined_score_delta": score_delta,
            "velocity_score": velocity,
            "acceleration_score": accel,
            "trend_label": trend,
            "confidence_score": conf,
            "source_version": P61_SOURCE_VERSION,
            "computed_at": now,
        }
        if existing:
            for k, v in payload.items():
                setattr(existing, k, v)
            session.add(existing)
        else:
            session.add(
                DemandVelocitySnapshot(
                    external_issue_id=ext_id,
                    window_days=window_days,
                    **payload,
                )
            )
        updated += 1
    session.commit()
    return updated


def list_velocity_snapshots(
    session: Session,
    *,
    window_days: int = 7,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[DemandVelocitySnapshot], int]:
    rows = session.exec(
        select(DemandVelocitySnapshot)
        .where(DemandVelocitySnapshot.window_days == window_days)
        .order_by(DemandVelocitySnapshot.velocity_score.desc(), DemandVelocitySnapshot.id.desc())
    ).all()
    total = len(rows)
    return rows[offset : offset + limit], total


def count_velocity_snapshots(session: Session) -> int:
    from sqlalchemy import func

    return int(session.exec(select(func.count()).select_from(DemandVelocitySnapshot)).one())
