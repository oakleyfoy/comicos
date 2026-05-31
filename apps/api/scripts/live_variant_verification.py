"""Live Lunar variant repair verification via in-process API (current code). Never prints secrets."""
from __future__ import annotations

import json
import sys
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
from app.services.ops_access import is_ops_admin_user


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _issue_token(session: Session, user: User) -> str:
    assert user.id is not None
    token = create_access_token(subject=str(user.id))
    create_session(
        session,
        user_id=int(user.id),
        raw_token=token,
        expires_at=token_expiration_utc(token),
        device_label=build_device_label("live-variant-verification"),
        device_type=detect_device_type("live-variant-verification"),
        ip_address="127.0.0.1",
        user_agent="live-variant-verification",
    )
    return token


def _resolve_owner(session: Session) -> User:
    run = session.exec(select(LunarFeedRun).order_by(LunarFeedRun.id.desc())).first()
    if run is not None:
        user = session.get(User, run.owner_user_id)
        if user is not None:
            return user
    row = session.exec(
        select(ReleaseIssue.owner_user_id, func.count())
        .group_by(ReleaseIssue.owner_user_id)
        .order_by(func.count().desc())
    ).first()
    if row is None:
        raise SystemExit("No release owner found")
    user = session.get(User, row[0])
    if user is None:
        raise SystemExit("Owner user missing")
    return user


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


def _duplicate_variant_uuids(session: Session, owner_id: int) -> int:
    rows = session.exec(
        select(ReleaseVariant.variant_uuid, func.count())
        .join(ReleaseIssue, ReleaseVariant.issue_id == ReleaseIssue.id)
        .where(ReleaseIssue.owner_user_id == owner_id, ReleaseVariant.variant_uuid != "")
        .group_by(ReleaseVariant.variant_uuid)
        .having(func.count() > 1)
    ).all()
    return len(rows)


def _issue_variant_snapshot(session: Session, *, series_substr: str, issue_number: str) -> dict[str, object]:
    rows = session.exec(
        select(ReleaseSeries, ReleaseIssue)
        .join(ReleaseIssue, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseSeries.series_name.ilike(f"%{series_substr}%"), ReleaseIssue.issue_number == issue_number)
        .order_by(ReleaseIssue.id.asc())
    ).all()
    if not rows:
        return {"issue": None, "variants": [], "issue_row_count": 0}
    series_name = rows[0][0].series_name
    canonical = rows[0][1]
    variants = session.exec(
        select(ReleaseVariant)
        .where(ReleaseVariant.issue_id == canonical.id)
        .order_by(ReleaseVariant.variant_name.asc())
    ).all()
    return {
        "issue": f"{series_name} #{issue_number}",
        "variants": [v.variant_name for v in variants],
        "issue_row_count": len(rows),
    }


def _find_examples(session: Session, owner_id: int) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    z = _issue_variant_snapshot(session, series_substr="ZATANNA", issue_number="5")
    if z["issue"]:
        out.append(z)

    candidates = session.exec(
        select(ReleaseVariant, ReleaseIssue, ReleaseSeries)
        .join(ReleaseIssue, ReleaseVariant.issue_id == ReleaseIssue.id)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseIssue.owner_user_id == owner_id)
        .order_by(ReleaseVariant.id.desc())
        .limit(500)
    ).all()

    want_tags = ["ratio_incentive", "cover_b", "cover_c", "virgin", "ratio"]
    found_tags: set[str] = set()
    seen_issues: set[str] = {str(z.get("issue"))}

    for variant, issue, series in candidates:
        tag = None
        if variant.is_incentive_variant and variant.ratio_value:
            tag = "ratio_incentive"
        elif variant.variant_name.startswith("Cover B"):
            tag = "cover_b"
        elif variant.variant_name.startswith("Cover C"):
            tag = "cover_c"
        elif "Virgin" in variant.variant_name:
            tag = "virgin"
        elif variant.ratio_value:
            tag = "ratio"
        if tag is None or tag in found_tags:
            continue
        snap = _issue_variant_snapshot(session, series_substr=series.series_name.split()[0], issue_number=issue.issue_number)
        key = str(snap.get("issue"))
        if not snap.get("variants") or key in seen_issues:
            continue
        out.append(snap)
        seen_issues.add(key)
        found_tags.add(tag)
        if len(out) >= 6:
            break
    return out


