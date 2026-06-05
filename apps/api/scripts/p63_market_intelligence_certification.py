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
from app.models.want_list import WantListItem  # noqa: E402
from app.services.market_intelligence_automation import run_market_intelligence_platform_build  # noqa: E402
from app.services.p63_acquisition_opportunity_service import get_latest_acquisition_snapshot  # noqa: E402
from app.services.market_signal_service import get_latest_market_signal_snapshot  # noqa: E402
from app.services.portfolio_performance_service import get_latest_portfolio_snapshot  # noqa: E402
from app.services.sell_signal_service import get_latest_sell_signal_snapshot  # noqa: E402


def _inventory_count(session: Session, *, owner_user_id: int) -> int:
    return int(
        session.exec(
            select(func.count())
            .select_from(InventoryCopy)
            .where(InventoryCopy.user_id == owner_user_id)
        ).one()
    )


def _want_list_count(session: Session, *, owner_user_id: int) -> int:
    return int(
        session.exec(
            select(func.count())
            .select_from(WantListItem)
            .where(WantListItem.owner_user_id == owner_user_id)
        ).one()
    )


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def _p63_readiness_summary(session: Session, *, owner_user_id: int, inventory_count: int) -> dict:
    port = get_latest_portfolio_snapshot(session, owner_user_id=owner_user_id)
    sell = get_latest_sell_signal_snapshot(session, owner_user_id=owner_user_id)
    acq = get_latest_acquisition_snapshot(session, owner_user_id=owner_user_id)
    sig = get_latest_market_signal_snapshot(session, owner_user_id=owner_user_id)
    notes: list[str] = []
    if inventory_count > 0 and port is None:
        notes.append("missing_portfolio_snapshot")
    if inventory_count > 0 and sell is None:
        notes.append("missing_sell_snapshot")
    likely_ready_after_build = inventory_count > 0
    return {
        "inventory_count": inventory_count,
        "portfolio_snapshot": _iso(port.generated_at) if port else None,
        "sell_snapshot": _iso(sell.generated_at) if sell else None,
        "acquisition_snapshot": _iso(acq.generated_at) if acq else None,
        "market_signals_snapshot": _iso(sig.generated_at) if sig else None,
        "pre_build_gaps": notes,
        "cert_expected_after_platform_build": likely_ready_after_build,
    }


def list_eligible_owners(session: Session) -> list[dict]:
    rows = session.exec(
        select(InventoryCopy.user_id, func.count())
        .where(InventoryCopy.user_id.isnot(None))
        .group_by(InventoryCopy.user_id)
        .having(func.count() > 0)
        .order_by(func.count().desc())
    ).all()
    eligible: list[dict] = []
    for user_id, inv_count in rows:
        if user_id is None:
            continue
        oid = int(user_id)
        user = session.get(User, oid)
        email = user.email if user else None
        eligible.append(
            {
                "owner_user_id": oid,
                "email": email,
                "inventory_count": int(inv_count),
                "want_list_count": _want_list_count(session, owner_user_id=oid),
            }
        )
    return eligible


def print_eligible_owners(session: Session) -> list[dict]:
    eligible = list_eligible_owners(session)
    print("Eligible owners (inventory_copy count > 0):")
    if not eligible:
        print("  (none)")
        return eligible
    for row in eligible:
        readiness = _p63_readiness_summary(
            session,
            owner_user_id=row["owner_user_id"],
            inventory_count=row["inventory_count"],
        )
        print(
            f"  owner_id={row['owner_user_id']} email={row['email']!r} "
            f"inventory={row['inventory_count']} want_list={row['want_list_count']} "
            f"p63_pre_build={json.dumps(readiness, sort_keys=True)}"
        )
    return eligible


def resolve_owner_id(session: Session, *, email: str | None) -> tuple[int, dict]:
    eligible = print_eligible_owners(session)

    if email:
        user = session.exec(select(User).where(User.email == email)).first()
        if user is None or user.id is None:
            raise SystemExit(f"Owner not found: {email}")
        oid = int(user.id)
        inv = _inventory_count(session, owner_user_id=oid)
        if inv <= 0:
            raise SystemExit(
                f"Owner {email!r} (id={oid}) has inventory_count=0; "
                "cannot certify P63 market intelligence. Pick an eligible owner from the list above."
            )
        meta = {
            "owner_user_id": oid,
            "email": user.email,
            "inventory_count": inv,
            "want_list_count": _want_list_count(session, owner_user_id=oid),
        }
        return oid, meta

    if not eligible:
        raise SystemExit(
            "No owners with inventory_copy rows. Seed inventory or pass --owner-email for an owner with copies."
        )

    best = eligible[0]
    meta = {
        "owner_user_id": best["owner_user_id"],
        "email": best["email"],
        "inventory_count": best["inventory_count"],
        "want_list_count": best["want_list_count"],
    }
    print(
        f"Auto-selected owner_id={meta['owner_user_id']} email={meta['email']!r} "
        f"(highest inventory_count={meta['inventory_count']})"
    )
    return int(meta["owner_user_id"]), meta


def main() -> None:
    parser = argparse.ArgumentParser(description="P63 market intelligence certification")
    parser.add_argument("--owner-email", default=None, help="Owner email (must have inventory_copy rows)")
    parser.add_argument("--skip-pytest", action="store_true")
    parser.add_argument("--list-owners-only", action="store_true", help="Print eligible owners and exit")
    args = parser.parse_args()

    if not args.skip_pytest and not args.list_owners_only:
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
        if args.list_owners_only:
            print_eligible_owners(session)
            return

        owner_id, meta = resolve_owner_id(session, email=args.owner_email)
        readiness = _p63_readiness_summary(
            session,
            owner_user_id=owner_id,
            inventory_count=meta["inventory_count"],
        )
        print("Certification target:")
        print(json.dumps({**meta, "p63_readiness_before_build": readiness}, indent=2))

        result = run_market_intelligence_platform_build(session, owner_user_id=owner_id)
        cert = result["certification"]
        print(json.dumps({"owner_user_id": owner_id, "steps": result["steps"], "certification": cert}, indent=2))
        if not cert.get("platform_ready"):
            raise SystemExit("P63 platform not ready")
        print(f"P63 market intelligence CERTIFIED for owner_id={owner_id} email={meta['email']!r}")


if __name__ == "__main__":
    main()
