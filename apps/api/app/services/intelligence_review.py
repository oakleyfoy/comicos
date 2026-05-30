from __future__ import annotations

from fastapi import HTTPException
from sqlmodel import Session

from app.models import AgentExecution, IntelligenceRecommendationReview
from app.schemas.intelligence import IntelligenceRecommendationDetail, IntelligenceRecommendationReviewRead
from app.services.agent_permissions import RECOMMENDATION_REVIEW_CAPABILITY, check_permission
from app.services.intelligence_engine import (
    REVIEW_STATUS_ACCEPTED,
    REVIEW_STATUS_DISMISSED,
    REVIEW_STATUS_NOTED,
    REVIEW_STATUS_REVIEWED,
    _visible_recommendation_row,
    get_recommendation_detail_for_owner,
)


def _review_read(row: IntelligenceRecommendationReview) -> IntelligenceRecommendationReviewRead:
    return IntelligenceRecommendationReviewRead(
        id=int(row.id or 0),
        recommendation_id=row.recommendation_id,
        review_status=row.review_status,
        reviewed_by=row.reviewed_by,
        reviewed_at=row.reviewed_at,
        review_notes=row.review_notes,
    )


def _execution_agent_id(session: Session, *, agent_execution_id: int) -> int:
    row = session.get(AgentExecution, agent_execution_id)
    if row is None:
        raise RuntimeError("Agent execution for recommendation review was not found.")
    return row.agent_id


def _enforce_review_permission(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_id: int,
    review_status: str,
) -> None:
    recommendation = _visible_recommendation_row(
        session,
        owner_user_id=owner_user_id,
        recommendation_id=recommendation_id,
    )
    agent_id = _execution_agent_id(session, agent_execution_id=recommendation.agent_execution_id)
    action_code = f"intelligence_{review_status.strip().lower()}"
    review_scope = "admin" if review_status == REVIEW_STATUS_ACCEPTED else "review"
    review_check = check_permission(
        session,
        agent_id=agent_id,
        execution_id=recommendation.agent_execution_id,
        capability_code=RECOMMENDATION_REVIEW_CAPABILITY,
        permission_scope=review_scope,
        action_code=action_code,
        event_payload_json={
            "owner_user_id": owner_user_id,
            "recommendation_id": recommendation_id,
            "review_status": review_status,
        },
    )
    if not review_check.allowed:
        raise HTTPException(status_code=403, detail=f"Recommendation review denied: {review_check.reason}.")


def _append_review(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_id: int,
    reviewed_by: str,
    review_status: str,
    review_notes: str | None = None,
) -> IntelligenceRecommendationDetail:
    _enforce_review_permission(
        session,
        owner_user_id=owner_user_id,
        recommendation_id=recommendation_id,
        review_status=review_status,
    )
    row = _visible_recommendation_row(
        session,
        owner_user_id=owner_user_id,
        recommendation_id=recommendation_id,
    )
    review = IntelligenceRecommendationReview(
        recommendation_id=int(row.id or 0),
        review_status=review_status,
        reviewed_by=reviewed_by.strip(),
        review_notes=(review_notes or "").strip() or None,
    )
    session.add(review)
    session.commit()
    session.refresh(review)
    return get_recommendation_detail_for_owner(
        session,
        owner_user_id=owner_user_id,
        recommendation_id=int(row.id or 0),
    )


def mark_reviewed(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_id: int,
    reviewed_by: str,
    review_notes: str | None = None,
) -> IntelligenceRecommendationDetail:
    return _append_review(
        session,
        owner_user_id=owner_user_id,
        recommendation_id=recommendation_id,
        reviewed_by=reviewed_by,
        review_status=REVIEW_STATUS_REVIEWED,
        review_notes=review_notes,
    )


def mark_dismissed(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_id: int,
    reviewed_by: str,
    review_notes: str | None = None,
) -> IntelligenceRecommendationDetail:
    return _append_review(
        session,
        owner_user_id=owner_user_id,
        recommendation_id=recommendation_id,
        reviewed_by=reviewed_by,
        review_status=REVIEW_STATUS_DISMISSED,
        review_notes=review_notes,
    )


def mark_accepted(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_id: int,
    reviewed_by: str,
    review_notes: str | None = None,
) -> IntelligenceRecommendationDetail:
    return _append_review(
        session,
        owner_user_id=owner_user_id,
        recommendation_id=recommendation_id,
        reviewed_by=reviewed_by,
        review_status=REVIEW_STATUS_ACCEPTED,
        review_notes=review_notes,
    )


def add_review_notes(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_id: int,
    reviewed_by: str,
    review_notes: str,
) -> IntelligenceRecommendationDetail:
    return _append_review(
        session,
        owner_user_id=owner_user_id,
        recommendation_id=recommendation_id,
        reviewed_by=reviewed_by,
        review_status=REVIEW_STATUS_NOTED,
        review_notes=review_notes,
    )
