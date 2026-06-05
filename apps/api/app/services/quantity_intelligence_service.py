"""P66-02 Quantity Intelligence — collection/spec/flip split (read-only P62 inputs)."""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.variant_market_intelligence import QuantityRecommendationItem, QuantityRecommendationSnapshot
from app.services.buy_queue_service import get_latest_buy_queue_snapshot, list_buy_queue_items


def get_latest_quantity_snapshot(session: Session, *, owner_user_id: int) -> QuantityRecommendationSnapshot | None:
    return session.exec(
        select(QuantityRecommendationSnapshot)
        .where(QuantityRecommendationSnapshot.owner_user_id == owner_user_id)
        .order_by(QuantityRecommendationSnapshot.generated_at.desc(), QuantityRecommendationSnapshot.id.desc())
    ).first()


def list_quantity_items(session: Session, *, snapshot_id: int, limit: int = 200) -> list[QuantityRecommendationItem]:
    return list(
        session.exec(
            select(QuantityRecommendationItem)
            .where(QuantityRecommendationItem.snapshot_id == snapshot_id)
            .order_by(QuantityRecommendationItem.total_quantity.desc(), QuantityRecommendationItem.id.asc())
            .limit(limit)
        ).all()
    )


def _confidence(priority: float, demand: float, spec: float) -> str:
    if priority >= 80 and demand >= 50:
        return "HIGH"
    if priority >= 65 or spec >= 60:
        return "MEDIUM"
    return "LOW"


def _quantities_for_row(
    *,
    priority: float,
    demand: float,
    velocity: float,
    spec: float,
    legacy_qty: int,
) -> tuple[int, int, int, str]:
    conf = _confidence(priority, demand, spec)
    collection = 1 if priority >= 58 else 0
    spec_q = 0
    if demand >= 45 and spec >= 55:
        spec_q = 2 if priority >= 82 else 1
    elif spec >= 70:
        spec_q = 1
    if demand < 25:
        spec_q = min(spec_q, 1)
    flip_q = 0
    if velocity >= 50 and demand >= 60 and priority >= 75:
        flip_q = 1
    if conf == "LOW":
        spec_q = min(spec_q, 1)
        flip_q = 0
        collection = min(collection, 1)
    total = collection + spec_q + flip_q
    if total == 0 and priority >= 50:
        collection = 1
        total = 1
    if legacy_qty > total and conf == "HIGH":
        total = legacy_qty
        spec_q = max(spec_q, legacy_qty - collection - flip_q)
    reason_parts = [
        f"collection need {collection}",
        f"spec need {spec_q}",
        f"flip need {flip_q}",
    ]
    if demand < 25:
        reason_parts.append("capped spec (low demand)")
    if conf == "LOW":
        reason_parts.append("reduced quantity (low confidence)")
    return collection, spec_q, flip_q, total, "; ".join(reason_parts)


def build_quantity_recommendations(session: Session, *, owner_user_id: int) -> QuantityRecommendationSnapshot:
    snap = QuantityRecommendationSnapshot(owner_user_id=owner_user_id, total_items=0, metadata_json={})
    session.add(snap)
    session.flush()

    bq = get_latest_buy_queue_snapshot(session, owner_user_id=owner_user_id)
    count = 0
    if bq:
        items, _ = list_buy_queue_items(session, snapshot_id=int(bq.id or 0), limit=100)
        for row in items:
            coll, spec_q, flip_q, total, reason = _quantities_for_row(
                priority=float(row.priority_score),
                demand=float(row.demand_score),
                velocity=float(row.velocity_score),
                spec=float(row.spec_score),
                legacy_qty=int(row.quantity_recommended or 1),
            )
            session.add(
                QuantityRecommendationItem(
                    snapshot_id=int(snap.id or 0),
                    owner_user_id=owner_user_id,
                    buy_queue_item_id=int(row.id or 0),
                    external_catalog_issue_id=int(row.external_catalog_issue_id) if row.external_catalog_issue_id else None,
                    title=row.title,
                    collection_quantity=coll,
                    spec_quantity=spec_q,
                    flip_quantity=flip_q,
                    total_quantity=total,
                    confidence=_confidence(float(row.priority_score), float(row.demand_score), float(row.spec_score)),
                    reason=reason,
                    factors_json={
                        "priority_score": row.priority_score,
                        "demand_score": row.demand_score,
                        "velocity_score": row.velocity_score,
                        "spec_score": row.spec_score,
                        "p62_quantity_recommended": row.quantity_recommended,
                    },
                )
            )
            count += 1

    snap.total_items = count
    session.add(snap)
    session.commit()
    session.refresh(snap)
    return snap
