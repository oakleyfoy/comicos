from __future__ import annotations

from sqlmodel import Session, select

from app.models.asset_ledger import InventoryCopy
from app.models.sell_candidate import SellCandidateRecommendation
from app.schemas.sell_candidate import SellCandidateRecommendationRead, SellCandidateSummaryRead
from app.services.sell_candidate_engine import generate_sell_candidates


def _latest_sell_candidate_rows(session: Session, *, owner_user_id: int) -> dict[int, SellCandidateRecommendation]:
    rows = session.exec(
        select(SellCandidateRecommendation)
        .where(SellCandidateRecommendation.owner_user_id == owner_user_id)
        .order_by(SellCandidateRecommendation.created_at.desc(), SellCandidateRecommendation.id.desc())
    ).all()
    latest: dict[int, SellCandidateRecommendation] = {}
    for row in rows:
        if row.inventory_item_id not in latest:
            latest[row.inventory_item_id] = row
    return latest


def _to_read(session: Session, *, row: SellCandidateRecommendation) -> SellCandidateRecommendationRead:
    copy = session.get(InventoryCopy, row.inventory_item_id)
    from app.services.sell_candidate_engine import _split_identity_key

    publisher, series, issue_number, variant = _split_identity_key(copy.metadata_identity_key if copy else None)
    title = series or (copy.metadata_identity_key if copy else "")
    return SellCandidateRecommendationRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        inventory_item_id=int(row.inventory_item_id),
        recommendation=row.recommendation,  # type: ignore[arg-type]
        confidence_score=float(row.confidence_score),
        rationale=row.rationale,
        estimated_fmv=float(row.estimated_fmv),
        estimated_profit=float(row.estimated_profit),
        created_at=row.created_at.isoformat(),
        title=title,
        issue_number=issue_number,
        publisher=publisher,
        variant=variant,
    )


def generate_sell_candidate_recommendations(session: Session, *, owner_user_id: int) -> int:
    computed = generate_sell_candidates(session, owner_user_id=owner_user_id)
    latest = _latest_sell_candidate_rows(session, owner_user_id=owner_user_id)
    created = 0
    for result in computed:
        prior = latest.get(result.inventory_item_id)
        if prior is not None:
            if (
                prior.recommendation == result.recommendation
                and prior.rationale == result.rationale
                and abs(float(prior.confidence_score) - float(result.confidence_score)) < 1e-9
                and abs(float(prior.estimated_fmv) - float(result.estimated_fmv)) < 1e-9
                and abs(float(prior.estimated_profit) - float(result.estimated_profit)) < 1e-9
            ):
                continue
        session.add(
            SellCandidateRecommendation(
                owner_user_id=owner_user_id,
                inventory_item_id=result.inventory_item_id,
                recommendation=result.recommendation,
                confidence_score=result.confidence_score,
                rationale=result.rationale,
                estimated_fmv=result.estimated_fmv,
                estimated_profit=result.estimated_profit,
            )
        )
        created += 1
    session.commit()
    return created


def list_sell_candidate_recommendations(
    session: Session,
    *,
    owner_user_id: int,
    recommendation: str | None = None,
    publisher: str | None = None,
    min_confidence: float | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[SellCandidateRecommendationRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    latest = _latest_sell_candidate_rows(session, owner_user_id=owner_user_id)
    items: list[SellCandidateRecommendationRead] = []
    for inv_id in sorted(latest.keys()):
        row = latest[inv_id]
        if recommendation and row.recommendation != recommendation.strip().upper():
            continue
        read = _to_read(session, row=row)
        if publisher and publisher.strip().lower() not in read.publisher.lower():
            continue
        if min_confidence is not None and read.confidence_score < float(min_confidence):
            continue
        items.append(read)
    items.sort(key=lambda r: (-r.confidence_score, r.inventory_item_id))
    total = len(items)
    return items[offset : offset + limit], total


def list_latest_sell_candidate_recommendations(
    session: Session,
    *,
    owner_user_id: int,
    recommendation: str | None = None,
    publisher: str | None = None,
    min_confidence: float | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[SellCandidateRecommendationRead], int]:
    return list_sell_candidate_recommendations(
        session,
        owner_user_id=owner_user_id,
        recommendation=recommendation,
        publisher=publisher,
        min_confidence=min_confidence,
        limit=limit,
        offset=offset,
    )


def get_sell_candidate_recommendation(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_id: int,
) -> SellCandidateRecommendationRead:
    row = session.get(SellCandidateRecommendation, recommendation_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise ValueError("Sell candidate recommendation not found.")
    return _to_read(session, row=row)


def build_sell_candidate_summary(session: Session, *, owner_user_id: int) -> SellCandidateSummaryRead:
    latest = _latest_sell_candidate_rows(session, owner_user_id=owner_user_id)
    counts = {"STRONG_SELL": 0, "SELL": 0, "HOLD": 0, "REVIEW": 0}
    total_profit = 0.0
    for row in latest.values():
        counts[row.recommendation] = counts.get(row.recommendation, 0) + 1
        total_profit += float(row.estimated_profit)
    return SellCandidateSummaryRead(
        total_candidates=len(latest),
        strong_sell_count=int(counts.get("STRONG_SELL", 0)),
        sell_count=int(counts.get("SELL", 0)),
        hold_count=int(counts.get("HOLD", 0)),
        review_count=int(counts.get("REVIEW", 0)),
        total_estimated_profit=round(total_profit, 2),
    )
