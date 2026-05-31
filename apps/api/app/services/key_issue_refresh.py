from __future__ import annotations

from datetime import date

from sqlmodel import Session

from app.schemas.key_issue_intelligence import KeyIssueRefreshResponse
from app.services.intelligence_seed import catalog_is_seeded, seed_intelligence_catalog
from app.services.key_issue_dashboard import build_key_issue_dashboard, list_key_issues_for_owner
from app.services.key_issue_engine import run_key_issue_detection_for_owner
from app.services.key_issue_matching import match_catalog_key_issues_for_owner, match_pattern_key_issues_for_owner
from app.services.key_issue_scoring import apply_key_issue_scoring_for_owner


def refresh_owner_key_issues(session: Session, *, owner_user_id: int) -> KeyIssueRefreshResponse:
    if not catalog_is_seeded(session):
        seed_intelligence_catalog(session)
    detections = run_key_issue_detection_for_owner(session, owner_user_id=owner_user_id)
    catalog_matches = match_catalog_key_issues_for_owner(session, owner_user_id=owner_user_id)
    pattern_matches = match_pattern_key_issues_for_owner(session, owner_user_id=owner_user_id)
    scores_updated = apply_key_issue_scoring_for_owner(session, owner_user_id=owner_user_id)
    return KeyIssueRefreshResponse(
        detections_created=detections,
        catalog_matches=catalog_matches,
        pattern_matches=pattern_matches,
        scores_updated=scores_updated,
        refreshed_at=date.today(),
    )


__all__ = [
    "refresh_owner_key_issues",
    "build_key_issue_dashboard",
    "list_key_issues_for_owner",
]
