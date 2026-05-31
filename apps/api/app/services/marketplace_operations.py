from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, func, select

from app.models import AgentExecution
from app.models.marketplace_operations import (
    MarketplaceRecommendation,
    MarketplaceRecommendationEvidence,
    MarketplaceRecommendationReview,
)
from app.schemas.marketplace_operations import (
    MarketplaceOperationsDashboardRead,
    MarketplaceRecommendationDetail,
    MarketplaceRecommendationEvidenceRead,
    MarketplaceRecommendationListResponse,
    MarketplaceRecommendationRead,
    MarketplaceRecommendationReviewRead,
)
from app.services.agent_registry import clamp_agent_pagination

RECOMMENDATION_STATUS_OPEN = "OPEN"
REVIEW_STATUS_REVIEWED = "REVIEWED"
REVIEW_STATUS_DISMISSED = "DISMISSED"
REVIEW_STATUS_ACCEPTED = "ACCEPTED"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in sorted(value.items(), key=lambda p: str(p[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def calculate_confidence_score(*, evidence_scores: list[float]) -> float:
    if not evidence_scores:
        return 0.0
    return round(_clamp01(sum(_clamp01(s) for s in evidence_scores) / len(evidence_scores)), 4)


def calculate_priority_score(*, confidence_score: float, severity: float = 0.5) -> float:
    return round(_clamp01((confidence_score * 0.6) + (_clamp01(severity) * 0.4)), 4)


def _review_rows(session: Session, *, recommendation_id: int) -> list[MarketplaceRecommendationReview]:
    return session.exec(
        select(MarketplaceRecommendationReview)
        .where(MarketplaceRecommendationReview.recommendation_id == recommendation_id)
        .order_by(MarketplaceRecommendationReview.reviewed_at.asc(), MarketplaceRecommendationReview.id.asc())
    ).all()


def _evidence_rows(session: Session, *, recommendation_id: int) -> list[MarketplaceRecommendationEvidence]:
    return session.exec(
        select(MarketplaceRecommendationEvidence)
        .where(MarketplaceRecommendationEvidence.recommendation_id == recommendation_id)
        .order_by(MarketplaceRecommendationEvidence.created_at.asc(), MarketplaceRecommendationEvidence.id.asc())
    ).all()


def _review_read(row: MarketplaceRecommendationReview) -> MarketplaceRecommendationReviewRead:
    return MarketplaceRecommendationReviewRead(
        id=int(row.id or 0),
        recommendation_id=row.recommendation_id,
        review_status=row.review_status,
        reviewed_by=row.reviewed_by,
        reviewed_at=row.reviewed_at,
        review_notes=row.review_notes,
    )


def _evidence_read(row: MarketplaceRecommendationEvidence) -> MarketplaceRecommendationEvidenceRead:
    return MarketplaceRecommendationEvidenceRead(
        id=int(row.id or 0),
        recommendation_id=row.recommendation_id,
        evidence_type=row.evidence_type,
        evidence_source=row.evidence_source,
        evidence_payload_json=dict(row.evidence_payload_json or {}),
        evidence_score=row.evidence_score,
        created_at=row.created_at,
    )


def _display_status(row: MarketplaceRecommendation, reviews: list[MarketplaceRecommendationReview]) -> str:
    if reviews:
        return reviews[-1].review_status
    return row.recommendation_status


def _recommendation_read(session: Session, row: MarketplaceRecommendation) -> MarketplaceRecommendationRead:
    reviews = _review_rows(session, recommendation_id=int(row.id or 0))
    latest = _review_read(reviews[-1]) if reviews else None
    return MarketplaceRecommendationRead(
        id=int(row.id or 0),
        recommendation_uuid=row.recommendation_uuid,
        agent_execution_id=row.agent_execution_id,
        recommendation_type=row.recommendation_type,
        title=row.title,
        description=row.description,
        confidence_score=row.confidence_score,
        priority_score=row.priority_score,
        recommendation_status=_display_status(row, reviews),
        listing_id=row.listing_id,
        inventory_copy_id=row.inventory_copy_id,
        marketplace_id=row.marketplace_id,
        marketplace_account_id=row.marketplace_account_id,
        created_at=row.created_at,
        latest_review=latest,
    )


def _visible_statement(*, owner_user_id: int):
    return (
        select(MarketplaceRecommendation)
        .join(AgentExecution, AgentExecution.id == MarketplaceRecommendation.agent_execution_id)
        .where(AgentExecution.triggered_by == str(owner_user_id))
    )


def _visible_row(session: Session, *, owner_user_id: int, recommendation_id: int) -> MarketplaceRecommendation:
    row = session.exec(
        _visible_statement(owner_user_id=owner_user_id).where(MarketplaceRecommendation.id == recommendation_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Marketplace recommendation not found.")
    return row


def create_recommendation_with_evidence(
    session: Session,
    *,
    agent_execution_id: int | None,
    recommendation_key: str,
    recommendation_type: str,
    title: str,
    description: str,
    listing_id: int | None = None,
    inventory_copy_id: int | None = None,
    marketplace_id: int | None = None,
    marketplace_account_id: int | None = None,
    evidence: list[dict[str, Any]],
    severity: float = 0.5,
) -> MarketplaceRecommendationRead:
    if not evidence:
        raise ValueError("Marketplace recommendations require at least one evidence record.")
    scores = [float(item.get("evidence_score", 0.0)) for item in evidence]
    confidence = calculate_confidence_score(evidence_scores=scores)
    priority = calculate_priority_score(confidence_score=confidence, severity=severity)
    rec_uuid = str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"marketplace-recommendation:{agent_execution_id}:{recommendation_key.strip().lower()}",
        )
    )
    row = MarketplaceRecommendation(
        recommendation_uuid=rec_uuid,
        agent_execution_id=agent_execution_id,
        recommendation_type=recommendation_type.strip().upper(),
        title=title.strip(),
        description=description.strip(),
        confidence_score=confidence,
        priority_score=priority,
        recommendation_status=RECOMMENDATION_STATUS_OPEN,
        listing_id=listing_id,
        inventory_copy_id=inventory_copy_id,
        marketplace_id=marketplace_id,
        marketplace_account_id=marketplace_account_id,
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    for item in evidence:
        session.add(
            MarketplaceRecommendationEvidence(
                recommendation_id=int(row.id or 0),
                evidence_type=str(item["evidence_type"]).strip().lower(),
                evidence_source=str(item["evidence_source"]).strip(),
                evidence_payload_json=_json_safe(item.get("evidence_payload_json") or {}),
                evidence_score=_clamp01(float(item.get("evidence_score", 0.0))),
                created_at=utc_now(),
            )
        )
    session.commit()
    session.refresh(row)
    return _recommendation_read(session, row)


def recommendation_detail(session: Session, *, recommendation_id: int) -> MarketplaceRecommendationDetail:
    row = session.get(MarketplaceRecommendation, recommendation_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Marketplace recommendation not found.")
    return MarketplaceRecommendationDetail(
        recommendation=_recommendation_read(session, row),
        evidence=[_evidence_read(e) for e in _evidence_rows(session, recommendation_id=recommendation_id)],
        reviews=[_review_read(r) for r in _review_rows(session, recommendation_id=recommendation_id)],
    )


def list_recommendations(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_type: str | None = None,
    recommendation_status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> MarketplaceRecommendationListResponse:
    limit, offset = clamp_agent_pagination(limit=limit, offset=offset)
    stmt = _visible_statement(owner_user_id=owner_user_id)
    if recommendation_type is not None:
        stmt = stmt.where(MarketplaceRecommendation.recommendation_type == recommendation_type.strip().upper())
    rows = session.exec(
        stmt.order_by(
            MarketplaceRecommendation.priority_score.desc(),
            MarketplaceRecommendation.created_at.asc(),
            MarketplaceRecommendation.id.asc(),
        )
    ).all()
    items = [_recommendation_read(session, row) for row in rows]
    if recommendation_status is not None:
        normalized = recommendation_status.strip().upper()
        items = [item for item in items if item.recommendation_status == normalized]
    total = len(items)
    return MarketplaceRecommendationListResponse(
        items=items[offset : offset + limit],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def get_recommendation_for_owner(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_id: int,
) -> MarketplaceRecommendationDetail:
    row = _visible_row(session, owner_user_id=owner_user_id, recommendation_id=recommendation_id)
    return recommendation_detail(session, recommendation_id=int(row.id or 0))


def append_review(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_id: int,
    reviewed_by: str,
    review_status: str,
    review_notes: str | None = None,
) -> MarketplaceRecommendationDetail:
    row = _visible_row(session, owner_user_id=owner_user_id, recommendation_id=recommendation_id)
    session.add(
        MarketplaceRecommendationReview(
            recommendation_id=int(row.id or 0),
            review_status=review_status.strip().upper(),
            reviewed_by=reviewed_by.strip(),
            reviewed_at=utc_now(),
            review_notes=(review_notes or "").strip() or None,
        )
    )
    session.commit()
    return get_recommendation_for_owner(session, owner_user_id=owner_user_id, recommendation_id=recommendation_id)


def get_operations_dashboard(session: Session, *, owner_user_id: int) -> MarketplaceOperationsDashboardRead:
    rows = session.exec(_visible_statement(owner_user_id=owner_user_id)).all()
    by_type: dict[str, int] = {}
    by_status: dict[str, int] = {}
    open_count = 0
    for row in rows:
        by_type[row.recommendation_type] = by_type.get(row.recommendation_type, 0) + 1
        reviews = _review_rows(session, recommendation_id=int(row.id or 0))
        status = _display_status(row, reviews)
        by_status[status] = by_status.get(status, 0) + 1
        if status == RECOMMENDATION_STATUS_OPEN:
            open_count += 1
    return MarketplaceOperationsDashboardRead(
        total_recommendations=len(rows),
        open_recommendations=open_count,
        by_type=by_type,
        by_status=by_status,
    )
