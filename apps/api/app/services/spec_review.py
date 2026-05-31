from __future__ import annotations

from sqlmodel import Session, select

from app.models.spec_intelligence import SpecRecommendationReview
from app.schemas.spec_intelligence import SpecRecommendationRead, SpecRecommendationReviewRead, SpecReviewResponse
from app.services.spec_intelligence import get_recommendation_for_owner


def _append_review(
    session: Session,
    *,
    recommendation_id: int,
    review_status: str,
    review_notes: str,
) -> SpecRecommendationReviewRead:
    row = SpecRecommendationReview(
        recommendation_id=recommendation_id,
        review_status=review_status,
        review_notes=review_notes,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return SpecRecommendationReviewRead.model_validate(row)


def mark_reviewed(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_id: int,
    review_notes: str = "",
) -> SpecReviewResponse:
    rec = get_recommendation_for_owner(session, recommendation_id=recommendation_id, owner_user_id=owner_user_id)
    review = _append_review(
        session,
        recommendation_id=int(rec.id or 0),
        review_status="REVIEWED",
        review_notes=review_notes,
    )
    return SpecReviewResponse(recommendation=SpecRecommendationRead.model_validate(rec), review=review)


def mark_accepted(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_id: int,
    review_notes: str = "",
) -> SpecReviewResponse:
    rec = get_recommendation_for_owner(session, recommendation_id=recommendation_id, owner_user_id=owner_user_id)
    review = _append_review(
        session,
        recommendation_id=int(rec.id or 0),
        review_status="ACCEPTED",
        review_notes=review_notes or "Advisory acceptance recorded; no automatic order submission.",
    )
    return SpecReviewResponse(recommendation=SpecRecommendationRead.model_validate(rec), review=review)


def mark_dismissed(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_id: int,
    review_notes: str = "",
) -> SpecReviewResponse:
    rec = get_recommendation_for_owner(session, recommendation_id=recommendation_id, owner_user_id=owner_user_id)
    review = _append_review(
        session,
        recommendation_id=int(rec.id or 0),
        review_status="DISMISSED",
        review_notes=review_notes,
    )
    return SpecReviewResponse(recommendation=SpecRecommendationRead.model_validate(rec), review=review)


def add_review_notes(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_id: int,
    review_notes: str,
) -> SpecReviewResponse:
    return mark_reviewed(
        session,
        owner_user_id=owner_user_id,
        recommendation_id=recommendation_id,
        review_notes=review_notes,
    )


def list_reviews_for_owner(session: Session, *, owner_user_id: int, limit: int = 50) -> list[SpecRecommendationReviewRead]:
    from app.models.release_intelligence import ReleaseIssue
    from app.models.spec_intelligence import SpecRecommendation

    rows = session.exec(
        select(SpecRecommendationReview)
        .join(SpecRecommendation, SpecRecommendationReview.recommendation_id == SpecRecommendation.id)
        .join(ReleaseIssue, SpecRecommendation.release_issue_id == ReleaseIssue.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .order_by(SpecRecommendationReview.reviewed_at.desc(), SpecRecommendationReview.id.desc())
    ).all()
    return [SpecRecommendationReviewRead.model_validate(row) for row in rows[:limit]]
