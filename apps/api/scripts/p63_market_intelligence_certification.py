"""P63 Market Intelligence certification runner."""

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
from app.models.asset_ledger import InventoryCopy  # noqa: E402
from app.services.market_intelligence_automation import run_market_intelligence_platform_build  # noqa: E402


def _pick_owner_id(session: Session, email: str | None) -> int:
    if email:
        user = session.exec(select(User).where(User.email == email)).first()
        if user and user.id is not None:
            return int(user.id)
        raise SystemExit(f"Owner not found: {email}")
    row = session.exec(
        select(InventoryCopy.user_id, func.count())
        .where(InventoryCopy.user_id.isnot(None))
        .group_by(InventoryCopy.user_id)
        .order_by(func.count().desc())
    ).first()
    if row and row[0] is not None:
        return int(row[0])
    user = session.exec(select(User).order_by(User.id.asc())).first()
    if user and user.id is not None:
        return int(user.id)
    raise SystemExit("No users in database")


def main() -> None:
    parser = argparse.ArgumentParser(description="P63 market intelligence certification")
    parser.add_argument("--owner-email", default=None)
    parser.add_argument("--skip-pytest", action="store_true")
    args = parser.parse_args()

    if not args.skip_pytest:
        tests = [
            "tests/test_p63_portfolio_performance.py",
            "tests/test_p63_sell_signals.py",
            "tests/test_p63_acquisition_opportunities.py",
            "tests/test_p63_market_signals.py",
            "tests/test_p63_market_intelligence_platform.py",
        ]
        subprocess.run([sys.executable, "-m", "pytest", *tests, "-q"], cwd=API_ROOT, check=True)

    engine = get_engine()
    with Session(engine) as session:
        owner_id = _pick_owner_id(session, args.owner_email)
        result = run_market_intelligence_platform_build(session, owner_user_id=owner_id)
        cert = result["certification"]
        print(json.dumps({"owner_user_id": owner_id, "steps": result["steps"], "certification": cert}, indent=2))
        if not cert.get("platform_ready"):
            raise SystemExit("P63 platform not ready")
        print("P63 market intelligence CERTIFIED for owner", owner_id)


if __name__ == "__main__":
    main()
