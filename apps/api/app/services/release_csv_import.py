from __future__ import annotations

import csv
import io
import re
from datetime import date
from typing import Any

from pydantic import ValidationError
from sqlmodel import Session

from app.schemas.release_imports import ReleaseImportRunRead
from app.schemas.release_intelligence import (
    ReleaseImportFeedRequest,
    ReleaseImportResult,
    ReleaseIssueImport,
    ReleaseSeriesImport,
    ReleaseVariantImport,
)
from app.services.release_json_import import begin_import_run, record_import_results, validate_json_feed
from app.services.release_import import import_release_feed

REQUIRED_COLUMNS = {"publisher", "series_name", "issue_number"}


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return cleaned or "unknown"


def _parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    return date.fromisoformat(text)


def _parse_float(value: str | None) -> float:
    if value is None:
        return 0.0
    text = value.strip()
    if not text:
        return 0.0
    return float(text)


def _parse_ratio(value: str | None) -> int | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    return int(float(text))


def validate_csv_feed(text: str) -> tuple[ReleaseImportFeedRequest | None, list[tuple[str, str, str]], int]:
    errors: list[tuple[str, str, str]] = []
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return None, [("", "INVALID_CSV", "Missing CSV header row")], 0
    headers = {header.strip().lower() for header in reader.fieldnames if header}
    missing = REQUIRED_COLUMNS - headers
    if missing:
        return None, [("", "MISSING_COLUMNS", f"Missing columns: {', '.join(sorted(missing))}")], 0

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    row_index = 1
    for row in reader:
        row_index += 1
        publisher = (row.get("publisher") or "").strip()
        series_name = (row.get("series_name") or "").strip()
        issue_number = (row.get("issue_number") or "").strip()
        if not publisher or not series_name or not issue_number:
            errors.append((f"row:{row_index}", "MISSING_REQUIRED", "publisher, series_name, and issue_number are required"))
            continue
        grouped.setdefault((publisher, series_name), []).append({"row_index": row_index, "values": row})

    if errors and not grouped:
        return None, errors, 0

    series_payloads: list[ReleaseSeriesImport] = []
    for (publisher, series_name), rows in grouped.items():
        issues: list[ReleaseIssueImport] = []
        for entry in rows:
            row = entry["values"]
            row_index = entry["row_index"]
            issue_number = (row.get("issue_number") or "").strip()
            title = (row.get("title") or "").strip() or f"{series_name} #{issue_number}"
            release_uuid = f"csv-{_slug(publisher)}-{_slug(series_name)}-{_slug(issue_number)}"
            variants: list[ReleaseVariantImport] = []
            variant_name = (row.get("variant_name") or "").strip()
            ratio = _parse_ratio(row.get("ratio"))
            if variant_name:
                variants.append(
                    ReleaseVariantImport(
                        variant_name=variant_name,
                        ratio_value=ratio,
                        variant_type="INCENTIVE" if ratio else "OPEN_ORDER",
                    )
                )
            try:
                issues.append(
                    ReleaseIssueImport(
                        release_uuid=release_uuid,
                        issue_number=issue_number,
                        title=title,
                        foc_date=_parse_date(row.get("foc_date")),
                        release_date=_parse_date(row.get("release_date")),
                        cover_price=_parse_float(row.get("cover_price")),
                        release_status="SCHEDULED",
                        variants=variants,
                    )
                )
            except (ValueError, ValidationError) as exc:
                errors.append((f"row:{row_index}", "VALIDATION_ERROR", str(exc)))
        if issues:
            series_payloads.append(
                ReleaseSeriesImport(
                    publisher=publisher,
                    series_name=series_name,
                    series_type="ONGOING",
                    status="ACTIVE",
                    issues=issues,
                )
            )

    if not series_payloads:
        return None, errors or [("", "EMPTY_CSV", "No valid rows found")], 0

    feed = ReleaseImportFeedRequest(series=series_payloads)
    _, json_errors = validate_json_feed(feed.model_dump())
    errors.extend(json_errors)
    records_processed = sum(len(series.issues) for series in feed.series)
    if json_errors:
        return None, errors, records_processed
    return feed, errors, records_processed


def import_csv_feed(
    session: Session,
    *,
    owner_user_id: int,
    file_name: str,
    csv_text: str,
) -> tuple[ReleaseImportRunRead, ReleaseImportResult | None]:
    file_size = len(csv_text.encode("utf-8"))
    run, _ = begin_import_run(
        session,
        owner_user_id=owner_user_id,
        import_type="CSV",
        file_name=file_name,
        file_type="CSV",
        file_size=file_size,
    )
    payload, validation_errors, records_processed = validate_csv_feed(csv_text)
    if payload is None:
        run = record_import_results(
            session,
            run=run,
            result=None,
            records_processed=records_processed,
            records_failed=max(len(validation_errors), 1),
            errors=validation_errors,
        )
        return ReleaseImportRunRead.model_validate(run), None

    try:
        result = import_release_feed(session, owner_user_id=owner_user_id, payload=payload)
    except Exception as exc:  # noqa: BLE001
        run = record_import_results(
            session,
            run=run,
            result=None,
            records_processed=records_processed,
            records_failed=len(validation_errors) + 1,
            errors=validation_errors + [("feed", "IMPORT_ERROR", str(exc))],
        )
        return ReleaseImportRunRead.model_validate(run), None

    run = record_import_results(
        session,
        run=run,
        result=result,
        records_processed=records_processed,
        records_failed=len(validation_errors),
        errors=validation_errors,
    )
    return ReleaseImportRunRead.model_validate(run), result
