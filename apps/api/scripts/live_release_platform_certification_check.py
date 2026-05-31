"""Live release platform certification smoke check (read-only)."""

from __future__ import annotations

import os
import sys

from fastapi.testclient import TestClient
from sqlmodel import Session, select

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.db.session import get_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.lunar_feed import LunarFeedRun  # noqa: E402
from app.services.release_platform_certification import get_release_platform_certification  # noqa: E402
from app.services.release_platform_summary import get_release_platform_summary  # noqa: E402
from app.services.release_platform_validation import validate_release_platform  # noqa: E402


def _pick_owner_id(session: Session) -> int | None:
    row = session.exec(select(LunarFeedRun).order_by(LunarFeedRun.id.desc())).first()
    if row:
        return int(row.owner_user_id)
    return None


def main() -> int:
    owner_id = int(os.environ.get("RELEASE_PLATFORM_OWNER_ID", "0") or "0")
    with Session(get_engine()) as session:
        if owner_id <= 0:
            resolved = _pick_owner_id(session)
            if resolved is None:
                print("No lunar feed runs found; set RELEASE_PLATFORM_OWNER_ID.")
                return 1
            owner_id = resolved

        validation = validate_release_platform(session, owner_user_id=owner_id)
        summary = get_release_platform_summary(session, owner_user_id=owner_id)
        certification = get_release_platform_certification(session, owner_user_id=owner_id)

    print(f"owner_user_id={owner_id}")
    print(f"validation={validation.overall_status}")
    print(f"health={certification.health_status}")
    print(f"readiness_score={summary.platform_readiness_score}")
    print(f"releases={summary.total_releases} variants={summary.total_variants}")
    print(f"scheduler_enabled={summary.scheduler.scheduler_enabled}")
    print(f"go_live={certification.go_live_recommendation}")
    print(f"platform_certified={certification.platform_certified}")

    client = TestClient(app)
    # Routes require auth; service-level check above uses DB directly.
    return 0 if certification.platform_certified or validation.overall_status != "FAIL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
