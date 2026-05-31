from __future__ import annotations

from sqlmodel import Session, select

from app.models.asset_ledger import InventoryCopy
from app.models.grade_before_sell import GradeBeforeSellRecommendation
from app.schemas.grade_before_sell import GradeBeforeSellRecommendationRead, GradeBeforeSellSummaryRead
from app.services.grade_before_sell_engine import generate_grade_before_sell_recommendations
from app.services.sell_candidate_engine import _split_identity_key


def _latest_rows(session: Session, *, owner_user_id: int) -> dict[int, GradeBeforeSellRecommendation]:
    rows = session.exec(
        select(GradeBeforeSellRecommendation)
        .where(GradeBeforeSellRecommendation.owner_user_id == owner_user_id)
        .order_by(GradeBeforeSellRecommendation.created_at.desc(), GradeBeforeSellRecommendation.id.desc())
    ).all()
    latest: dict[int, GradeBeforeSellRecommendation] = {}
    for row in rows:
        if row.inventory_item_id not in latest:
            latest[row.inventory_item_id] = row
    return latest


def _to_read(session: Session, *, row: GradeBeforeSellRecommendation) -> GradeBeforeSellRecommendationRead:
    copy = session.get(InventoryCopy, row.inventory_item_id)
    publisher, series, issue_number, _variant = _split_identity_key(copy.metadata_identity_key if copy else None)
    title = series or (copy.metadata_identity_key if copy else "")
    return GradeBeforeSellRecommendationRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        inventory_item_id=int(row.inventory_item_id),
        recommendation=row.recommendation,  # type: ignore[arg-type]
        current_estimated_value=float(row.current_estimated_value),
        expected_graded_value=float(row.expected_graded_value),
        estimated_grading_cost=float(row.estimated_grading_cost),
        expected_value_gain=float(row.expected_value_gain),
        expected_roi=float(row.expected_roi),
        confidence_score=float(row.confidence_score),
        rationale=row.rationale,
        created_at=row.created_at.isoformat(),
        title=title,
        issue_number=issue_number,
        publisher=publisher,
    )


def persist_grade_before_sell_recommendations(session: Session, *, owner_user_id: int) -> int:
    computed = generate_grade_before_sell_recommendations(session, owner_user_id=owner_user_id)
    latest = _latest_rows(session, owner_user_id=owner_user_id)
    created = 0
    for result in computed:
        prior = latest.get(result.inventory_item_id)
        if prior is not None:
            if (
                prior.recommendation == result.recommendation
                and abs(float(prior.expected_roi) - float(result.expected_roi)) < 1e-9
                and abs(float(prior.expected_value_gain) - float(result.expected_value_gain)) < 1e-9
                and abs(float(prior.confidence_score) - float(result.confidence_score)) < 1e-9
                and prior.rationale == result.rationale
            ):
                continue
        session.add(
            GradeBeforeSellRecommendation(
                owner_user_id=owner_user_id,
                inventory_item_id=result.inventory_item_id,
                recommendation=result.recommendation,
                current_estimated_value=result.current_estimated_value,
                expected_graded_value=result.expected_graded_value,
                estimated_grading_cost=result.estimated_grading_cost,
                expected_value_gain=result.expected_value_gain,
                expected_roi=result.expected_roi,
                confidence_score=result.confidence_score,
                rationale=result.rationale,
            )
        )
        created += 1
    session.commit()
    return created


def list_grade_before_sell_recommendations(
    session: Session,
    *,
    owner_user_id: int,
    recommendation: str | None = None,
    roi_min: float | None = None,
    publisher: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[GradeBeforeSellRecommendationRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    latest = _latest_rows(session, owner_user_id=owner_user_id)
    items: list[GradeBeforeSellRecommendationRead] = []
    for inv_id in sorted(latest.keys()):
        row = latest[inv_id]
        if recommendation and row.recommendation != recommendation.strip().upper():
            continue
        if roi_min is not None and float(row.expected_roi) < float(roi_min):
            continue
        read = _to_read(session, row=row)
        if publisher and publisher.strip().lower() not in read.publisher.lower():
            continue
        items.append(read)
    items.sort(key=lambda r: (-r.expected_roi, r.inventory_item_id))
    total = len(items)
    return items[offset : offset + limit], total


def refresh_and_list_latest_grade_before_sell(
    session: Session,
    *,
    owner_user_id: int,
    recommendation: str | None = None,
    roi_min: float | None = None,
    publisher: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[GradeBeforeSellRecommendationRead], int]:
    persist_grade_before_sell_recommendations(session, owner_user_id=owner_user_id)
    return list_grade_before_sell_recommendations(
        session,
        owner_user_id=owner_user_id,
        recommendation=recommendation,
        roi_min=roi_min,
        publisher=publisher,
        limit=limit,
        offset=offset,
    )


def build_grade_before_sell_summary(session: Session, *, owner_user_id: int) -> GradeBeforeSellSummaryRead:
    latest = _latest_rows(session, owner_user_id=owner_user_id)
    counts = {"GRADE_BEFORE_SELL": 0, "SELL_RAW": 0, "HOLD_FOR_REVIEW": 0}
    roi_sum = 0.0
    gain_sum = 0.0
    for row in latest.values():
        counts[row.recommendation] = counts.get(row.recommendation, 0) + 1
        roi_sum += float(row.expected_roi)
        gain_sum += float(row.expected_value_gain)
    total = len(latest)
    avg_roi = round(roi_sum / total, 4) if total else 0.0
    return GradeBeforeSellSummaryRead(
        total_recommendations=total,
        grade_before_sell_count=int(counts.get("GRADE_BEFORE_SELL", 0)),
        sell_raw_count=int(counts.get("SELL_RAW", 0)),
        hold_for_review_count=int(counts.get("HOLD_FOR_REVIEW", 0)),
        average_expected_roi=avg_roi,
        total_expected_value_gain=round(gain_sum, 2),
    )
