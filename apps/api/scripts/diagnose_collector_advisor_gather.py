"""Diagnose Collector Advisor proposal gather for a single owner (ops/local)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from sqlmodel import Session

from app.db.session import get_engine
from app.services.advisor_proposal_gather import ADVISOR_GATHER_SUBSYSTEMS, gather_advisor_proposals_with_result
from app.services.advisor_signal_diagnostics import build_advisor_signal_diagnostics
from app.services.collector_advisor_service import generate_collector_advisor_snapshot, latest_advisor_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose Collector Advisor gather")
    parser.add_argument("--owner-user-id", type=int, required=True)
    parser.add_argument("--dry-run", action="store_true", help="Generate snapshot without commit")
    args = parser.parse_args()
    owner_user_id = int(args.owner_user_id)

    with Session(get_engine()) as session:
        diagnostics = build_advisor_signal_diagnostics(session, owner_user_id=owner_user_id)
        report: dict = {"owner_user_id": owner_user_id, "signal_diagnostics": diagnostics.model_dump(), "subsystems": []}

        for subsystem, gather in ADVISOR_GATHER_SUBSYSTEMS:
            entry = {"subsystem": subsystem, "ok": True, "proposal_count": 0}
            try:
                entry["proposal_count"] = len(gather(session, owner_user_id=owner_user_id))
            except Exception as exc:  # noqa: BLE001
                entry["ok"] = False
                entry["exception_type"] = type(exc).__name__
                entry["message"] = str(exc)
            report["subsystems"].append(entry)

        gather_result = gather_advisor_proposals_with_result(session, owner_user_id=owner_user_id)
        report["gather"] = {
            "total_proposals": len(gather_result.proposals),
            "succeeded_subsystems": gather_result.succeeded_subsystems,
            "failed_subsystems": gather_result.failed_subsystems,
            "errors": gather_result.errors,
            "all_subsystems_failed": gather_result.all_subsystems_failed,
        }

        summary = generate_collector_advisor_snapshot(
            session,
            owner_user_id=owner_user_id,
            dry_run=bool(args.dry_run),
        )
        report["generate_dry_run"] = summary
        if not args.dry_run:
            session.commit()
            snap = latest_advisor_snapshot(session, owner_user_id=owner_user_id)
            report["latest_generation_status"] = str(snap.generation_status if snap else "")

        print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
