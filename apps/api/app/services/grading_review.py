from __future__ import annotations

from sqlmodel import Session, select

from app.models.grading_intelligence import GradingRecommendationReview
from app.schemas.grading_intelligence import GradingRecommendationRead, GradingRecommendationReviewRead, GradingReviewResponse
from app.services.grading_intelligence import get_recommendation_for_owner


def _append_review(
    session: Session,
    *,
    recommendation_id: int,
    review_status: str,
    reviewed_by: int,
    review_notes: str,
) -> GradingRecommendationReviewRead:
    row = GradingRecommendationReview(
        recommendation_id=recommendation_id,
        review_status=review_status,
        reviewed_by=reviewed_by,
        review_notes=review_notes,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return GradingRecommendationReviewRead.model_validate(row)


def mark_reviewed(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_id: int,
    reviewed_by: int,
    review_notes: str = "",
) -> GradingReviewResponse:
    rec = get_recommendation_for_owner(session, recommendation_id=recommendation_id, owner_user_id=owner_user_id)
    review = _append_review(
        session,
        recommendation_id=int(rec.id),
        review_status="REVIEWED",
        reviewed_by=reviewed_by,
        review_notes=review_notes,
    )
    return GradingReviewResponse(recommendation=GradingRecommendationRead.model_validate(rec), review=review)


def mark_dismissed(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_id: int,
    reviewed_by: int,
    review_notes: str = "",
) -> GradingReviewResponse:
    rec = get_recommendation_for_owner(session, recommendation_id=recommendation_id, owner_user_id=owner_user_id)
    review = _append_review(
        session,
        recommendation_id=int(rec.id),
        review_status="DISMISSED",
        reviewed_by=reviewed_by,
        review_notes=review_notes,
    )
    return GradingReviewResponse(recommendation=GradingRecommendationRead.model_validate(rec), review=review)


def mark_accepted(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_id: int,
    reviewed_by: int,
    review_notes: str = "",
) -> GradingReviewResponse:
    rec = get_recommendation_for_owner(session, recommendation_id=recommendation_id, owner_user_id=owner_user_id)
    review = _append_review(
        session,
        recommendation_id=int(rec.id),
        review_status="ACCEPTED",
        reviewed_by=reviewed_by,
        review_notes=review_notes or "Advisory acceptance recorded; no automatic submission.",
    )
    return GradingReviewResponse(recommendation=GradingRecommendationRead.model_validate(rec), review=review)


def add_review_notes(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_id: int,
    reviewed_by: int,
    review_notes: str,
) -> GradingReviewResponse:
    return mark_reviewed(
        session,
        owner_user_id=owner_user_id,
        recommendation_id=recommendation_id,
        reviewed_by=reviewed_by,
        review_notes=review_notes,
    )


def list_reviews_for_recommendation(session: Session, *, recommendation_id: int) -> list[GradingRecommendationReviewRead]:
    rows = session.exec(
        select(GradingRecommendationReview)
        .where(GradingRecommendationReview.recommendation_id == recommendation_id)
        .order_by(GradingRecommendationReview.reviewed_at.desc(), GradingRecommendationReview.id.desc())
    ).all()
    return [GradingRecommendationReviewRead.model_validate(row) for row in rows]
