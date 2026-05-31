"""Run final ComicOS v1.0 platform certification for an owner (ops use)."""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sqlmodel import Session  # noqa: E402

from app.db.session import get_engine  # noqa: E402
from app.services.final_platform_certification import run_final_platform_certification  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run P57-05 final platform certification")
    parser.add_argument("--owner-user-id", type=int, required=True)
    args = parser.parse_args()
    with Session(get_engine()) as session:
        report = run_final_platform_certification(session, owner_user_id=args.owner_user_id)
    print(f"readiness_score={report.readiness_score}")
    print(f"certification_result={report.certification_result}")
    print(f"health_status={report.health_status}")
    print(f"production_recommendation={report.report.production_recommendation}")
    return 0 if report.certification_result == "APPROVED_FOR_PRODUCTION" else 1


if __name__ == "__main__":
    sys.exit(main())
