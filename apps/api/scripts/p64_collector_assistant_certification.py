"""P64 Collector Assistant certification runner."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
API_ROOT = os.path.join(REPO_ROOT, "apps", "api")
if API_ROOT not in sys.path:
    sys.path.insert(0, API_ROOT)

from sqlmodel import Session  # noqa: E402

from app.db.session import get_engine  # noqa: E402
from app.services.collector_assistant_certification_service import (  # noqa: E402
    get_collector_assistant_platform_certification,
)
from app.services.collector_intelligence_automation import run_collector_intelligence_pipeline  # noqa: E402
from app.services.market_intelligence_automation import run_market_intelligence_platform_build  # noqa: E402


def _load_p63_owner_helpers():
    path = os.path.join(API_ROOT, "scripts", "p63_market_intelligence_certification.py")
    spec = importlib.util.spec_from_file_location("p63_market_intelligence_certification", path)
    if spec is None or spec.loader is None:
        raise SystemExit("Could not load P63 certification script for owner selection")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> None:
    parser = argparse.ArgumentParser(description="P64 collector assistant certification")
    parser.add_argument("--owner-email", default=None, help="Owner email (must have inventory_copy rows)")
    parser.add_argument("--skip-pytest", action="store_true")
    parser.add_argument("--list-owners-only", action="store_true")
    parser.add_argument("--skip-upstream-build", action="store_true", help="Skip P62/P63 platform rebuild before P64 cert")
    args = parser.parse_args()

    p63 = _load_p63_owner_helpers()

    if not args.skip_pytest and not args.list_owners_only:
        subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_p64_collector_assistant.py", "-q"],
            cwd=API_ROOT,
            check=True,
        )

    engine = get_engine()
    with Session(engine) as session:
        if args.list_owners_only:
            p63.print_eligible_owners(session)
            return

        owner_id, meta = p63.resolve_owner_id(session, email=args.owner_email)
        readiness = p63._p63_readiness_summary(  # noqa: SLF001
            session,
            owner_user_id=owner_id,
            inventory_count=meta["inventory_count"],
        )
        print("Certification target:")
        print(json.dumps({**meta, "p63_readiness_before_build": readiness}, indent=2))

        if not args.skip_upstream_build:
            print("Building P62 collector pipeline...")
            run_collector_intelligence_pipeline(session, owner_user_id=owner_id)
            print("Building P63 market platform...")
            run_market_intelligence_platform_build(session, owner_user_id=owner_id)

        cert = get_collector_assistant_platform_certification(session, owner_user_id=owner_id)
        print(json.dumps({"owner_user_id": owner_id, "certification": cert}, indent=2))
        if not cert.get("platform_ready"):
            raise SystemExit("P64 collector assistant platform not ready")
        print(f"P64 collector assistant CERTIFIED for owner_id={owner_id} email={meta['email']!r}")


if __name__ == "__main__":
    main()
