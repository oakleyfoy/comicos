"""P62 Collector Intelligence Suite certification runner (local/CI)."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
API_ROOT = os.path.join(REPO_ROOT, "apps", "api")
if API_ROOT not in sys.path:
    sys.path.insert(0, API_ROOT)

from sqlmodel import Session, select, func  # noqa: E402

from app.db.session import get_engine  # noqa: E402
from app.models import User  # noqa: E402
from app.models.release_intelligence import ReleaseIssue  # noqa: E402
from app.services.collector_intelligence_automation import run_collector_intelligence_pipeline  # noqa: E402


def _pick_owner_id(session: Session, email: str | None) -> int:
    if email:
        user = session.exec(select(User).where(User.email == email)).first()
        if user and user.id is not None:
            return int(user.id)
        raise SystemExit(f"Owner not found: {email}")
    row = session.exec(
        select(ReleaseIssue.owner_user_id, func.count())
        .where(ReleaseIssue.owner_user_id.isnot(None))
        .group_by(ReleaseIssue.owner_user_id)
        .order_by(func.count().desc())
    ).first()
    if row and row[0] is not None:
        return int(row[0])
    user = session.exec(select(User).order_by(User.id.asc())).first()
    if user and user.id is not None:
        return int(user.id)
    raise SystemExit("No users in database")


def main() -> None:
    parser = argparse.ArgumentParser(description="P62 collector intelligence certification")
    parser.add_argument("--owner-email", default=None, help="Owner email for pipeline cert")
    parser.add_argument("--skip-pytest", action="store_true")
    args = parser.parse_args()

    if not args.skip_pytest:
        tests = [
            "tests/test_foc_intelligence.py",
            "tests/test_future_pull_forecasting.py",
            "tests/test_auto_watchlists.py",
            "tests/test_p62_collector_intelligence_suite.py",
        ]
        cmd = [sys.executable, "-m", "pytest", *tests, "-q"]
        print("Running:", " ".join(cmd))
        subprocess.run(cmd, cwd=API_ROOT, check=True)

    engine = get_engine()
    with Session(engine) as session:
        owner_id = _pick_owner_id(session, args.owner_email)
        result = run_collector_intelligence_pipeline(session, owner_user_id=owner_id)
        cert = result["certification"]
        ready = cert.get("platform_ready", False)
        print(json.dumps({"owner_user_id": owner_id, "steps": result["steps"], "certification": cert}, indent=2))
        if not ready:
            raise SystemExit("P62 collector platform not ready")
        print("P62 collector intelligence CERTIFIED for owner", owner_id)


if __name__ == "__main__":
    main()
