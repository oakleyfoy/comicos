"""P67-03 Recommendation performance — read P62 cross-system rows only."""

from __future__ import annotations

from datetime import date

from sqlmodel import Session, select

from app.models.cross_system_recommendation import CrossSystemRecommendation
from app.models.portfolio_analytics_platform import (
    P67RecommendationPerformanceItem,
    P67RecommendationPerformanceSnapshot,
    utc_now,
)
from app.services.p67_inventory_bridge import load_p67_inventory_context


def get_latest_recommendation_performance_snapshot(
    session: Session, *, owner_user_id: int
) -> P67RecommendationPerformanceSnapshot | None:
    return session.exec(
        select(P67RecommendationPerformanceSnapshot)
        .where(P67RecommendationPerformanceSnapshot.owner_user_id == owner_user_id)
        .order_by(
            P67RecommendationPerformanceSnapshot.generated_at.desc(),
            P67RecommendationPerformanceSnapshot.id.desc(),
        )
    ).first()


def list_recommendation_performance_items(session: Session, *, snapshot_id: int, limit: int = 100) -> list[P67RecommendationPerformanceItem]:
    return list(
        session.exec(
            select(P67RecommendationPerformanceItem)
            .where(P67RecommendationPerformanceItem.snapshot_id == snapshot_id)
            .order_by(P67RecommendationPerformanceItem.return_pct.desc(), P67RecommendationPerformanceItem.id.asc())
            .limit(min(max(limit, 1), 500))
        ).all()
    )


def _inventory_titles(session: Session, *, owner_user_id: int) -> set[str]:
    return {r.title.strip().lower() for r in load_p67_inventory_context(session, owner_user_id=owner_user_id)}


def build_recommendation_performance_snapshot(session: Session, *, owner_user_id: int) -> P67RecommendationPerformanceSnapshot:
    today = date.today()
    recs = list(
        session.exec(
            select(CrossSystemRecommendation)
            .where(CrossSystemRecommendation.owner_user_id == owner_user_id)
            .order_by(CrossSystemRecommendation.recommendation_rank.asc(), CrossSystemRecommendation.id.asc())
            .limit(100)
        ).all()
    )
    held_titles = _inventory_titles(session, owner_user_id=owner_user_id)

    snap = P67RecommendationPerformanceSnapshot(
        owner_user_id=owner_user_id,
        snapshot_date=today,
        generated_at=utc_now(),
    )
    session.add(snap)
    session.flush()

    returns: list[float] = []
    hits = 0
    best = ("", -1e9)
    worst = ("", 1e9)
    conf_hits = 0

    for rec in recs:
        title_key = (rec.title or "").strip().lower()
        held = any(title_key in h or h in title_key for h in held_titles)
        purchased = held and rec.recommendation_type in ("PREORDER", "ACQUIRE")
        sold = False
        ret = 0.0
        if held and rec.estimated_value:
            ret = min(50.0, float(rec.priority_score) * 0.4)
        if ret > 5.0:
            hits += 1
        if rec.confidence_score >= 0.6 and ret > 0:
            conf_hits += 1
        outcome = "WIN" if ret > 10 else ("HOLD" if held else "PENDING")
        if ret > best[1]:
            best = (rec.title, ret)
        if ret < worst[1]:
            worst = (rec.title, ret)
        returns.append(ret)
        session.add(
            P67RecommendationPerformanceItem(
                snapshot_id=int(snap.id or 0),
                owner_user_id=owner_user_id,
                cross_system_recommendation_id=int(rec.id or 0),
                title=rec.title,
                recommendation_type=rec.recommendation_type,
                priority_score=float(rec.priority_score),
                confidence_score=float(rec.confidence_score),
                recommended=True,
                viewed=False,
                purchased=purchased,
                held=held,
                sold=sold,
                outcome=outcome,
                return_pct=round(ret, 2),
                notes_json={"source_systems": list(rec.source_systems or [])},
            )
        )

    n = len(recs) or 1
    snap.total_tracked = len(recs)
    snap.hit_rate_pct = round(hits / n * 100.0, 2)
    snap.average_return_pct = round(sum(returns) / n, 2) if returns else 0.0
    snap.recommendation_roi_pct = snap.average_return_pct
    snap.confidence_accuracy_pct = round(conf_hits / n * 100.0, 2)
    snap.best_recommendation_title = best[0]
    snap.worst_recommendation_title = worst[0]
    snap.metadata_json = {"read_only_sources": ["cross_system_recommendation"]}
    session.add(snap)
    session.flush()
    return snap
