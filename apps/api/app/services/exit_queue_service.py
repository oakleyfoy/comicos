"""P71-04 Prioritized exit queue."""

from __future__ import annotations

from datetime import date

from sqlmodel import Session, select

from app.models.sell_intelligence_platform import P71ExitQueueItem, P71ExitQueueSnapshot, utc_now
from app.services.exit_recommendation_service import get_latest_exit_recommendation_snapshot, list_exit_recommendation_items
from app.services.listing_intelligence_service import get_latest_listing_snapshot, list_listing_items


def get_latest_exit_queue_snapshot(session: Session, *, owner_user_id: int) -> P71ExitQueueSnapshot | None:
    return session.exec(
        select(P71ExitQueueSnapshot)
        .where(P71ExitQueueSnapshot.owner_user_id == owner_user_id)
        .order_by(P71ExitQueueSnapshot.generated_at.desc(), P71ExitQueueSnapshot.id.desc())
    ).first()


def list_exit_queue_items(session: Session, *, snapshot_id: int, limit: int = 100) -> list[P71ExitQueueItem]:
    return list(
        session.exec(
            select(P71ExitQueueItem)
            .where(P71ExitQueueItem.snapshot_id == snapshot_id)
            .order_by(P71ExitQueueItem.priority.asc(), P71ExitQueueItem.id.asc())
            .limit(min(max(limit, 1), 200))
        ).all()
    )


def build_exit_queue_snapshot(session: Session, *, owner_user_id: int) -> P71ExitQueueSnapshot:
    today = date.today()
    exit_snap = get_latest_exit_recommendation_snapshot(session, owner_user_id=owner_user_id)
    list_snap = get_latest_listing_snapshot(session, owner_user_id=owner_user_id)
    if exit_snap is None:
        from app.services.exit_recommendation_service import build_exit_recommendation_snapshot

        exit_snap = build_exit_recommendation_snapshot(session, owner_user_id=owner_user_id)
    if list_snap is None:
        from app.services.listing_intelligence_service import build_listing_recommendation_snapshot

        list_snap = build_listing_recommendation_snapshot(session, owner_user_id=owner_user_id)

    exit_items = list_exit_recommendation_items(session, snapshot_id=int(exit_snap.id or 0))
    listing_by_copy = {
        it.inventory_copy_id: it for it in list_listing_items(session, snapshot_id=int(list_snap.id or 0))
    }
    ranked = sorted(exit_items, key=lambda x: (x.exit_score, x.exit_confidence), reverse=True)

    snap = P71ExitQueueSnapshot(owner_user_id=owner_user_id, snapshot_date=today, generated_at=utc_now())
    session.add(snap)
    session.flush()

    priority = 1
    for ex in ranked[:100]:
        if ex.recommendation in ("HOLD",):
            continue
        lst = listing_by_copy.get(ex.inventory_copy_id)
        session.add(
            P71ExitQueueItem(
                snapshot_id=int(snap.id or 0),
                owner_user_id=owner_user_id,
                inventory_copy_id=ex.inventory_copy_id,
                title=ex.title,
                priority=priority,
                expected_profit=float(lst.expected_profit if lst else 0),
                expected_roi_pct=float(lst.expected_roi_pct if lst else 0),
                confidence=float(ex.exit_confidence),
                recommended_action=ex.recommendation,
                target_price=float(lst.suggested_bin if lst and lst.suggested_bin else 0) or None,
                expected_days=float(lst.expected_days_to_sell if lst else 30),
                factors_json={"exit_score": ex.exit_score, "primary_reason": ex.primary_reason},
            )
        )
        priority += 1

    snap.total_items = priority - 1
    session.add(snap)
    session.flush()
    return snap
