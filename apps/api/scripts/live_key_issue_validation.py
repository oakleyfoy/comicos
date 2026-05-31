"""Live key issue detection smoke check against owner Lunar catalog."""

from __future__ import annotations

import os
import sys

from sqlmodel import Session, select

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.db.session import get_engine  # noqa: E402
from app.models.key_issue_intelligence import KeyIssueProfile  # noqa: E402
from app.models.lunar_feed import LunarFeedRun  # noqa: E402
from app.models.release_intelligence import ReleaseIssue  # noqa: E402
from app.services.key_issue_refresh import refresh_owner_key_issues  # noqa: E402


def main() -> int:
    owner_id = int(os.environ.get("KEY_ISSUE_OWNER_ID", "0") or "0")
    with Session(get_engine()) as session:
        if owner_id <= 0:
            run = session.exec(select(LunarFeedRun).order_by(LunarFeedRun.id.desc())).first()
            if run is None:
                print("No lunar runs found; set KEY_ISSUE_OWNER_ID.")
                return 1
            owner_id = int(run.owner_user_id)

        refresh_owner_key_issues(session, owner_user_id=owner_id)
        profiles = session.exec(
            select(KeyIssueProfile, ReleaseIssue)
            .join(ReleaseIssue, KeyIssueProfile.release_issue_id == ReleaseIssue.id)
            .where(ReleaseIssue.owner_user_id == owner_id)
        ).all()
        print(f"owner_user_id={owner_id} profiles={len(profiles)}")
        for profile, issue in profiles[:25]:
            if profile.key_issue_type in {"MILESTONE_NUMBERING", "ANNIVERSARY", "UNIVERSE_LAUNCH", "RELAUNCH"}:
                print(f"  {issue.title} -> {profile.key_issue_type} score={profile.importance_score}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
