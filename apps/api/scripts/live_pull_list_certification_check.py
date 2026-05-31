#!/usr/bin/env python3
"""Live Pull List Intelligence certification check (P52-05)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from sqlmodel import Session, select  # noqa: E402

from app.db.session import get_engine  # noqa: E402
from app.models import User  # noqa: E402
from app.services.pull_list_certification import run_pull_list_certification  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run pull list certification for an owner.")
    parser.add_argument("--owner-id", type=int, default=40)
    parser.add_argument("--email", type=str, default="")
    args = parser.parse_args()

    with Session(get_engine()) as session:
        owner_user_id = args.owner_id
        if args.email:
            user = session.exec(select(User).where(User.email == args.email)).first()
            if user is None or user.id is None:
                print(json.dumps({"error": f"User not found: {args.email}"}, indent=2))
                return 1
            owner_user_id = int(user.id)
        report = run_pull_list_certification(session, owner_user_id=owner_user_id)

    payload = {
        "owner_id": owner_user_id,
        "readiness_score": report.readiness_score,
        "certification_result": report.certification_result,
        "certification_recommendation": report.certification_recommendation,
        "validation_status": report.validation_status,
        "domain_scores": {
            "foundation": report.foundation_score,
            "decision_engine": report.decision_engine_score,
            "dashboard": report.dashboard_score,
            "automation": report.automation_score,
            "determinism": report.determinism_score,
            "operations": report.operations_score,
        },
        "checks": [c.model_dump() for c in report.checks],
    }
    print(json.dumps(payload, indent=2, default=str))
    return 0 if report.certification_result == "APPROVED_FOR_PRODUCTION" else 1


if __name__ == "__main__":
    raise SystemExit(main())
