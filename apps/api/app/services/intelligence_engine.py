from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Iterable

from fastapi import HTTPException
from sqlmodel import Session, func, select

from app.models import (
    AgentExecution,
    IntelligenceEvidence,
    IntelligenceRecommendation,
    IntelligenceRecommendationReview,
)
from app.schemas.intelligence import (
    IntelligenceEvidenceRead,
    IntelligenceRecommendationDetail,
    IntelligenceRecommendationListResponse,
    IntelligenceRecommendationRead,
    IntelligenceRecommendationReviewRead,
    IntelligenceRecommendationTypeListResponse,
)
from app.services.agent_registry import clamp_agent_pagination

PRICING_RECOMMENDATION_TYPES: tuple[str, ...] = (
    "underpriced_inventory",
    "overpriced_inventory",
    "rapid_appreciation_candidate",
    "rapid_decline_candidate",
    "grade_candidate",
    "hold_candidate",
    "sell_candidate",
    "watch_candidate",
)

CATALOG_RECOMMENDATION_TYPES: tuple[str, ...] = (
    "missing_metadata",
    "possible_duplicate",
    "catalog_conflict",
    "publisher_conflict",
    "series_conflict",
    "ocr_review_needed",
    "variant_review_needed",
    "cover_review_needed",
    "identity_review_needed",
)

ALL_INTELLIGENCE_RECOMMENDATION_TYPES: tuple[str, ...] = tuple(
    sorted({*PRICING_RECOMMENDATION_TYPES, *CATALOG_RECOMMENDATION_TYPES})
)

RECOMMENDATION_STATUS_OPEN = "OPEN"
REVIEW_STATUS_REVIEWED = "REVIEWED"
REVIEW_STATUS_DISMISSED = "DISMISSED"
REVIEW_STATUS_ACCEPTED = "ACCEPTED"
REVIEW_STATUS_NOTED = "NOTED"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _avg(values: Iterable[float]) -> float:
    rows = [float(value) for value in values]
    if not rows:
        return 0.0
    return sum(rows) / len(rows)


def calculate_confidence_score(
    *,
    evidence_scores: list[float],
    supporting_signal_count: int = 0,
    data_freshness_score: float | None = None,
) -> float:
    evidence_component = _avg([_clamp01(score) for score in evidence_scores])
    support_bonus = min(0.18, max(0, supporting_signal_count) * 0.03)
    freshness_component = 0.0 if data_freshness_score is None else 0.12 * _clamp01(data_freshness_score)
    base = (evidence_component * 0.7) + support_bonus + freshness_component
    return round(_clamp01(base), 4)


def calculate_opportunity_score(
    *,
    spread_score: float = 0.0,
    trend_score: float = 0.0,
    urgency_score: float = 0.0,
    scarcity_score: float = 0.0,
    data_gap_score: float = 0.0,
) -> float:
    weighted = (
        (_clamp01(spread_score) * 0.35)
        + (_clamp01(trend_score) * 0.25)
        + (_clamp01(urgency_score) * 0.2)
        + (_clamp01(scarcity_score) * 0.1)
        + (_clamp01(data_gap_score) * 0.1)
    )
    return round(_clamp01(weighted), 4)


def calculate_priority_score(
    *,
    opportunity_score: float,
    confidence_score: float,
    urgency_score: float = 0.0,
) -> float:
    weighted = (
        (_clamp01(opportunity_score) * 0.5)
        + (_clamp01(confidence_score) * 0.35)
        + (_clamp01(urgency_score) * 0.15)
    )
    return round(_clamp01(weighted), 4)


