from __future__ import annotations

from sqlmodel import Session, select

from app.models.acquisition_opportunity import AcquisitionOpportunity
from app.schemas.acquisition_opportunity import (
    AcquisitionOpportunityRead,
    AcquisitionOpportunitySummaryRead,
)
from app.services.acquisition_opportunity_engine import (
    AcquisitionOpportunityCandidate,
    generate_acquisition_opportunities,
)


def _source_key(source_type: str, source_reference_id: int | None) -> tuple[str, int | None]:
    return (source_type.strip().upper(), source_reference_id)


def latest_acquisition_opportunity_rows(
    session: Session,
    *,
    owner_user_id: int,
) -> dict[tuple[str, int | None], AcquisitionOpportunity]:
    rows = session.exec(
        select(AcquisitionOpportunity)
        .where(AcquisitionOpportunity.owner_user_id == owner_user_id)
        .order_by(AcquisitionOpportunity.created_at.desc(), AcquisitionOpportunity.id.desc())
    ).all()
    latest: dict[tuple[str, int | None], AcquisitionOpportunity] = {}
    for row in rows:
        key = _source_key(row.source_type, row.source_reference_id)
        if key not in latest:
            latest[key] = row
    return latest


def _to_read(row: AcquisitionOpportunity) -> AcquisitionOpportunityRead:
    return AcquisitionOpportunityRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        source_type=row.source_type,  # type: ignore[arg-type]
        source_reference_id=row.source_reference_id,
        publisher=row.publisher,
        series_name=row.series_name,
        issue_number=row.issue_number,
        variant_description=row.variant_description,
        opportunity_type=row.opportunity_type,  # type: ignore[arg-type]
        priority_score=float(row.priority_score),
        confidence_score=float(row.confidence_score),
        estimated_fmv=float(row.estimated_fmv) if row.estimated_fmv is not None else None,
        target_price=float(row.target_price) if row.target_price is not None else None,
        value_gap=float(row.value_gap) if row.value_gap is not None else None,
        rationale=row.rationale,
        created_at=row.created_at.isoformat(),
    )


def _matches_for_idempotency(prior: AcquisitionOpportunity, candidate: AcquisitionOpportunityCandidate) -> bool:
    def _price(v: float | None) -> float | None:
        return round(float(v), 2) if v is not None else None

    return (
        round(float(prior.priority_score), 1) == round(candidate.priority_score, 1)
        and round(float(prior.confidence_score), 2) == round(candidate.confidence_score, 2)
        and _price(prior.target_price) == _price(candidate.target_price)
        and prior.rationale == candidate.rationale
    )


def persist_acquisition_opportunities(session: Session, *, owner_user_id: int) -> int:
    candidates = generate_acquisition_opportunities(session, owner_user_id=owner_user_id)
    latest = latest_acquisition_opportunity_rows(session, owner_user_id=owner_user_id)
    created = 0
    for candidate in candidates:
        key = _source_key(candidate.source_type, candidate.source_reference_id)
        prior = latest.get(key)
        if prior is not None and _matches_for_idempotency(prior, candidate):
            continue
        row = AcquisitionOpportunity(
            owner_user_id=owner_user_id,
            source_type=candidate.source_type,
            source_reference_id=candidate.source_reference_id,
            publisher=candidate.publisher,
            series_name=candidate.series_name,
            issue_number=candidate.issue_number,
            variant_description=candidate.variant_description,
            opportunity_type=candidate.opportunity_type,
            priority_score=candidate.priority_score,
            confidence_score=candidate.confidence_score,
            estimated_fmv=candidate.estimated_fmv,
            target_price=candidate.target_price,
            value_gap=candidate.value_gap,
            rationale=candidate.rationale,
        )
        session.add(row)
        created += 1
        latest[key] = row
    if created:
        session.commit()
    return created


def list_acquisition_opportunities(
    session: Session,
    *,
    owner_user_id: int,
    opportunity_type: str | None = None,
    priority_score_min: float | None = None,
    publisher: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AcquisitionOpportunityRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    latest = latest_acquisition_opportunity_rows(session, owner_user_id=owner_user_id)
    items: list[AcquisitionOpportunityRead] = []
    for row in latest.values():
        if opportunity_type and row.opportunity_type != opportunity_type.strip().upper():
            continue
        if priority_score_min is not None and float(row.priority_score) < float(priority_score_min):
            continue
        if publisher and publisher.strip().lower() not in row.publisher.lower():
            continue
        items.append(_to_read(row))
    items.sort(key=lambda r: (-r.priority_score, r.publisher.lower(), r.series_name.lower(), r.issue_number))
    total = len(items)
    return items[offset : offset + limit], total


def refresh_and_list_latest_acquisition_opportunities(
    session: Session,
    *,
    owner_user_id: int,
    opportunity_type: str | None = None,
    priority_score_min: float | None = None,
    publisher: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AcquisitionOpportunityRead], int]:
    persist_acquisition_opportunities(session, owner_user_id=owner_user_id)
    return list_acquisition_opportunities(
        session,
        owner_user_id=owner_user_id,
        opportunity_type=opportunity_type,
        priority_score_min=priority_score_min,
        publisher=publisher,
        limit=limit,
        offset=offset,
    )


def build_acquisition_opportunity_summary(session: Session, *, owner_user_id: int) -> AcquisitionOpportunitySummaryRead:
    latest = latest_acquisition_opportunity_rows(session, owner_user_id=owner_user_id)
    by_type: dict[str, int] = {}
    priority_sum = 0.0
    confidence_sum = 0.0
    with_target = 0
    for row in latest.values():
        by_type[row.opportunity_type] = by_type.get(row.opportunity_type, 0) + 1
        priority_sum += float(row.priority_score)
        confidence_sum += float(row.confidence_score)
        if row.target_price is not None:
            with_target += 1
    count = len(latest)
    return AcquisitionOpportunitySummaryRead(
        total_opportunities=count,
        average_priority_score=round(priority_sum / count, 1) if count else 0.0,
        average_confidence_score=round(confidence_sum / count, 2) if count else 0.0,
        by_opportunity_type=by_type,
        with_target_price=with_target,
    )
