from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session

from app.models.lunar_feed import LunarFeedError, LunarFeedRawRow, LunarFeedRun
from app.schemas.lunar_feed import LunarFeedImportSummaryRead
from app.services.lunar_authenticated_client import LunarAuthenticatedClient
from app.services.lunar_csv_parser import parse_lunar_product_csv, row_product_code
from app.services.lunar_feed_downloader import download_latest_monthly_products_csv
from app.services.lunar_foc_intelligence import generate_foc_alerts
from app.services.lunar_release_normalizer import normalize_lunar_rows
from app.services.release_import import import_release_feed

STATUS_RUNNING = "RUNNING"
STATUS_COMPLETED = "COMPLETED"
STATUS_FAILED = "FAILED"
STATUS_PARTIAL = "PARTIAL"
SOURCE_REMOTE = "REMOTE"
SOURCE_UPLOAD = "UPLOAD"


def _begin_run(
    session: Session,
    *,
    owner_user_id: int,
    source_type: str,
    file_name: str,
    file_period: str,
    source_url: str,
) -> LunarFeedRun:
    run = LunarFeedRun(
        owner_user_id=owner_user_id,
        source_type=source_type,
        file_name=file_name,
        file_period=file_period,
        status=STATUS_RUNNING,
        source_url=source_url,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def _finalize_run(
    session: Session,
    *,
    run: LunarFeedRun,
    records_processed: int,
    records_created: int,
    records_updated: int,
    records_failed: int,
    foc_alerts_created: int,
    status: str,
) -> LunarFeedRun:
    run.records_processed = records_processed
    run.records_created = records_created
    run.records_updated = records_updated
    run.records_failed = records_failed
    run.foc_alerts_created = foc_alerts_created
    run.status = status
    run.completed_at = datetime.now(timezone.utc)
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def _store_raw_rows(session: Session, *, run_id: int, rows: list[dict[str, str]]) -> None:
    for index, row in enumerate(rows, start=1):
        session.add(
            LunarFeedRawRow(
                feed_run_id=run_id,
                row_index=index,
                product_code=row_product_code(row),
                row_payload_json=row,
            )
        )
    session.commit()


def _store_errors(session: Session, *, run_id: int, errors: list[tuple[str, str, str]]) -> None:
    for record_identifier, error_code, error_message in errors:
        session.add(
            LunarFeedError(
                feed_run_id=run_id,
                record_identifier=record_identifier,
                error_code=error_code,
                error_message=error_message,
            )
        )
    session.commit()


def import_lunar_csv_bytes(
    session: Session,
    *,
    owner_user_id: int,
    file_name: str,
    content_bytes: bytes,
    file_period: str = "",
    source_type: str = SOURCE_UPLOAD,
    source_url: str = "",
) -> LunarFeedImportSummaryRead:
    run = _begin_run(
        session,
        owner_user_id=owner_user_id,
        source_type=source_type,
        file_name=file_name,
        file_period=file_period,
        source_url=source_url,
    )
    try:
        rows = parse_lunar_product_csv(content_bytes)
        feed, validation_errors = normalize_lunar_rows(rows)
        _store_raw_rows(session, run_id=int(run.id or 0), rows=rows)
        result = import_release_feed(session, owner_user_id=owner_user_id, payload=feed)
        foc_alerts = generate_foc_alerts(
            session,
            owner_user_id=owner_user_id,
            feed_run_id=int(run.id or 0),
            rows=rows,
        )
        _store_errors(session, run_id=int(run.id or 0), errors=validation_errors)
        status = STATUS_PARTIAL if validation_errors else STATUS_COMPLETED
        run = _finalize_run(
            session,
            run=run,
            records_processed=len(rows),
            records_created=result.issues_created + result.series_created + result.variants_created,
            records_updated=result.issues_matched + result.series_matched + result.variants_matched,
            records_failed=len(validation_errors),
            foc_alerts_created=len(foc_alerts),
            status=status,
        )
        return LunarFeedImportSummaryRead.from_run(run, errors=validation_errors)
    except Exception as exc:  # noqa: BLE001
        _store_errors(session, run_id=int(run.id or 0), errors=[("feed", "IMPORT_ERROR", str(exc))])
        run = _finalize_run(
            session,
            run=run,
            records_processed=0,
            records_created=0,
            records_updated=0,
            records_failed=1,
            foc_alerts_created=0,
            status=STATUS_FAILED,
        )
        return LunarFeedImportSummaryRead.from_run(run, errors=[("feed", "IMPORT_ERROR", str(exc))])


def import_latest_lunar_csv_from_remote(
    session: Session,
    *,
    owner_user_id: int,
    client: LunarAuthenticatedClient | None = None,
) -> LunarFeedImportSummaryRead:
    downloaded = download_latest_monthly_products_csv(client=client)
    return import_lunar_csv_bytes(
        session,
        owner_user_id=owner_user_id,
        file_name=downloaded.file_name,
        content_bytes=downloaded.content_bytes,
        file_period=downloaded.file_period,
        source_type=SOURCE_REMOTE,
        source_url=downloaded.source_url,
    )
