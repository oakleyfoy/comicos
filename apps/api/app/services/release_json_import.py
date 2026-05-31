from __future__ import annotations

from datetime import datetime, timezone

from pydantic import ValidationError
from sqlmodel import Session

from app.models.release_imports import ReleaseImportError, ReleaseImportFile, ReleaseImportRun
from app.schemas.release_imports import ReleaseImportRunRead
from app.schemas.release_intelligence import ReleaseImportFeedRequest, ReleaseImportResult
from app.services.release_import import import_release_feed

IMPORT_TYPE_JSON = "JSON"
IMPORT_TYPE_CSV = "CSV"

STATUS_RUNNING = "RUNNING"
STATUS_COMPLETED = "COMPLETED"
STATUS_FAILED = "FAILED"
STATUS_PARTIAL = "PARTIAL"


def validate_json_feed(raw: object) -> tuple[ReleaseImportFeedRequest | None, list[tuple[str, str, str]]]:
    errors: list[tuple[str, str, str]] = []
    if not isinstance(raw, dict):
        return None, [("", "INVALID_JSON", "Feed must be a JSON object")]
    try:
        if "feed" in raw and isinstance(raw["feed"], dict):
            payload = ReleaseImportFeedRequest.model_validate(raw["feed"])
            return payload, errors
        payload = ReleaseImportFeedRequest.model_validate(raw)
        return payload, errors
    except ValidationError as exc:
        for item in exc.errors():
            loc = ".".join(str(part) for part in item.get("loc", ()))
            errors.append((loc or "feed", "VALIDATION_ERROR", item.get("msg", "Invalid feed")))
        return None, errors


def _count_issue_records(payload: ReleaseImportFeedRequest) -> int:
    return sum(len(series.issues) for series in payload.series)


def record_import_results(
    session: Session,
    *,
    run: ReleaseImportRun,
    result: ReleaseImportResult | None,
    records_processed: int,
    records_failed: int,
    errors: list[tuple[str, str, str]],
) -> ReleaseImportRun:
    if result is not None:
        run.records_created = result.issues_created + result.series_created + result.variants_created
        run.records_updated = result.issues_matched + result.series_matched + result.variants_matched
    run.records_processed = records_processed
    run.records_failed = records_failed
    if records_failed and result is None:
        run.status = STATUS_FAILED
    elif records_failed:
        run.status = STATUS_PARTIAL
    else:
        run.status = STATUS_COMPLETED
    run.completed_at = datetime.now(timezone.utc)
    session.add(run)
    for record_identifier, error_code, error_message in errors:
        session.add(
            ReleaseImportError(
                import_run_id=int(run.id or 0),
                record_identifier=record_identifier,
                error_code=error_code,
                error_message=error_message,
            )
        )
    session.commit()
    session.refresh(run)
    return run


def begin_import_run(
    session: Session,
    *,
    owner_user_id: int,
    import_type: str,
    file_name: str,
    file_type: str,
    file_size: int,
) -> tuple[ReleaseImportRun, ReleaseImportFile]:
    run = ReleaseImportRun(
        owner_user_id=owner_user_id,
        import_type=import_type,
        file_name=file_name,
        status=STATUS_RUNNING,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    file_row = ReleaseImportFile(
        import_run_id=int(run.id or 0),
        file_name=file_name,
        file_type=file_type,
        file_size=file_size,
    )
    session.add(file_row)
    session.commit()
    session.refresh(file_row)
    return run, file_row


def import_json_feed(
    session: Session,
    *,
    owner_user_id: int,
    file_name: str,
    raw_feed: object,
    file_size: int = 0,
) -> tuple[ReleaseImportRunRead, ReleaseImportResult | None]:
    run, _ = begin_import_run(
        session,
        owner_user_id=owner_user_id,
        import_type=IMPORT_TYPE_JSON,
        file_name=file_name,
        file_type="JSON",
        file_size=file_size,
    )
    payload, validation_errors = validate_json_feed(raw_feed if isinstance(raw_feed, dict) else {"feed": raw_feed})
    if payload is None:
        run = record_import_results(
            session,
            run=run,
            result=None,
            records_processed=0,
            records_failed=len(validation_errors),
            errors=validation_errors,
        )
        return ReleaseImportRunRead.model_validate(run), None

    records_processed = _count_issue_records(payload)
    try:
        result = import_release_feed(session, owner_user_id=owner_user_id, payload=payload)
    except Exception as exc:  # noqa: BLE001
        run = record_import_results(
            session,
            run=run,
            result=None,
            records_processed=records_processed,
            records_failed=1,
            errors=[("feed", "IMPORT_ERROR", str(exc))],
        )
        return ReleaseImportRunRead.model_validate(run), None

    run = record_import_results(
        session,
        run=run,
        result=result,
        records_processed=records_processed,
        records_failed=0,
        errors=[],
    )
    return ReleaseImportRunRead.model_validate(run), result