def main() -> None:
    settings = get_settings()
    engine = get_engine()
    client = TestClient(app)

    with Session(engine) as session:
        owner = _resolve_owner(session)
        assert owner.id is not None
        if not is_ops_admin_user(owner, settings):
            raise SystemExit("Catalog owner is not ops admin")
        token = _issue_token(session, owner)
        owner_id = int(owner.id)
        before = _counts(session, owner_id)

    headers = _auth_headers(token)
    repair_resp = client.post("/api/v1/lunar-feed/repair-variants", headers=headers)
    repair_data = repair_resp.json().get("data", repair_resp.json())

    with Session(engine) as session:
        after = _counts(session, owner_id)
        dup_variants_before_reimport = _duplicate_variant_uuids(session, owner_id)
        examples = _find_examples(session, owner_id)

    api_checks = {}
    for label, path in [
        ("release-intelligence/variants", "/api/v1/release-intelligence/variants?limit=5"),
        ("release-intelligence/variants/top", "/api/v1/release-intelligence/variants/top?limit=5"),
        ("release-platform/ratio-variants", "/api/v1/release-platform/ratio-variants?limit=5"),
        ("release-platform/new-variants", "/api/v1/release-platform/new-variants?limit=5"),
    ]:
        resp = client.get(path, headers=headers)
        items = resp.json().get("data", {}).get("items") if resp.status_code == 200 else None
        api_checks[label] = f"HTTP {resp.status_code} items={len(items) if items is not None else 0}"

    dashboards = {}
    for label, path in [
        ("release-intelligence", "/api/v1/release-intelligence/dashboard"),
        ("release-platform", "/api/v1/release-platform/dashboard"),
        ("spec-intelligence", "/api/v1/spec-intelligence/dashboard"),
    ]:
        resp = client.get(path, headers=headers)
        data = resp.json().get("data", {}) if resp.status_code == 200 else {}
        dashboards[label] = {
            "status": resp.status_code,
            "variant_count": data.get("variant_count"),
            "ratio_variant_count": data.get("ratio_variant_count"),
            "cover_variant_count": data.get("cover_variant_count"),
            "top_ratio_variants": len(data.get("top_ratio_variants") or []),
            "top_new_variants": len(data.get("top_new_variants") or data.get("recent_variants") or []),
        }

    reimport_resp = client.post("/api/v1/lunar-feed/import/latest-remote", headers=headers)
    reimport_data = reimport_resp.json().get("data", reimport_resp.json())

    with Session(engine) as session:
        post = _counts(session, owner_id)
        dup_after = _duplicate_variant_uuids(session, owner_id)

    reimport_pass = (
        reimport_resp.status_code in {200, 201}
        and post[2] >= after[2]
        and dup_after == 0
        and post[1] >= after[1] - 50  # legacy duplicate issue rows preserved
    )

    report = {
        "repair_status": repair_resp.status_code,
        "repair_summary": repair_data,
        "issues_processed": repair_data.get("issue_groups_processed"),
        "variants_created": repair_data.get("variants_created"),
        "errors": repair_resp.json().get("errors") if repair_resp.status_code != 201 else [],
        "release_series_count": after[0],
        "release_issue_count": after[1],
        "release_variant_count": after[2],
        "counts_before_repair": {"series": before[0], "issues": before[1], "variants": before[2]},
        "examples": examples,
        "api_checks": api_checks,
        "dashboards": dashboards,
        "reimport_status": reimport_resp.status_code,
        "reimport_summary": {
            "records_processed": reimport_data.get("records_processed"),
            "records_created": reimport_data.get("records_created"),
            "records_updated": reimport_data.get("records_updated"),
            "records_failed": reimport_data.get("records_failed"),
        },
        "counts_after_reimport": {"series": post[0], "issues": post[1], "variants": post[2]},
        "duplicate_variant_uuid_groups_after_reimport": dup_after,
        "reimport_verification": "PASS" if reimport_pass else "FAIL",
    }
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
