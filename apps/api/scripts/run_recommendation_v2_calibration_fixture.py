"""Run deterministic V2 calibration fixture and print component diagnostics."""

from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sqlmodel import Session, select  # noqa: E402

from app.db.session import get_engine  # noqa: E402
from app.models import User  # noqa: E402
from app.services.recommendation_v2_calibration_fixture import (  # noqa: E402
    assert_fixture_ranking_passes,
    dominant_ranking_driver,
    score_calibration_fixture,
    seed_calibration_fixture,
    weighted_component_contributions,
)


def _resolve_owner_id(session: Session, owner_user_id: int | None, email: str | None) -> int:
    if owner_user_id is not None:
        return owner_user_id
    if email:
        row = session.exec(select(User).where(User.email == email)).first()
        if row is None:
            raise SystemExit(f"User not found for email={email}")
        return int(row.id or 0)
    raise SystemExit("Provide --owner-user-id or --owner-email")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner-user-id", type=int, default=None)
    parser.add_argument("--owner-email", type=str, default=None)
    parser.add_argument("--assert-pass", action="store_true")
    args = parser.parse_args()

    with Session(get_engine()) as session:
        owner_id = _resolve_owner_id(session, args.owner_user_id, args.owner_email)
        refs = seed_calibration_fixture(session, owner_user_id=owner_id)
        rows = score_calibration_fixture(session, owner_user_id=owner_id, refs=refs)

    print("\n=== V2 Calibration Fixture Rankings ===")
    driver_counts: dict[str, int] = {}
    for row in rows:
        driver, magnitude, kind = dominant_ranking_driver(row.bundle)
        driver_counts[driver] = driver_counts.get(driver, 0) + 1
        print(
            f"#{row.rank:02d} {row.bundle.total_score:5.1f} {row.bundle.recommendation_tier:12} "
            f"{row.bundle.recommendation_type:24} [{row.case_id}] {row.label}"
        )
        print(f"     dominant_driver={driver} ({kind}, magnitude={magnitude:.3f})")
        contribs = weighted_component_contributions(row.bundle)
        top5 = sorted(contribs.items(), key=lambda i: i[1], reverse=True)[:5]
        print("     weighted_top5:", ", ".join(f"{k}={v:.3f}" for k, v in top5))
        if row.bundle.score_trace:
            trace = " -> ".join(f"{label}:{score:.1f}" for label, score in row.bundle.score_trace)
            print(f"     score_trace: {trace}")
        for comp in sorted(row.bundle.components, key=lambda c: -c.component_score)[:8]:
            print(f"       {comp.component_name:28} raw={comp.component_score:6.2f} w={comp.component_weight:.2f}")

    print("\n=== Dominant Driver Summary (fixture) ===")
    for name, count in sorted(driver_counts.items(), key=lambda i: -i[1]):
        print(f"  {name}: {count}/10")

    if args.assert_pass:
        assert_fixture_ranking_passes(rows)
        print("\nFIXTURE_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
