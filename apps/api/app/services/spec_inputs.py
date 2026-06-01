from __future__ import annotations

from sqlmodel import Session, select

from app.models.spec_input import SpecInput
from app.schemas.spec_input import SpecInputLatestRead, SpecInputRead, SpecInputSummaryRead
from app.services.spec_input_builder import _parse_source_systems, build_spec_inputs


def _to_read(row: SpecInput) -> SpecInputRead:
    return SpecInputRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        release_id=int(row.release_id) if row.release_id is not None else None,
        industry_candidate_id=int(row.industry_candidate_id) if row.industry_candidate_id is not None else None,
        future_release_match_id=int(row.future_release_match_id) if row.future_release_match_id is not None else None,
        title=row.title,
        publisher=row.publisher,
        series_name=row.series_name,
        issue_number=row.issue_number,
        foc_date=row.foc_date.isoformat() if row.foc_date else None,
        release_date=row.release_date.isoformat() if row.release_date else None,
        source_systems=_parse_source_systems(row.source_systems),
        signal_summary=row.signal_summary,
        created_at=row.created_at.isoformat(),
    )


def list_spec_inputs(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[SpecInputRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = session.exec(
        select(SpecInput)
        .where(SpecInput.owner_user_id == owner_user_id)
        .order_by(SpecInput.created_at.desc(), SpecInput.id.desc())
    ).all()
    total = len(rows)
    page = rows[offset : offset + limit]
    return [_to_read(row) for row in page], total


def refresh_latest_spec_inputs(session: Session, *, owner_user_id: int) -> SpecInputLatestRead:
    build_result = build_spec_inputs(session, owner_user_id=owner_user_id)
    items, _ = list_spec_inputs(session, owner_user_id=owner_user_id, limit=200, offset=0)
    return SpecInputLatestRead(
        items=items,
        inputs_created=build_result.created,
        inputs_skipped=build_result.skipped,
        inputs_updated=build_result.updated,
    )


def build_spec_input_summary(session: Session, *, owner_user_id: int) -> SpecInputSummaryRead:
    rows = session.exec(select(SpecInput).where(SpecInput.owner_user_id == owner_user_id)).all()
    source_counts: dict[str, int] = {}
    release_ids: set[int] = set()
    with_candidate = 0
    with_match = 0
    for row in rows:
        if row.release_id is not None:
            release_ids.add(int(row.release_id))
        if row.industry_candidate_id is not None:
            with_candidate += 1
        if row.future_release_match_id is not None:
            with_match += 1
        for system in _parse_source_systems(row.source_systems):
            source_counts[system] = source_counts.get(system, 0) + 1
    return SpecInputSummaryRead(
        total_inputs=len(rows),
        unique_releases=len(release_ids),
        with_industry_candidate=with_candidate,
        with_future_match=with_match,
        source_system_counts=source_counts,
    )
