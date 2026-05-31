"""Verify double remote import does not grow canonical issue rows."""
from __future__ import annotations

import json
import sys
import uuid
from collections import defaultdict
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, select, func

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.core.config import get_settings
from app.core.security import create_access_token, token_expiration_utc
from app.db.session import get_engine
from app.main import app
from app.models import User
from app.models.lunar_feed import LunarFeedRun
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries, ReleaseVariant
from app.security.session_manager import build_device_label, create_session, detect_device_type
from app.services.lunar_issue_identity import is_canonical_lunar_issue_uuid
from app.services.ops_access import is_ops_admin_user


def _token(session: Session, user: User) -> str:
    assert user.id is not None
    token = create_access_token(subject=str(user.id))
    create_session(
        session,
        user_id=int(user.id),
        raw_token=token,
        expires_at=token_expiration_utc(token),
        device_label=build_device_label("reimport-idempotency-check"),
        device_type=detect_device_type("script"),
        ip_address="127.0.0.1",
        user_agent="reimport-idempotency-check",
    )
    return token


def _counts(session: Session, owner_id: int) -> tuple[int, int, int]:
    series = session.scalar(
        select(func.count()).select_from(ReleaseSeries).where(ReleaseSeries.owner_user_id == owner_id)
    ) or 0
    issues = session.scalar(
        select(func.count()).select_from(ReleaseIssue).where(ReleaseIssue.owner_user_id == owner_id)
    ) or 0
    variants = session.scalar(
        select(func.count())
        .select_from(ReleaseVariant)
        .join(ReleaseIssue, ReleaseVariant.issue_id == ReleaseIssue.id)
        .where(ReleaseIssue.owner_user_id == owner_id)
    ) or 0
    return int(series), int(issues), int(variants)


def _duplicate_canonical_groups(session: Session, owner_id: int) -> int:
    rows = session.exec(
        select(ReleaseIssue.series_id, ReleaseIssue.issue_number, ReleaseIssue.release_uuid)
        .where(ReleaseIssue.owner_user_id == owner_id)
        .where(ReleaseIssue.release_uuid.like("lunar-issue-%"))
    ).all()
    groups: dict[tuple[int, str], set[str]] = defaultdict(set)
    for series_id, issue_number, release_uuid in rows:
        groups[(series_id, issue_number)].add(release_uuid)
    return sum(1 for uuids in groups.values() if len(uuids) > 1)


def main() -> None:
    settings = get_settings()
    engine = get_engine()
    client = TestClient(app)
    with Session(engine) as session:
        run = session.exec(select(LunarFeedRun).order_by(LunarFeedRun.id.desc())).first()
        if run is None:
            raise SystemExit("No lunar feed run found")
        user = session.get(User, run.owner_user_id)
        if user is None or not is_ops_admin_user(user, settings):
            raise SystemExit("Owner missing or not ops admin")
        owner_id = int(user.id)
        token = _token(session, user)
        before = _counts(session, owner_id)

    headers = {"Authorization": f"Bearer {token}"}
    first = client.post("/api/v1/lunar-feed/import/latest-remote", headers=headers)
    with Session(engine) as session:
        after_first = _counts(session, owner_id)
        dup_after_first = _duplicate_canonical_groups(session, owner_id)

    second = client.post("/api/v1/lunar-feed/import/latest-remote", headers=headers)
    with Session(engine) as session:
        after_second = _counts(session, owner_id)
        dup_after_second = _duplicate_canonical_groups(session, owner_id)

    print(
        json.dumps(
            {
                "before_first": {"series": before[0], "issues": before[1], "variants": before[2]},
                "after_first_status": first.status_code,
                "after_first": {"series": after_first[0], "issues": after_first[1], "variants": after_first[2]},
                "after_second_status": second.status_code,
                "after_second": {"series": after_second[0], "issues": after_second[1], "variants": after_second[2]},
                "duplicate_canonical_uuid_groups_after_second": dup_after_second,
                "second_import_records_created": second.json().get("data", {}).get("records_created"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