def _execution_row(session: Session, *, agent_execution_id: int) -> AgentExecution:
    row = session.get(AgentExecution, agent_execution_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Agent execution not found.")
    return row


def _recommendation_row(session: Session, *, recommendation_id: int) -> IntelligenceRecommendation:
    row = session.get(IntelligenceRecommendation, recommendation_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Intelligence recommendation not found.")
    return row


def _evidence_rows(session: Session, *, recommendation_id: int) -> list[IntelligenceEvidence]:
    return session.exec(
        select(IntelligenceEvidence)
        .where(IntelligenceEvidence.recommendation_id == recommendation_id)
        .order_by(IntelligenceEvidence.created_at.asc(), IntelligenceEvidence.id.asc())
    ).all()


def _review_rows(session: Session, *, recommendation_id: int) -> list[IntelligenceRecommendationReview]:
    return session.exec(
        select(IntelligenceRecommendationReview)
        .where(IntelligenceRecommendationReview.recommendation_id == recommendation_id)
        .order_by(IntelligenceRecommendationReview.reviewed_at.asc(), IntelligenceRecommendationReview.id.asc())
    ).all()


def _review_read(row: IntelligenceRecommendationReview) -> IntelligenceRecommendationReviewRead:
    return IntelligenceRecommendationReviewRead(
        id=int(row.id or 0),
        recommendation_id=row.recommendation_id,
        review_status=row.review_status,
        reviewed_by=row.reviewed_by,
        reviewed_at=row.reviewed_at,
        review_notes=row.review_notes,
    )


def _evidence_read(row: IntelligenceEvidence) -> IntelligenceEvidenceRead:
    return IntelligenceEvidenceRead(
        id=int(row.id or 0),
        recommendation_id=row.recommendation_id,
        evidence_type=row.evidence_type,
        evidence_source=row.evidence_source,
        evidence_payload_json=row.evidence_payload_json,
        evidence_score=row.evidence_score,
        created_at=row.created_at,
    )


def _recommendation_read(session: Session, row: IntelligenceRecommendation) -> IntelligenceRecommendationRead:
    reviews = _review_rows(session, recommendation_id=int(row.id or 0))
    latest_review = _review_read(reviews[-1]) if reviews else None
    return IntelligenceRecommendationRead(
        id=int(row.id or 0),
        recommendation_uuid=row.recommendation_uuid,
        agent_execution_id=row.agent_execution_id,
        recommendation_type=row.recommendation_type,
        title=row.title,
        description=row.description,
        confidence_score=row.confidence_score,
        opportunity_score=row.opportunity_score,
        priority_score=row.priority_score,
        inventory_copy_id=row.inventory_copy_id,
        inventory_title=row.inventory_title,
        status=latest_review.review_status if latest_review is not None else row.status,
        recommendation_payload_json=row.recommendation_payload_json,
        created_at=row.created_at,
        latest_review=latest_review,
    )


def recommendation_detail(session: Session, *, recommendation_id: int) -> IntelligenceRecommendationDetail:
    row = _recommendation_row(session, recommendation_id=recommendation_id)
    return IntelligenceRecommendationDetail(
        recommendation=_recommendation_read(session, row),
        evidence=[_evidence_read(evidence) for evidence in _evidence_rows(session, recommendation_id=recommendation_id)],
        reviews=[_review_read(review) for review in _review_rows(session, recommendation_id=recommendation_id)],
    )


def create_recommendation(
    session: Session,
    *,
    agent_execution_id: int,
    recommendation_key: str,
    recommendation_type: str,
    title: str,
    description: str,
    inventory_copy_id: int | None = None,
    inventory_title: str | None = None,
    confidence_score: float,
    opportunity_score: float,
    priority_score: float,
    recommendation_payload_json: dict[str, Any] | None = None,
    status: str = RECOMMENDATION_STATUS_OPEN,
) -> IntelligenceRecommendationRead:
    _execution_row(session, agent_execution_id=agent_execution_id)
    row = IntelligenceRecommendation(
        recommendation_uuid=str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"intelligence-recommendation:{agent_execution_id}:{recommendation_key.strip().lower()}",
            )
        ),
        agent_execution_id=agent_execution_id,
        recommendation_type=recommendation_type.strip().lower(),
        title=title.strip(),
        description=description.strip(),
        confidence_score=_clamp01(confidence_score),
        opportunity_score=_clamp01(opportunity_score),
        priority_score=_clamp01(priority_score),
        inventory_copy_id=inventory_copy_id,
        inventory_title=(inventory_title or "").strip(),
        status=status.strip().upper(),
        recommendation_payload_json=_json_safe(recommendation_payload_json or {}),
        created_at=utc_now(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _recommendation_read(session, row)


def attach_evidence(
    session: Session,
    *,
    recommendation_id: int,
    evidence_type: str,
    evidence_source: str,
    evidence_payload_json: dict[str, Any] | None = None,
    evidence_score: float,
) -> IntelligenceEvidenceRead:
    _recommendation_row(session, recommendation_id=recommendation_id)
    row = IntelligenceEvidence(
        recommendation_id=recommendation_id,
        evidence_type=evidence_type.strip().lower(),
        evidence_source=evidence_source.strip(),
        evidence_payload_json=_json_safe(evidence_payload_json or {}),
        evidence_score=_clamp01(evidence_score),
        created_at=utc_now(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _evidence_read(row)


def _visible_recommendation_statement(*, owner_user_id: int):
    return (
        select(IntelligenceRecommendation)
        .join(AgentExecution, AgentExecution.id == IntelligenceRecommendation.agent_execution_id)
        .where(AgentExecution.triggered_by == str(owner_user_id))
    )


def _visible_recommendation_row(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_id: int,
) -> IntelligenceRecommendation:
    row = session.exec(
        _visible_recommendation_statement(owner_user_id=owner_user_id).where(IntelligenceRecommendation.id == recommendation_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Intelligence recommendation not found.")
    return row


def list_recommendations(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_type: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> IntelligenceRecommendationListResponse:
    limit, offset = clamp_agent_pagination(limit=limit, offset=offset)
    stmt = _visible_recommendation_statement(owner_user_id=owner_user_id)
    count_stmt = (
        select(func.count())
        .select_from(IntelligenceRecommendation)
        .join(AgentExecution, AgentExecution.id == IntelligenceRecommendation.agent_execution_id)
        .where(AgentExecution.triggered_by == str(owner_user_id))
    )
    if recommendation_type is not None:
        normalized = recommendation_type.strip().lower()
        stmt = stmt.where(IntelligenceRecommendation.recommendation_type == normalized)
        count_stmt = count_stmt.where(IntelligenceRecommendation.recommendation_type == normalized)
    if status is not None:
        normalized_status = status.strip().upper()
        if normalized_status == RECOMMENDATION_STATUS_OPEN:
            stmt = stmt.where(
                ~select(IntelligenceRecommendationReview.id)
                .where(IntelligenceRecommendationReview.recommendation_id == IntelligenceRecommendation.id)
                .exists()
            )
            count_stmt = count_stmt.where(
                ~select(IntelligenceRecommendationReview.id)
                .where(IntelligenceRecommendationReview.recommendation_id == IntelligenceRecommendation.id)
                .exists()
            )
        else:
            latest_review_subquery = (
                select(func.max(IntelligenceRecommendationReview.id))
                .where(IntelligenceRecommendationReview.recommendation_id == IntelligenceRecommendation.id)
                .scalar_subquery()
            )
            stmt = stmt.where(
                select(IntelligenceRecommendationReview.review_status)
                .where(IntelligenceRecommendationReview.id == latest_review_subquery)
                .scalar_subquery()
                == normalized_status
            )
            count_stmt = count_stmt.where(
                select(IntelligenceRecommendationReview.review_status)
                .where(IntelligenceRecommendationReview.id == latest_review_subquery)
                .scalar_subquery()
                == normalized_status
            )
    rows = session.exec(
        stmt.order_by(
            IntelligenceRecommendation.priority_score.desc(),
            IntelligenceRecommendation.created_at.asc(),
            IntelligenceRecommendation.id.asc(),
        )
        .offset(offset)
        .limit(limit)
    ).all()
    total_items = int(session.exec(count_stmt).one())
    return IntelligenceRecommendationListResponse(
        items=[_recommendation_read(session, row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
    )


def get_recommendation_detail_for_owner(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_id: int,
) -> IntelligenceRecommendationDetail:
    row = _visible_recommendation_row(session, owner_user_id=owner_user_id, recommendation_id=recommendation_id)
    return recommendation_detail(session, recommendation_id=int(row.id or 0))


def list_recommendation_types() -> IntelligenceRecommendationTypeListResponse:
    return IntelligenceRecommendationTypeListResponse(items=list(ALL_INTELLIGENCE_RECOMMENDATION_TYPES))
