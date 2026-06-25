"""Backfill gcd_large_write_batch_report.json from catalog_import_job (after DetachedInstanceError fix)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session, select  # noqa: E402

from app.db.session import get_engine  # noqa: E402
from app.models.catalog_p97 import CatalogImportJob  # noqa: E402
from app.services.gcd_catalog_import_dashboard_service import (  # noqa: E402
    GCD_JOB_TYPE_LARGE_WRITE,
    load_job_dashboard_dict,
)

OUT = Path("data/p102/gcd_large_write_batch_report.json")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", type=int, default=None)
    parser.add_argument("--output", default=str(OUT))
    args = parser.parse_args()

    with Session(get_engine()) as session:
        if args.job_id is not None:
            job_id = args.job_id
        else:
            row = session.exec(
                select(CatalogImportJob)
                .where(CatalogImportJob.job_type == GCD_JOB_TYPE_LARGE_WRITE)
                .order_by(CatalogImportJob.id.desc())
            ).first()
            if row is None or row.id is None:
                print("No gcd_large_write_batch job found", file=sys.stderr)
                return 2
            job_id = int(row.id)
        payload = load_job_dashboard_dict(session, job_id)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    rb = payload.get("rollback") or {}
    print(f"job_id={payload.get('job_id')} status={payload.get('status')}")
    print(f"issues={payload.get('inserted_issues')} upcs={payload.get('inserted_upcs')}")
    print(f"rollback issue_ids={len(rb.get('issue_ids') or [])} upc_ids={len(rb.get('upc_ids') or [])}")
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
