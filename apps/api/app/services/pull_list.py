from __future__ import annotations

from datetime import date

from sqlmodel import Session, col, select

from app.models.pull_list import PullList, PullListIssue
from app.models.release_intelligence import ReleaseIssue
from app.schemas.pull_list import (
    PullListCreate,
    PullListDetailRead,
    PullListIssueAttachRequest,
    PullListIssueRead,
    PullListRead,
    PullListUpdate,
)

_UPCOMING_ACTION_STATES = {"UPCOMING", "FOC_APPROACHING"}


def derive_action_state(*, foc_date: date | None, release_date: date | None, today: date | None = None) -> str:
    if today is None:
        from app.services.foc_dates import utc_today

        today = utc_today()
    if release_date is not None and release_date <= today:
        return "RELEASED"
    if foc_date is not None and foc_date < today:
        return "MISSED"
    if foc_date is not None and foc_date >= today and (foc_date - today).days <= 14:
        return "FOC_APPROACHING"
    return "UPCOMING"


def sync_pull_list_issue_action_states(
    session: Session,
    *,
    owner_user_id: int,
    today: date | None = None,
) -> int:
    """Deterministically refresh pull-list issue FOC/release fields and action states."""
    if today is None:
        from app.services.foc_dates import utc_today

        today = utc_today()
    updated = 0
    rows = session.exec(
        select(PullListIssue)
        .join(PullList, PullList.id == PullListIssue.pull_list_id)
        .where(PullList.owner_user_id == owner_user_id)
    ).all()
    for pl_issue in rows:
        release = session.get(ReleaseIssue, pl_issue.release_id)
        foc_date = release.foc_date if release else pl_issue.foc_date
        release_date = release.release_date if release else pl_issue.release_date
        if release is not None:
            issue_number = release.issue_number
            title = release.title or ""
        else:
            issue_number = pl_issue.issue_number
            title = pl_issue.title
        new_state = derive_action_state(foc_date=foc_date, release_date=release_date, today=today)
        changed = (
            pl_issue.action_state != new_state
            or pl_issue.foc_date != foc_date
            or pl_issue.release_date != release_date
            or pl_issue.issue_number != issue_number
            or pl_issue.title != title
        )
        if not changed:
            continue
        pl_issue.foc_date = foc_date
        pl_issue.release_date = release_date
        pl_issue.issue_number = issue_number
        pl_issue.title = title
        pl_issue.action_state = new_state
        _touch(pl_issue)
        session.add(pl_issue)
        updated += 1
    if updated:
        session.commit()
    return updated


def _touch(row: PullList | PullListIssue) -> None:
    from app.models.pull_list import utc_now

    row.updated_at = utc_now()


def _upcoming_count(session: Session, *, pull_list_id: int) -> int:
    rows = session.exec(
        select(PullListIssue).where(
            PullListIssue.pull_list_id == pull_list_id,
            col(PullListIssue.action_state).in_(_UPCOMING_ACTION_STATES),
        )
    ).all()
    return len(rows)


def _to_read(session: Session, row: PullList) -> PullListRead:
    return PullListRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        publisher=row.publisher,
        series_name=row.series_name,
        canonical_series_id=row.canonical_series_id,
        status=row.status,  # type: ignore[arg-type]
        upcoming_issue_count=_upcoming_count(session, pull_list_id=int(row.id or 0)),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def create_pull_list(session: Session, *, owner_user_id: int, payload: PullListCreate) -> PullListDetailRead:
    row = PullList(
        owner_user_id=owner_user_id,
        publisher=payload.publisher.strip(),
        series_name=payload.series_name.strip(),
        canonical_series_id=payload.canonical_series_id,
        status=payload.status,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return get_pull_list(session, owner_user_id=owner_user_id, pull_list_id=int(row.id or 0))


def update_pull_list(
    session: Session,
    *,
    owner_user_id: int,
    pull_list_id: int,
    payload: PullListUpdate,
) -> PullListDetailRead:
    row = session.get(PullList, pull_list_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise ValueError("Pull list not found.")
    if payload.publisher is not None:
        row.publisher = payload.publisher.strip()
    if payload.series_name is not None:
        row.series_name = payload.series_name.strip()
    if "canonical_series_id" in payload.model_fields_set:
        row.canonical_series_id = payload.canonical_series_id
    if payload.status is not None:
        row.status = payload.status
    _touch(row)
    session.add(row)
    session.commit()
    session.refresh(row)
    return get_pull_list(session, owner_user_id=owner_user_id, pull_list_id=pull_list_id)


def list_pull_lists(
    session: Session,
    *,
    owner_user_id: int,
    status: str | None = None,
    publisher: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[PullListRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    stmt = select(PullList).where(PullList.owner_user_id == owner_user_id)
    if status:
        stmt = stmt.where(PullList.status == status.strip().upper())
    if publisher:
        stmt = stmt.where(PullList.publisher.ilike(f"%{publisher.strip()}%"))  # type: ignore[attr-defined]
    if search:
        term = f"%{search.strip()}%"
        stmt = stmt.where(
            (PullList.series_name.ilike(term)) | (PullList.publisher.ilike(term))  # type: ignore[attr-defined]
        )
    rows = session.exec(stmt.order_by(PullList.updated_at.desc(), PullList.id.desc())).all()
    total = len(rows)
    page = rows[offset : offset + limit]
    return [_to_read(session, row) for row in page], total


def get_pull_list(session: Session, *, owner_user_id: int, pull_list_id: int) -> PullListDetailRead:
    row = session.get(PullList, pull_list_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise ValueError("Pull list not found.")
    issues = session.exec(
        select(PullListIssue)
        .where(PullListIssue.pull_list_id == pull_list_id)
        .order_by(PullListIssue.release_date, PullListIssue.id)
    ).all()
    return PullListDetailRead(
        pull_list=_to_read(session, row),
        issues=[PullListIssueRead.model_validate(issue) for issue in issues],
    )


def attach_release_to_pull_list(
    session: Session,
    *,
    owner_user_id: int,
    pull_list_id: int,
    payload: PullListIssueAttachRequest,
) -> PullListDetailRead:
    pull_list = session.get(PullList, pull_list_id)
    if pull_list is None or pull_list.owner_user_id != owner_user_id:
        raise ValueError("Pull list not found.")
    release = session.get(ReleaseIssue, payload.release_id)
    if release is None or release.owner_user_id != owner_user_id:
        raise ValueError("Release not found.")
    existing = session.exec(
        select(PullListIssue).where(
            PullListIssue.pull_list_id == pull_list_id,
            PullListIssue.release_id == payload.release_id,
        )
    ).first()
    action = derive_action_state(foc_date=release.foc_date, release_date=release.release_date)
    if existing is not None:
        existing.issue_number = release.issue_number
        existing.title = release.title or ""
        existing.release_date = release.release_date
        existing.foc_date = release.foc_date
        existing.action_state = action
        _touch(existing)
        session.add(existing)
    else:
        session.add(
            PullListIssue(
                pull_list_id=pull_list_id,
                release_id=int(release.id or 0),
                issue_number=release.issue_number,
                title=release.title or "",
                release_date=release.release_date,
                foc_date=release.foc_date,
                action_state=action,
            )
        )
    _touch(pull_list)
    session.add(pull_list)
    session.commit()
    return get_pull_list(session, owner_user_id=owner_user_id, pull_list_id=pull_list_id)
