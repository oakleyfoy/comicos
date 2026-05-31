from __future__ import annotations

from sqlmodel import Session, select

from app.models.release_intelligence import ReleaseIssue, ReleaseVariant
from app.schemas.release_intelligence import ReleaseVariantRead


def count_variants_for_owner(session: Session, *, owner_user_id: int) -> int:
    issue_ids = [
        int(x)
        for x in session.exec(select(ReleaseIssue.id).where(ReleaseIssue.owner_user_id == owner_user_id)).all()
        if x
    ]
    if not issue_ids:
        return 0
    return len(session.exec(select(ReleaseVariant).where(ReleaseVariant.issue_id.in_(issue_ids))).all())


def count_ratio_variants_for_owner(session: Session, *, owner_user_id: int) -> int:
    issue_ids = [
        int(x)
        for x in session.exec(select(ReleaseIssue.id).where(ReleaseIssue.owner_user_id == owner_user_id)).all()
        if x
    ]
    if not issue_ids:
        return 0
    rows = session.exec(
        select(ReleaseVariant)
        .where(ReleaseVariant.issue_id.in_(issue_ids))
        .where(ReleaseVariant.is_incentive_variant.is_(True))
    ).all()
    return len(rows)


def count_cover_variants_for_owner(session: Session, *, owner_user_id: int) -> int:
    issue_ids = [
        int(x)
        for x in session.exec(select(ReleaseIssue.id).where(ReleaseIssue.owner_user_id == owner_user_id)).all()
        if x
    ]
    if not issue_ids:
        return 0
    rows = session.exec(
        select(ReleaseVariant)
        .where(ReleaseVariant.issue_id.in_(issue_ids))
        .where(ReleaseVariant.variant_type == "COVER")
    ).all()
    return len(rows)


def list_recent_variants(session: Session, *, owner_user_id: int, limit: int = 10) -> list[ReleaseVariantRead]:
    issue_ids = [
        int(x)
        for x in session.exec(select(ReleaseIssue.id).where(ReleaseIssue.owner_user_id == owner_user_id)).all()
        if x
    ]
    if not issue_ids:
        return []
    rows = session.exec(
        select(ReleaseVariant)
        .where(ReleaseVariant.issue_id.in_(issue_ids))
        .order_by(ReleaseVariant.created_at.desc(), ReleaseVariant.id.desc())
        .limit(limit)
    ).all()
    return [ReleaseVariantRead.model_validate(row) for row in rows]


def list_top_ratio_variants(session: Session, *, owner_user_id: int, limit: int = 10) -> list[ReleaseVariantRead]:
    issue_ids = [
        int(x)
        for x in session.exec(select(ReleaseIssue.id).where(ReleaseIssue.owner_user_id == owner_user_id)).all()
        if x
    ]
    if not issue_ids:
        return []
    rows = session.exec(
        select(ReleaseVariant)
        .where(ReleaseVariant.issue_id.in_(issue_ids))
        .where(ReleaseVariant.ratio_value.is_not(None))
        .order_by(ReleaseVariant.ratio_value.desc(), ReleaseVariant.created_at.desc())
        .limit(limit)
    ).all()
    return [ReleaseVariantRead.model_validate(row) for row in rows]
