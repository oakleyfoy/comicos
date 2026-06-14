from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlalchemy import func  # noqa: E402
from sqlmodel import Session, select  # noqa: E402

from app.models.catalog_master import (  # noqa: E402
    CatalogImage,
    CatalogImageFingerprint,
    CatalogIssue,
    CatalogOcrMetadata,
)
from p97_db import get_p97_engine, resolve_p97_database_url  # noqa: E402

DEFAULT_DATABASE_URL = "postgresql+pg8000://postgres:postgres@localhost:5433/comic_os"


def pct_of(numerator: int, denominator: int, *, digits: int = 1) -> float:
    if denominator <= 0:
        return 0.0
    return round(100.0 * numerator / denominator, digits)


def compute_bottleneck(
    *,
    pending_covers: int,
    ready_covers: int,
    fingerprints: int,
    ocr_rows: int,
) -> str:
    if pending_covers > 0:
        return "COVER_DOWNLOAD"
    if ready_covers > 0 and fingerprints < ready_covers:
        return "FINGERPRINT_GENERATION"
    if ready_covers > 0 and ocr_rows < ready_covers * 0.90:
        return "OCR_GENERATION"
    return "NONE"


def compute_status(*, visual_match_ready_pct: float) -> str:
    if visual_match_ready_pct < 50.0:
        return "ENRICHMENT_BACKLOG"
    if visual_match_ready_pct < 90.0:
        return "PARTIAL_SCAN_READY"
    return "SCANNER_READY_FOR_VALIDATION"


def derive_progress(
    *,
    total_issues: int,
    total_images: int,
    ready_covers: int,
    pending_covers: int,
    failed_covers: int,
    fingerprints: int,
    ocr_rows: int,
) -> dict:
    cover_ready_pct = pct_of(ready_covers, total_issues)
    pending_cover_pct = pct_of(pending_covers, total_issues)
    failed_cover_pct = pct_of(failed_covers, total_issues)
    fingerprint_ready_pct = pct_of(fingerprints, ready_covers)
    ocr_ready_pct = pct_of(ocr_rows, ready_covers)
    visual_match_ready_pct = pct_of(fingerprints, total_issues)
    ocr_catalog_pct = pct_of(ocr_rows, total_issues)
    bottleneck = compute_bottleneck(
        pending_covers=pending_covers,
        ready_covers=ready_covers,
        fingerprints=fingerprints,
        ocr_rows=ocr_rows,
    )
    status = compute_status(visual_match_ready_pct=visual_match_ready_pct)
    return {
        "total_issues": total_issues,
        "total_images": total_images,
        "ready_covers": ready_covers,
        "pending_covers": pending_covers,
        "failed_covers": failed_covers,
        "fingerprints": fingerprints,
        "ocr_rows": ocr_rows,
        "cover_ready_pct": cover_ready_pct,
        "pending_cover_pct": pending_cover_pct,
        "failed_cover_pct": failed_cover_pct,
        "fingerprint_ready_pct": fingerprint_ready_pct,
        "ocr_ready_pct": ocr_ready_pct,
        "visual_match_ready_pct": visual_match_ready_pct,
        "ocr_catalog_pct": ocr_catalog_pct,
        "bottleneck": bottleneck,
        "status": status,
    }


def _cover_status_count(session: Session, status: str) -> int:
    statement = (
        select(func.count())
        .select_from(CatalogImage)
        .where(CatalogImage.image_type == "cover")
        .where(CatalogImage.download_status == status)
    )
    return int(session.exec(statement).one())


def collect_progress(session: Session) -> dict:
    total_issues = int(session.exec(select(func.count()).select_from(CatalogIssue)).one())
    total_images = int(session.exec(select(func.count()).select_from(CatalogImage)).one())
    ready_covers = _cover_status_count(session, "ready")
    pending_covers = _cover_status_count(session, "pending")
    failed_covers = _cover_status_count(session, "failed")
    fingerprints = int(session.exec(select(func.count()).select_from(CatalogImageFingerprint)).one())
    ocr_rows = int(session.exec(select(func.count()).select_from(CatalogOcrMetadata)).one())
    report = derive_progress(
        total_issues=total_issues,
        total_images=total_images,
        ready_covers=ready_covers,
        pending_covers=pending_covers,
        failed_covers=failed_covers,
        fingerprints=fingerprints,
        ocr_rows=ocr_rows,
    )
    report["report_at"] = datetime.now(timezone.utc).isoformat()
    return report


