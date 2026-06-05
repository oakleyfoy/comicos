"""One-off owner inventory for recommendation audit validation (stdout JSON + table)."""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sqlalchemy import func, select
from sqlmodel import Session

from app.db.session import get_engine
from app.models import InventoryCopy, User
from app.models.cross_system_recommendation import CrossSystemRecommendation
from app.models.pull_list import PullList, PullListIssue
from app.models.release_intelligence import ReleaseIssue
from app.models.unified_collector_intelligence import UnifiedCollectorRecommendation
from app.models.want_list import WantListItem
from app.services.cross_system_recommendation import list_latest_cross_system_recommendations
from app.services.unified_collector_intelligence import _latest_recommendation_rows
from scripts.owner_lookup import unwrap_user_row, user_id_from_object

PRODUCTION_OWNER_EMAIL = "ofoy@att.net"
TEST_OWNER_EMAIL = "ofoy@att.net"
REIMPORT_EMAIL_SUBSTR = "lunar-reimport-"


def scalar_int(value: object | None) -> int:
    if value is None:
        return 0
    if hasattr(value, "_mapping"):
        return int(value[0])
    if isinstance(value, tuple):
        return int(value[0])
    return int(value)


def main() -> int:
    out: list[dict] = []
    with Session(get_engine()) as session:
        user_rows = session.exec(select(User).order_by(User.id)).all()
        for row in user_rows:
            user = unwrap_user_row(row)
            uid = int(user_id_from_object(user) or 0)
            email = str(getattr(user, "email", None) or "")
            inventory_count = scalar_int(
                session.exec(
                    select(func.count()).select_from(InventoryCopy).where(InventoryCopy.user_id == uid)
                ).one()
            )
            pull_list_count = scalar_int(
                session.exec(
                    select(func.count()).select_from(PullList).where(PullList.owner_user_id == uid)
                ).one()
            )
            pull_list_issue_count = scalar_int(
                session.exec(
                    select(func.count())
                    .select_from(PullListIssue)
                    .join(PullList, PullListIssue.pull_list_id == PullList.id)
                    .where(PullList.owner_user_id == uid)
                ).one()
            )
            want_list_count = scalar_int(
                session.exec(
                    select(func.count()).select_from(WantListItem).where(WantListItem.owner_user_id == uid)
                ).one()
            )
            release_issue_count = scalar_int(
                session.exec(
                    select(func.count()).select_from(ReleaseIssue).where(ReleaseIssue.owner_user_id == uid)
                ).one()
            )
            recommendation_count_latest = len(_latest_recommendation_rows(session, owner_user_id=uid))
            _, cross_latest = list_latest_cross_system_recommendations(
                session, owner_user_id=uid, limit=500, offset=0
            )
            cross_system_recommendation_count_latest = int(cross_latest)
            recommendation_count_all = scalar_int(
                session.exec(
                    select(func.count())
                    .select_from(UnifiedCollectorRecommendation)
                    .where(UnifiedCollectorRecommendation.owner_user_id == uid)
                ).one()
            )
            cross_system_recommendation_count_all = scalar_int(
                session.exec(
                    select(func.count())
                    .select_from(CrossSystemRecommendation)
                    .where(CrossSystemRecommendation.owner_user_id == uid)
                ).one()
            )
            roles: list[str] = []
            if email.lower() == PRODUCTION_OWNER_EMAIL.lower():
                roles.extend(["production_owner", "test_owner"])
            if REIMPORT_EMAIL_SUBSTR in email.lower():
                roles.append("reimport_owner")
            if release_issue_count > 0 and (
                recommendation_count_latest > 0 or cross_system_recommendation_count_latest > 0
            ):
                roles.append("seeded_owner")
            if email.endswith("@example.com") and "reimport" not in email.lower():
                roles.append("fixture_owner")

            out.append(
                {
                    "owner_id": uid,
                    "email": email,
                    "inventory_count": inventory_count,
                    "pull_list_count": pull_list_count,
                    "pull_list_issue_count": pull_list_issue_count,
                    "want_list_count": want_list_count,
                    "release_issue_count": release_issue_count,
                    "recommendation_count": recommendation_count_latest,
                    "recommendation_count_all_rows": recommendation_count_all,
                    "cross_system_recommendation_count": cross_system_recommendation_count_latest,
                    "cross_system_recommendation_count_all_rows": cross_system_recommendation_count_all,
                    "roles": roles,
                }
            )

    audit_owner = _pick_audit_owner(out)
    report = {
        "database_url_host": _db_host(os.environ.get("DATABASE_URL", "")),
        "owner_count": len(out),
        "owners": out,
        "role_definitions": {
            "production_owner": f"Convention: real account {PRODUCTION_OWNER_EMAIL} (seed script default, LoCG capture).",
            "test_owner": f"P61 audit default: {TEST_OWNER_EMAIL}.",
            "seeded_owner": "Has release catalog and latest unified or cross-system recommendations.",
            "reimport_owner": f"Email contains {REIMPORT_EMAIL_SUBSTR!r} (Lunar reimport test fixture).",
        },
        "recommended_audit_owner": audit_owner,
    }
    sys.stdout.write(json.dumps(report, indent=2) + "\n")
    return 0


def _db_host(url: str) -> str | None:
    if "@" not in url:
        return None
    return url.split("@", 1)[1].split("/")[0].split(":")[0]


def _pick_audit_owner(owners: list[dict]) -> dict:
    """Choose owner for recommendation audits on this database."""
    seeded = [o for o in owners if "seeded_owner" in o["roles"]]
    reimport = [o for o in owners if "reimport_owner" in o["roles"]]
    prod = [o for o in owners if "production_owner" in o["roles"]]

    if prod and prod[0]["release_issue_count"] > 0 and prod[0]["cross_system_recommendation_count"] >= 20:
        choice = prod[0]
        reason = "Production/test owner has full cross-system snapshot (≥20 rows)."
    elif seeded:
        best = max(
            seeded,
            key=lambda o: (
                o["cross_system_recommendation_count"],
                o["recommendation_count"],
                o["release_issue_count"],
            ),
        )
        choice = best
        reason = (
            "Largest seeded recommendation footprint on this DB "
            f"(cross_latest={best['cross_system_recommendation_count']}, "
            f"releases={best['release_issue_count']})."
        )
    elif reimport:
        best = max(reimport, key=lambda o: o["release_issue_count"])
        choice = best
        reason = (
            "Reimport fixture has release catalog; use live candidate audit with --rebuild for persisted Top 20."
        )
    elif prod:
        choice = prod[0]
        reason = (
            "Production/test owner designated but catalog/recommendations empty on this DB—run seed_production_recommendations first."
        )
    else:
        choice = owners[0] if owners else {}
        reason = "No conventional owners; fallback to lowest id."

    return {
        "owner_id": choice.get("owner_id"),
        "email": choice.get("email"),
        "reason": reason,
        "commands": [
            f"python scripts/verify_cross_system_owner.py --email {choice.get('email')} --top 20",
            f"python scripts/p61_00_recommendation_audit.py --email {choice.get('email')} --top 20",
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())
