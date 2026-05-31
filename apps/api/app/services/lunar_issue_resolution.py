from __future__ import annotations

from sqlmodel import Session, select

from app.models.release_intelligence import ReleaseIssue, ReleaseVariant
from app.schemas.release_intelligence import ReleaseIssueImport
from app.services.lunar_issue_identity import is_canonical_lunar_issue_uuid


def _apply_issue_import(row: ReleaseIssue, payload: ReleaseIssueImport) -> None:
    row.issue_number = payload.issue_number
    row.title = payload.title
    if payload.foc_date is not None:
        row.foc_date = payload.foc_date
    if payload.release_date is not None:
        row.release_date = payload.release_date
    if payload.cover_price > 0:
        row.cover_price = payload.cover_price
    row.release_status = payload.release_status


def _release_uuid_in_use(
    session: Session,
    *,
    owner_user_id: int,
    release_uuid: str,
    exclude_issue_id: int | None,
) -> bool:
    query = (
        select(ReleaseIssue)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .where(ReleaseIssue.release_uuid == release_uuid)
    )
    if exclude_issue_id is not None:
        query = query.where(ReleaseIssue.id != exclude_issue_id)
    return session.exec(query).first() is not None


def _variant_count(session: Session, issue_id: int) -> int:
    return len(session.exec(select(ReleaseVariant.id).where(ReleaseVariant.issue_id == issue_id)).all())


def choose_canonical_issue_row(
    candidates: list[ReleaseIssue],
    *,
    preferred_release_uuid: str,
    variant_counts: dict[int, int] | None = None,
) -> ReleaseIssue:
    for row in candidates:
        if row.release_uuid == preferred_release_uuid:
            return row

    def sort_key(row: ReleaseIssue) -> tuple[int, int, int]:
        issue_id = int(row.id or 0)
        variants = (variant_counts or {}).get(issue_id, 0)
        canonical_rank = 0 if is_canonical_lunar_issue_uuid(row.release_uuid) else 1
        return (canonical_rank, -variants, issue_id)

    return min(candidates, key=sort_key)


def resolve_canonical_issue_for_import(
    session: Session,
    *,
    owner_user_id: int,
    series_id: int,
    payload: ReleaseIssueImport,
) -> tuple[ReleaseIssue | None, bool]:
    """Return (existing_row, matched_by_series_issue)."""
    by_uuid = session.exec(
        select(ReleaseIssue)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .where(ReleaseIssue.release_uuid == payload.release_uuid)
    ).first()
    if by_uuid is not None:
        return by_uuid, True

    siblings = session.exec(
        select(ReleaseIssue)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .where(ReleaseIssue.series_id == series_id)
        .where(ReleaseIssue.issue_number == payload.issue_number)
        .order_by(ReleaseIssue.id.asc())
    ).all()
    if not siblings:
        return None, False

    counts = {int(row.id or 0): _variant_count(session, int(row.id or 0)) for row in siblings}
    chosen = choose_canonical_issue_row(
        siblings,
        preferred_release_uuid=payload.release_uuid,
        variant_counts=counts,
    )
    if is_canonical_lunar_issue_uuid(chosen.release_uuid):
        return chosen, True

    if not _release_uuid_in_use(
        session,
        owner_user_id=owner_user_id,
        release_uuid=payload.release_uuid,
        exclude_issue_id=int(chosen.id or 0),
    ):
        chosen.release_uuid = payload.release_uuid

    return chosen, True


def maybe_promote_canonical_uuid(
    session: Session,
    *,
    owner_user_id: int,
    row: ReleaseIssue,
    payload: ReleaseIssueImport,
) -> None:
    if row.release_uuid == payload.release_uuid:
        return
    if is_canonical_lunar_issue_uuid(row.release_uuid):
        return
    if _release_uuid_in_use(
        session,
        owner_user_id=owner_user_id,
        release_uuid=payload.release_uuid,
        exclude_issue_id=int(row.id or 0),
    ):
        return
    row.release_uuid = payload.release_uuid
