"""P71-01 Exit recommendation engine."""

from __future__ import annotations

from datetime import date

from sqlmodel import Session, select

from app.models.sell_intelligence_platform import P71ExitRecommendationItem, P71ExitRecommendationSnapshot, utc_now
from app.services.p71_sell_context import load_sell_intel_contexts
from app.services.p71_sell_scoring import score_exit


def get_latest_exit_recommendation_snapshot(session: Session, *, owner_user_id: int) -> P71ExitRecommendationSnapshot | None:
    return session.exec(
        select(P71ExitRecommendationSnapshot)
        .where(P71ExitRecommendationSnapshot.owner_user_id == owner_user_id)
        .order_by(P71ExitRecommendationSnapshot.generated_at.desc(), P71ExitRecommendationSnapshot.id.desc())
    ).first()


def list_exit_recommendation_items(session: Session, *, snapshot_id: int, limit: int = 200) -> list[P71ExitRecommendationItem]:
    return list(
        session.exec(
            select(P71ExitRecommendationItem)
            .where(P71ExitRecommendationItem.snapshot_id == snapshot_id)
            .order_by(P71ExitRecommendationItem.exit_score.desc(), P71ExitRecommendationItem.id.asc())
            .limit(min(max(limit, 1), 500))
        ).all()
    )


def build_exit_recommendation_snapshot(session: Session, *, owner_user_id: int) -> P71ExitRecommendationSnapshot:
    today = date.today()
    contexts = load_sell_intel_contexts(session, owner_user_id=owner_user_id)
    snap = P71ExitRecommendationSnapshot(
        owner_user_id=owner_user_id,
        snapshot_date=today,
        generated_at=utc_now(),
        metadata_json={"source": "P61-P69_read_only"},
    )
    session.add(snap)
    session.flush()

    items: list[P71ExitRecommendationItem] = []
    for ctx in contexts:
        if ctx.estimated_fmv <= 0 and ctx.cost_basis <= 0:
            continue
        action, escore, conf, primary, secondary, factors = score_exit(ctx)
        items.append(
            P71ExitRecommendationItem(
                snapshot_id=int(snap.id or 0),
                owner_user_id=owner_user_id,
                inventory_copy_id=ctx.copy_id,
                title=ctx.title,
                publisher=ctx.publisher,
                issue_number=ctx.issue_number,
                recommendation=action,
                exit_score=escore,
                exit_confidence=conf,
                primary_reason=primary,
                secondary_reasons=secondary,
                factors_json=factors,
            )
        )
    for it in items:
        session.add(it)
    snap.total_items = len(items)
    session.add(snap)
    session.flush()
    return snap
