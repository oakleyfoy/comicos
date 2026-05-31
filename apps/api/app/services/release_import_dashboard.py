from __future__ import annotations

from sqlmodel import Session, select

from app.models.release_imports import ReleaseImportError, ReleaseImportFile, ReleaseImportRun
from app.schemas.release_imports import (
    ReleaseImportDashboardRead,
    ReleaseImportErrorRead,
    ReleaseImportFileRead,
    ReleaseImportRunDetailRead,
    ReleaseImportRunRead,
)
from app.services.release_json_import import STATUS_COMPLETED, STATUS_FAILED, STATUS_PARTIAL


def build_release_import_dashboard(session: Session, *, owner_user_id: int) -> ReleaseImportDashboardRead:
    runs = session.exec(
        select(ReleaseImportRun)
        .where(ReleaseImportRun.owner_user_id == owner_user_id)
        .order_by(ReleaseImportRun.created_at.desc(), ReleaseImportRun.id.desc())
    ).all()
    recent = [ReleaseImportRunRead.model_validate(row) for row in runs[:10]]

    completed = [row for row in runs if row.status == STATUS_COMPLETED]
    partial = [row for row in runs if row.status == STATUS_PARTIAL]
    failed = [row for row in runs if row.status == STATUS_FAILED]
    success_denominator = len(completed) + len(partial) + len(failed)
    success_rate = round(len(completed) / success_denominator, 3) if success_denominator else 1.0

    files = session.exec(
        select(ReleaseImportFile)
        .join(ReleaseImportRun, ReleaseImportFile.import_run_id == ReleaseImportRun.id)
        .where(ReleaseImportRun.owner_user_id == owner_user_id)
        .order_by(ReleaseImportFile.created_at.desc(), ReleaseImportFile.id.desc())
        .limit(10)
    ).all()
    latest_uploads = [ReleaseImportFileRead.model_validate(row) for row in files]

    error_rows = session.exec(
        select(ReleaseImportError)
        .join(ReleaseImportRun, ReleaseImportError.import_run_id == ReleaseImportRun.id)
        .where(ReleaseImportRun.owner_user_id == owner_user_id)
        .order_by(ReleaseImportError.created_at.desc(), ReleaseImportError.id.desc())
        .limit(200)
    ).all()
    summary_counts: dict[str, int] = {}
    for row in error_rows:
        summary_counts[row.error_code] = summary_counts.get(row.error_code, 0) + 1
    error_summary = [
        {"error_code": code, "count": count}
        for code, count in sorted(summary_counts.items(), key=lambda item: item[1], reverse=True)[:10]
    ]

    return ReleaseImportDashboardRead(
        recent_imports=recent,
        import_success_rate=success_rate,
        import_failures=len(failed) + len(partial),
        latest_uploads=latest_uploads,
        error_summary=error_summary,
    )


def list_import_runs_for_owner(session: Session, *, owner_user_id: int, limit: int = 50, offset: int = 0):
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = session.exec(
        select(ReleaseImportRun)
        .where(ReleaseImportRun.owner_user_id == owner_user_id)
        .order_by(ReleaseImportRun.created_at.desc(), ReleaseImportRun.id.desc())
    ).all()
    page = rows[offset : offset + limit]
    return [ReleaseImportRunRead.model_validate(row) for row in page], len(rows)


def get_import_run_detail(session: Session, *, owner_user_id: int, run_id: int):
    run = session.get(ReleaseImportRun, run_id)
    if run is None or run.owner_user_id != owner_user_id:
        return None
    files = session.exec(
        select(ReleaseImportFile)
        .where(ReleaseImportFile.import_run_id == run_id)
        .order_by(ReleaseImportFile.created_at.desc(), ReleaseImportFile.id.desc())
    ).all()
    errors = session.exec(
        select(ReleaseImportError)
        .where(ReleaseImportError.import_run_id == run_id)
        .order_by(ReleaseImportError.created_at.desc(), ReleaseImportError.id.desc())
    ).all()
    return ReleaseImportRunDetailRead(
        run=ReleaseImportRunRead.model_validate(run),
        files=[ReleaseImportFileRead.model_validate(row) for row in files],
        errors=[ReleaseImportErrorRead.model_validate(row) for row in errors],
    )


def list_import_errors_for_owner(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
    import_run_id: int | None = None,
):
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    query = (
        select(ReleaseImportError)
        .join(ReleaseImportRun, ReleaseImportError.import_run_id == ReleaseImportRun.id)
        .where(ReleaseImportRun.owner_user_id == owner_user_id)
    )
    if import_run_id is not None:
        query = query.where(ReleaseImportError.import_run_id == import_run_id)
    rows = session.exec(query.order_by(ReleaseImportError.created_at.desc(), ReleaseImportError.id.desc())).all()
    page = rows[offset : offset + limit]
    return [ReleaseImportErrorRead.model_validate(row) for row in page], len(rows)
