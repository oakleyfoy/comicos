from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlalchemy import func  # noqa: E402
from sqlmodel import Session, create_engine, select  # noqa: E402

from app.models.catalog_master import (  # noqa: E402
    CatalogImage,
    CatalogImageFingerprint,
    CatalogIssue,
    CatalogOcrMetadata,
    CatalogPublisher,
)
from app.models.catalog_p97 import CatalogImportJob  # noqa: E402

DEFAULT_DATABASE_URL = "postgresql+pg8000://postgres:postgres@localhost:5433/comic_os"


def _pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(100.0 * numerator / denominator, 2)


def _cover_status_count(session: Session, status: str) -> int:
    statement = (
        select(func.count())
        .select_from(CatalogImage)
        .where(CatalogImage.image_type == "cover")
        .where(CatalogImage.download_status == status)
    )
    return int(session.exec(statement).one())


def _top_publishers(session: Session, *, limit: int = 10) -> list[tuple[str, int]]:
    statement = (
        select(CatalogPublisher.name, func.count(CatalogIssue.id))
        .join(CatalogIssue, CatalogIssue.publisher_id == CatalogPublisher.id)
        .group_by(CatalogPublisher.name)
        .order_by(func.count(CatalogIssue.id).desc())
        .limit(limit)
    )
    return [(name, int(count)) for name, count in session.exec(statement).all()]


def _latest_jobs(session: Session, *, limit: int = 10) -> list[dict]:
    rows = session.exec(select(CatalogImportJob).order_by(CatalogImportJob.id.desc()).limit(limit)).all()
    out: list[dict] = []
    for job in rows:
        out.append(
            {
                "id": job.id,
                "source": job.source,
                "job_type": job.job_type,
                "status": job.status,
                "total_seen": job.total_seen,
                "total_created": job.total_created,
                "total_updated": job.total_updated,
                "total_skipped": job.total_skipped,
                "total_failed": job.total_failed,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "cursor": job.cursor,
            }
        )
    return out


def collect_health(session: Session) -> dict:
    total_issues = int(session.exec(select(func.count()).select_from(CatalogIssue)).one())
    total_images = int(session.exec(select(func.count()).select_from(CatalogImage)).one())
    ready_covers = _cover_status_count(session, "ready")
    pending_covers = _cover_status_count(session, "pending")
    failed_covers = _cover_status_count(session, "failed")
    fingerprints = int(session.exec(select(func.count()).select_from(CatalogImageFingerprint)).one())
    ocr_rows = int(session.exec(select(func.count()).select_from(CatalogOcrMetadata)).one())
    fingerprint_coverage_pct = _pct(fingerprints, ready_covers)
    ocr_coverage_pct = _pct(ocr_rows, ready_covers)
    return {
        "database": "connected",
        "report_at": datetime.now(timezone.utc).isoformat(),
        "total_issues": total_issues,
        "total_images": total_images,
        "ready_covers": ready_covers,
        "pending_covers": pending_covers,
        "failed_covers": failed_covers,
        "fingerprints": fingerprints,
        "fingerprint_coverage_pct": fingerprint_coverage_pct,
        "ocr_rows": ocr_rows,
        "ocr_coverage_pct": ocr_coverage_pct,
        "top_publishers": [{"publisher": name, "issue_count": count} for name, count in _top_publishers(session)],
        "latest_jobs": _latest_jobs(session),
    }


def _print_report(report: dict) -> None:
    print(f"total_issues={report['total_issues']}")
    print(f"total_images={report['total_images']}")
    print(f"ready_covers={report['ready_covers']}")
    print(f"pending_covers={report['pending_covers']}")
    print(f"failed_covers={report['failed_covers']}")
    print(f"fingerprints={report['fingerprints']}")
    print(f"fingerprint_coverage_pct={report['fingerprint_coverage_pct']}")
    print(f"ocr_rows={report['ocr_rows']}")
    print(f"ocr_coverage_pct={report['ocr_coverage_pct']}")
    print("top_publishers:")
    for row in report["top_publishers"]:
        print(f"  {row['publisher']}: {row['issue_count']}")
    print("latest_jobs:")
    print(json.dumps(report["latest_jobs"], indent=2, default=str))


def main() -> int:
    parser = argparse.ArgumentParser(description="P97 catalog health snapshot (read-only)")
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL),
        help="SQLAlchemy database URL (default: comic_os on localhost:5433)",
    )
    parser.add_argument("--json", action="store_true", help="Print full report as JSON only")
    args = parser.parse_args()

    engine = create_engine(args.database_url, pool_pre_ping=True)
    with Session(engine) as session:
        report = collect_health(session)
        report["database_url"] = args.database_url.split("@")[-1] if "@" in args.database_url else args.database_url

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        _print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
