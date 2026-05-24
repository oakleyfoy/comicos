from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from app.models import DuplicateCandidateReview, InventoryCopy, User
from app.schemas.duplicate_candidate_review import DuplicateCandidateReviewRead


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_notes_field(notes: str | None) -> str | None:
    if notes is None:
        return None
    trimmed = notes.strip()
    return trimmed or None


def _count_inventory_for_duplicate_key(session: Session, metadata_identity_key: str) -> int:
    stmt = select(func.count(InventoryCopy.id)).where(
        InventoryCopy.metadata_identity_key == metadata_identity_key,
        InventoryCopy.metadata_identity_key.is_not(None),
        InventoryCopy.metadata_identity_key != "",
    )
    result = session.exec(stmt).one()
    return int(result or 0)


def assert_metadata_key_is_duplicate_candidate(session: Session, metadata_identity_key: str) -> int:
    count = _count_inventory_for_duplicate_key(session, metadata_identity_key)
    if count < 2:
        raise HTTPException(
            status_code=404,
            detail=(
                "No duplicate candidate group for this metadata_identity_key "
                "(requires two or more inventory copies)."
            ),
        )
    return count


def load_reviews_for_keys(
    session: Session, identity_keys: list[str]
) -> dict[str, DuplicateCandidateReview]:
    if not identity_keys:
        return {}

    rows = session.exec(
        select(DuplicateCandidateReview).where(
            DuplicateCandidateReview.metadata_identity_key.in_(identity_keys)
        )
    ).all()

    reviews: dict[str, DuplicateCandidateReview] = {}
    for row in rows:
        if row.metadata_identity_key not in reviews and row.metadata_identity_key is not None:
            reviews[row.metadata_identity_key] = row
    return reviews


def serialize_duplicate_candidate_review_read(
    session: Session,
    record: DuplicateCandidateReview,
) -> DuplicateCandidateReviewRead:
    emails = reviewer_email_map(
        session, {record.reviewed_by_user_id} if record.reviewed_by_user_id else set()
    )
    return DuplicateCandidateReviewRead(
        metadata_identity_key=record.metadata_identity_key,
        review_status=record.review_status,
        notes=record.notes,
        reviewed_by_user_id=record.reviewed_by_user_id,
        reviewed_by_email=emails.get(record.reviewed_by_user_id)
        if record.reviewed_by_user_id is not None
        else None,
        reviewed_at=record.reviewed_at,
        created_at=record.created_at,
    )


def reviewer_email_map(session: Session, reviewer_ids: set[int]) -> dict[int, str]:
    normalized = {user_id for user_id in reviewer_ids if user_id is not None}
    if not normalized:
        return {}
    users = session.exec(select(User).where(User.id.in_(normalized))).all()
    return {user.id: user.email for user in users if user.id is not None}


def upsert_mark_duplicate_review(
    session: Session,
    *,
    metadata_identity_key: str,
    review_status: str,
    notes: str | None,
    notes_provided: bool,
    reviewed_by_user: User,
) -> DuplicateCandidateReview:
    assert_metadata_key_is_duplicate_candidate(session, metadata_identity_key)

    now = utc_now()
    existing = session.exec(
        select(DuplicateCandidateReview).where(
            DuplicateCandidateReview.metadata_identity_key == metadata_identity_key
        )
    ).first()

    if existing is None:
        entity = DuplicateCandidateReview(
            metadata_identity_key=metadata_identity_key,
            review_status=review_status,
            notes=_normalize_notes_field(notes) if notes_provided else None,
            reviewed_by_user_id=reviewed_by_user.id,
            reviewed_at=now,
            created_at=now,
        )
        session.add(entity)
        session.commit()
        session.refresh(entity)
        return entity

    existing.review_status = review_status
    if notes_provided:
        existing.notes = _normalize_notes_field(notes)
    existing.reviewed_by_user_id = reviewed_by_user.id
    existing.reviewed_at = now
    session.add(existing)
    session.commit()
    session.refresh(existing)
    return existing


def upsert_duplicate_review_notes(
    session: Session,
    *,
    metadata_identity_key: str,
    notes: str | None,
    reviewer: User,
) -> DuplicateCandidateReview:
    """
    Persist notes without changing resolved review status markers (confirmed / not duplicate).
    If no review row exists yet, creates one in pending state without confirming duplicates.
    """
    assert_metadata_key_is_duplicate_candidate(session, metadata_identity_key)

    now = utc_now()
    existing = session.exec(
        select(DuplicateCandidateReview).where(
            DuplicateCandidateReview.metadata_identity_key == metadata_identity_key
        )
    ).first()

    trimmed = _normalize_notes_field(notes)

    if existing is None:
        entity = DuplicateCandidateReview(
            metadata_identity_key=metadata_identity_key,
            review_status="pending",
            notes=trimmed,
            reviewed_by_user_id=reviewer.id,
            reviewed_at=now,
            created_at=now,
        )
        session.add(entity)
        session.commit()
        session.refresh(entity)
        return entity

    existing.notes = trimmed
    existing.reviewed_by_user_id = reviewer.id
    existing.reviewed_at = now
    session.add(existing)
    session.commit()
    session.refresh(existing)
    return existing


