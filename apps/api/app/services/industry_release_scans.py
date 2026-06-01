from __future__ import annotations

from sqlmodel import Session, select

from app.models.industry_release_scan import IndustryReleaseCandidate, IndustryReleaseScanRun
from app.schemas.industry_release_scan import (
    IndustryReleaseCandidateRead,
    IndustryReleaseScanRunRead,
)


def _run_to_read(row: IndustryReleaseScanRun) -> IndustryReleaseScanRunRead:
    return IndustryReleaseScanRunRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        status=row.status,
        started_at=row.started_at.isoformat(),
        completed_at=row.completed_at.isoformat() if row.completed_at else None,
        releases_scanned=int(row.releases_scanned),
        candidates_created=int(row.candidates_created),
        candidates_total=int(row.candidates_total),
        publishers_included=int(row.publishers_included),
        error_message=row.error_message or "",
        created_at=row.created_at.isoformat(),
    )


def _candidate_to_read(row: IndustryReleaseCandidate) -> IndustryReleaseCandidateRead:
    return IndustryReleaseCandidateRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        scan_run_id=int(row.scan_run_id),
        release_id=int(row.release_id),
        publisher_code=row.publisher_code,
        publisher_name=row.publisher_name,
        series_name=row.series_name,
        issue_number=row.issue_number,
        foc_date=row.foc_date.isoformat() if row.foc_date else None,
        release_date=row.release_date.isoformat() if row.release_date else None,
        variant_count=int(row.variant_count),
        monitoring_status=row.monitoring_status,
        created_at=row.created_at.isoformat(),
    )


def list_industry_release_scans(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[IndustryReleaseScanRunRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = session.exec(
        select(IndustryReleaseScanRun)
        .where(IndustryReleaseScanRun.owner_user_id == owner_user_id)
        .order_by(IndustryReleaseScanRun.started_at.desc(), IndustryReleaseScanRun.id.desc())
    ).all()
    total = len(rows)
    page = rows[offset : offset + limit]
    return [_run_to_read(row) for row in page], total


def latest_scan_run_id(session: Session, *, owner_user_id: int) -> int | None:
    row = session.exec(
        select(IndustryReleaseScanRun)
        .where(IndustryReleaseScanRun.owner_user_id == owner_user_id)
        .where(IndustryReleaseScanRun.status == "SUCCESS")
        .order_by(IndustryReleaseScanRun.started_at.desc(), IndustryReleaseScanRun.id.desc())
    ).first()
    if row is None or row.id is None:
        return None
    return int(row.id)


def list_industry_release_candidates(
    session: Session,
    *,
    owner_user_id: int,
    scan_run_id: int | None = None,
    publisher_code: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[IndustryReleaseCandidateRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    run_id = scan_run_id
    if run_id is None:
        run_id = latest_scan_run_id(session, owner_user_id=owner_user_id)
    if run_id is None:
        return [], 0

    statement = (
        select(IndustryReleaseCandidate)
        .where(IndustryReleaseCandidate.owner_user_id == owner_user_id)
        .where(IndustryReleaseCandidate.scan_run_id == run_id)
    )
    if publisher_code:
        statement = statement.where(IndustryReleaseCandidate.publisher_code == publisher_code.strip().upper())
    rows = session.exec(
        statement.order_by(
            IndustryReleaseCandidate.publisher_name.asc(),
            IndustryReleaseCandidate.series_name.asc(),
            IndustryReleaseCandidate.issue_number.asc(),
        )
    ).all()
    total = len(rows)
    page = rows[offset : offset + limit]
    return [_candidate_to_read(row) for row in page], total
