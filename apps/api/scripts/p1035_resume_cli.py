"""P103.5 --resume-job CLI helpers (shared by write/dry-run scripts)."""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlmodel import Session

    from app.services.p1035_gcd_identity_backfill_service import resolve_p1035_resume_skip_issue_ids


RESUME_JOB_HELP = (
    "Skip catalog issues already written in a prior run. Pass a CatalogImportJob id "
    "(integer) or the JSON file from a previous write (--output). "
    "Examples: --resume-job 42  |  --resume-job data/p1035/gcd_identity_backfill_write.json"
)


def add_p1035_resume_job_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--resume-job", default=None, metavar="ID_OR_JSON", help=RESUME_JOB_HELP)


def resolve_p1035_resume_skip_ids(session: Session, resume_job: str | None) -> set[int]:
    from app.services.p1035_gcd_identity_backfill_service import resolve_p1035_resume_skip_issue_ids

    if resume_job is None:
        return set()
    try:
        return resolve_p1035_resume_skip_issue_ids(session, resume_job)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
