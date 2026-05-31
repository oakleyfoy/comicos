from __future__ import annotations

from sqlmodel import Session, select

from app.models.asset_ledger import InventoryCopy
from app.models.hold_sell_intelligence import HoldSellRecommendation
from app.schemas.hold_sell_intelligence import HoldSellRecommendationRead, HoldSellSummaryRead
from app.services.hold_sell_engine import generate_hold_sell_recommendations
from app.services.sell_candidate_engine import _split_identity_key


def _latest_hold_sell_rows(session: Session, *, owner_user_id: int) -> dict[int, HoldSellRecommendation]:
    rows = session.exec(
        select(HoldSellRecommendation)
        .where(HoldSellRecommendation.owner_user_id == owner_user_id)
        .order_by(HoldSellRecommendation.created_at.desc(), HoldSellRecommendation.id.desc())
    ).all()
    latest: dict[int, HoldSellRecommendation] = {}
    for row in rows:
        if row.inventory_item_id not in latest:
            latest[row.inventory_item_id] = row
    return latest


def _to_read(session: Session, *, row: HoldSellRecommendation) -> HoldSellRecommendationRead:
    copy = session.get(InventoryCopy, row.inventory_item_id)
    publisher, series, issue_number, _variant = _split_identity_key(copy.metadata_identity_key if copy else None)
    title = series or (copy.metadata_identity_key if copy else "")
    return HoldSellRecommendationRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        inventory_item_id=int(row.inventory_item_id),
        recommendation=row.recommendation,  # type: ignore[arg-type]
        conviction_score=float(row.conviction_score),
        confidence_score=float(row.confidence_score),
        estimated_fmv=float(row.estimated_fmv),
        acquisition_cost=float(row.acquisition_cost),
        unrealized_gain=float(row.unrealized_gain),
        rationale=row.rationale,
        created_at=row.created_at.isoformat(),
        title=title,
        issue_number=issue_number,
        publisher=publisher,
    )


def persist_hold_sell_recommendations(session: Session, *, owner_user_id: int) -> int:
    computed = generate_hold_sell_recommendations(session, owner_user_id=owner_user_id)
    latest = _latest_hold_sell_rows(session, owner_user_id=owner_user_id)
    created = 0
    for result in computed:
        prior = latest.get(result.inventory_item_id)
        if prior is not None:
            if (
                prior.recommendation == result.recommendation
                and abs(float(prior.conviction_score) - float(result.conviction_score)) < 1e-9
                and abs(float(prior.confidence_score) - float(result.confidence_score)) < 1e-9
                and prior.rationale == result.rationale
            ):
                continue
        session.add(
            HoldSellRecommendation(
                owner_user_id=owner_user_id,
                inventory_item_id=result.inventory_item_id,
                recommendation=result.recommendation,
                conviction_score=result.conviction_score,
                confidence_score=result.confidence_score,
                estimated_fmv=result.estimated_fmv,
                acquisition_cost=result.acquisition_cost,
                unrealized_gain=result.unrealized_gain,
                rationale=result.rationale,
            )
        )
        created += 1
    session.commit()
    return created


def list_hold_sell_recommendations(
    session: Session,
    *,
    owner_user_id: int,
    recommendation: str | None = None,
    conviction_min: float | None = None,
    publisher: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[HoldSellRecommendationRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    latest = _latest_hold_sell_rows(session, owner_user_id=owner_user_id)
    items: list[HoldSellRecommendationRead] = []
    for inv_id in sorted(latest.keys()):
        row = latest[inv_id]
        if recommendation and row.recommendation != recommendation.strip().upper():
            continue
        if conviction_min is not None and float(row.conviction_score) < float(conviction_min):
            continue
        read = _to_read(session, row=row)
        if publisher and publisher.strip().lower() not in read.publisher.lower():
            continue
        items.append(read)
    items.sort(key=lambda r: (-r.conviction_score, r.inventory_item_id))
    total = len(items)
    return items[offset : offset + limit], total


def refresh_and_list_latest_hold_sell(
    session: Session,
    *,
    owner_user_id: int,
    recommendation: str | None = None,
    conviction_min: float | None = None,
    publisher: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[HoldSellRecommendationRead], int]:
    persist_hold_sell_recommendations(session, owner_user_id=owner_user_id)
    return list_hold_sell_recommendations(
        session,
        owner_user_id=owner_user_id,
        recommendation=recommendation,
        conviction_min=conviction_min,
        publisher=publisher,
        limit=limit,
        offset=offset,
    )


def build_hold_sell_summary(session: Session, *, owner_user_id: int) -> HoldSellSummaryRead:
    latest = _latest_hold_sell_rows(session, owner_user_id=owner_user_id)
    counts = {"HOLD": 0, "WATCH": 0, "SELL": 0}
    conviction_sum = 0.0
    gain_sum = 0.0
    for row in latest.values():
        counts[row.recommendation] = counts.get(row.recommendation, 0) + 1
        conviction_sum += float(row.conviction_score)
        gain_sum += float(row.unrealized_gain)
    total = len(latest)
    avg = round(conviction_sum / total, 1) if total else 0.0
    return HoldSellSummaryRead(
        total_recommendations=total,
        hold_count=int(counts.get("HOLD", 0)),
        watch_count=int(counts.get("WATCH", 0)),
        sell_count=int(counts.get("SELL", 0)),
        average_conviction=avg,
        total_unrealized_gain=round(gain_sum, 2),
    )
