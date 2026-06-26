"""Helpers for P103 write-batch audit (existence checks and assertion reporting)."""

from __future__ import annotations

from collections.abc import Iterator, Sequence

from sqlmodel import Session, select

from app.models.catalog_master import CatalogIssue

ISSUE_ID_BATCH_SIZE = 500
DB_ISSUE_EXISTENCE_TARGET_SECONDS = 2.0


def chunk_ids(issue_ids: Sequence[int], batch_size: int = ISSUE_ID_BATCH_SIZE) -> Iterator[list[int]]:
    if batch_size < 1:
        raise ValueError("batch_size must be >= 1")
    ids = list(issue_ids)
    for start in range(0, len(ids), batch_size):
        yield ids[start : start + batch_size]


def fetch_existing_catalog_issue_ids(
    session: Session,
    issue_ids: Sequence[int],
    *,
    batch_size: int = ISSUE_ID_BATCH_SIZE,
) -> set[int]:
    """Return catalog_issue.id values that exist, using batched IN queries."""
    if not issue_ids:
        return set()
    unique = sorted({int(i) for i in issue_ids})
    found: set[int] = set()
    for batch in chunk_ids(unique, batch_size):
        rows = session.exec(select(CatalogIssue.id).where(CatalogIssue.id.in_(batch))).all()
        for row in rows:
            if isinstance(row, int):
                found.add(row)
            elif isinstance(row, tuple):
                found.add(int(row[0]))
            else:
                found.add(int(row))
    return found


def resolve_job_upc_audit_fields(
    report: dict,
    rollback: dict,
) -> dict[str, int | bool | list[int] | None]:
    """P103: distinguish UPCs inserted by this job vs GCD UPCs already on updated issues."""
    expected_inserted_upcs = int(report.get("inserted_upcs", 0))
    written = report.get("written_rows") or []

    job_ids_raw = report.get("job_inserted_upc_ids")
    if job_ids_raw is not None:
        job_inserted_upc_ids = [int(x) for x in job_ids_raw]
        tracks_job_upc_inserts = True
    elif "upc_ids" in rollback:
        job_inserted_upc_ids = [int(x) for x in (rollback.get("upc_ids") or [])]
        tracks_job_upc_inserts = True
    else:
        job_inserted_upc_ids = None
        tracks_job_upc_inserts = False

    if job_inserted_upc_ids is not None:
        job_inserted_upc_count = len(job_inserted_upc_ids)
    else:
        job_inserted_upc_count = sum(1 for row in written if row.get("inserted_upc")) if written else None

    return {
        "expected_inserted_upcs": expected_inserted_upcs,
        "job_inserted_upc_ids": job_inserted_upc_ids,
        "job_inserted_upc_count": job_inserted_upc_count,
        "tracks_job_upc_inserts": tracks_job_upc_inserts,
    }


def duplicate_barcodes_in_job_inserts(written: list[dict]) -> list[str]:
    """Duplicate normalized barcodes among rows this job marked as inserted_upc."""
    from app.services.catalog_ingestion_service import normalize_upc

    seen: dict[str, int] = {}
    duplicates: list[str] = []
    for row in written:
        if not row.get("inserted_upc") or not row.get("barcode"):
            continue
        norm = normalize_upc(str(row["barcode"]))
        if not norm:
            continue
        if norm in seen:
            duplicates.append(norm)
        else:
            seen[norm] = 1
    return duplicates


def build_overall_assertion_failures(
    *,
    report_counts_ok: bool,
    report_failures: list[str],
    issues_found_in_db: int | None,
    expected_updated: int,
    expected_inserted_upcs: int,
    job_inserted_upc_count: int | None,
    tracks_job_upc_inserts: bool,
    barcode_pass: bool,
    barcode_tests: list[dict],
    error_count: int,
    error_limit: int = 25,
    db_issue_existence_seconds: float | None = None,
    missing_catalog_issue_count: int = 0,
    upc_mismatch_count: int = 0,
    duplicate_job_upc_barcodes: list[str] | None = None,
) -> list[str]:
    """Human-readable FAIL lines for every failed overall check."""
    fails: list[str] = []
    if not report_counts_ok:
        fails.append("FAIL: report_counts_ok false")
        for detail in report_failures:
            fails.append(f"  -> {detail}")
    if issues_found_in_db is not None and issues_found_in_db != expected_updated:
        fails.append(
            f"FAIL: issues_found_in_db mismatch ({issues_found_in_db} != updated_issues {expected_updated})"
        )
    if tracks_job_upc_inserts and job_inserted_upc_count is not None:
        if job_inserted_upc_count != expected_inserted_upcs:
            fails.append(
                "FAIL: job_inserted_upc_count mismatch "
                f"({job_inserted_upc_count} != expected_inserted_upcs {expected_inserted_upcs})"
            )
    if duplicate_job_upc_barcodes:
        fails.append(
            f"FAIL: duplicate UPC barcodes in job inserts ({len(duplicate_job_upc_barcodes)} duplicates)"
        )
        for bc in duplicate_job_upc_barcodes[:5]:
            fails.append(f"  -> duplicate barcode {bc!r}")
    if barcode_tests and not barcode_pass:
        passed = sum(1 for t in barcode_tests if t.get("pass"))
        fails.append(f"FAIL: barcode_lookup_pass false ({passed}/{len(barcode_tests)} passed)")
        for test in barcode_tests:
            if test.get("pass"):
                continue
            fails.append(
                "  -> barcode "
                f"{test.get('barcode')!r} expected issue_id={test.get('expected_catalog_issue_id')} "
                f"lookup issue_id={test.get('lookup_issue_id')} method={test.get('lookup_method')!r}"
            )
    if error_count > error_limit:
        fails.append(f"FAIL: error_count {error_count} exceeds limit {error_limit}")
    if missing_catalog_issue_count:
        fails.append(f"FAIL: missing catalog_issue rows ({missing_catalog_issue_count} ids)")
    if upc_mismatch_count:
        fails.append(f"FAIL: catalog_upc mismatch ({upc_mismatch_count} issue ids)")
    if db_issue_existence_seconds is not None and db_issue_existence_seconds > DB_ISSUE_EXISTENCE_TARGET_SECONDS:
        fails.append(
            f"FAIL: db_issue_existence slow ({db_issue_existence_seconds:.3f}s > "
            f"{DB_ISSUE_EXISTENCE_TARGET_SECONDS}s target for batched PK lookup)"
        )
    return fails