def json_export(report: dict) -> dict:
    return {
        "total_issues": report["total_issues"],
        "total_images": report["total_images"],
        "ready_covers": report["ready_covers"],
        "pending_covers": report["pending_covers"],
        "failed_covers": report["failed_covers"],
        "fingerprints": report["fingerprints"],
        "ocr_rows": report["ocr_rows"],
        "cover_ready_pct": report["cover_ready_pct"],
        "visual_match_ready_pct": report["visual_match_ready_pct"],
        "ocr_catalog_pct": report["ocr_catalog_pct"],
        "bottleneck": report["bottleneck"],
        "status": report["status"],
    }


def _fmt_count(value: int) -> str:
    return f"{value:,}"


def _fmt_pct(value: float) -> str:
    return f"{value:.1f}%"


def format_table(report: dict) -> str:
    lines = [
        "P97 Historical Catalog Progress",
        "=" * 52,
        "",
        f"{'Metric':<28}{'Count':>12}  {'Coverage':>10}",
        "-" * 52,
        f"{'Total Issues':<28}{_fmt_count(report['total_issues']):>12}  {_fmt_pct(100.0 if report['total_issues'] else 0.0):>10}",
        f"{'Total Images':<28}{_fmt_count(report['total_images']):>12}  {_fmt_pct(100.0 if report['total_images'] else 0.0):>10}",
        f"{'Ready Covers':<28}{_fmt_count(report['ready_covers']):>12}  {_fmt_pct(report['cover_ready_pct']):>10}",
        f"{'Pending Covers':<28}{_fmt_count(report['pending_covers']):>12}  {_fmt_pct(report['pending_cover_pct']):>10}",
        f"{'Failed Covers':<28}{_fmt_count(report['failed_covers']):>12}  {_fmt_pct(report['failed_cover_pct']):>10}",
        (
            f"{'Fingerprints':<28}{_fmt_count(report['fingerprints']):>12}  "
            f"{_fmt_pct(report['fingerprint_ready_pct']):>10} of ready covers"
        ),
        (
            f"{'OCR Rows':<28}{_fmt_count(report['ocr_rows']):>12}  "
            f"{_fmt_pct(report['ocr_ready_pct']):>10} of ready covers"
        ),
        "",
        "Scanner Readiness",
        "-" * 52,
        (
            f"{'Visual Match Ready':<28}{_fmt_count(report['fingerprints']):>12}  "
            f"{_fmt_pct(report['visual_match_ready_pct']):>10} of catalog"
        ),
        (
            f"{'OCR Search Ready':<28}{_fmt_count(report['ocr_rows']):>12}  "
            f"{_fmt_pct(report['ocr_catalog_pct']):>10} of catalog"
        ),
        f"{'Current Bottleneck':<28}{report['bottleneck']:>12}",
        f"{'Status':<28}{report['status']:>12}",
        "",
    ]
    return "\n".join(lines)


def fetch_progress(database_url: str) -> dict:
    engine = get_p97_engine(database_url)
    with Session(engine) as session:
        return collect_progress(session)


def main() -> int:
    parser = argparse.ArgumentParser(description="P97 catalog progress watch (read-only)")
    parser.add_argument(
        "--database-url",
        default=None,
        help="SQLAlchemy database URL (default: apps/api/.env DATABASE_URL or comic_os on localhost:5433)",
    )
    parser.add_argument("--json", action="store_true", help="Print progress snapshot as JSON")
    parser.add_argument(
        "--watch",
        type=int,
        metavar="SECONDS",
        help="Reprint progress every N seconds until Ctrl+C",
    )
    args = parser.parse_args()
    database_url = resolve_p97_database_url(args.database_url)

    def run_once() -> dict:
        try:
            return fetch_progress(database_url)
        except Exception as exc:
            print(f"ERROR: database connection failed: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc

    if args.watch is not None:
        if args.watch <= 0:
            print("ERROR: --watch interval must be a positive integer (seconds).", file=sys.stderr)
            return 1
        try:
            while True:
                report = run_once()
                if args.json:
                    print(json.dumps(json_export(report), indent=2))
                else:
                    print(format_table(report))
                    print(f"Updated: {report['report_at']}  (watch every {args.watch}s, Ctrl+C to stop)")
                time.sleep(args.watch)
        except KeyboardInterrupt:
            print("\nStopped.")
            return 0

    report = run_once()
    if args.json:
        print(json.dumps(json_export(report), indent=2))
    else:
        print(format_table(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
