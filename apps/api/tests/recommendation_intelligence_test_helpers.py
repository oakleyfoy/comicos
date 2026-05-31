from __future__ import annotations

from sqlmodel import Session

from app.models.release_intelligence import ReleaseIssue, ReleaseKeySignal, ReleaseSeries
from app.services.intelligence_seed import seed_intelligence_catalog
from app.services.key_issue_refresh import refresh_owner_key_issues
from app.services.market_demand_seed import seed_market_demand_baselines
from app.services.owner_manual_preference_seed import seed_manual_preferences_for_owner
from app.services.recommendation_v2_engine import generate_recommendations_v2
from app.services.spec_recommendation_agent import run_spec_recommendations
from app.services.spec_scoring_agent import run_spec_scoring
from release_platform_test_helpers import seed_release_platform_horizons


def seed_recommendation_intelligence_certification_stack(session: Session, *, owner_user_id: int) -> None:
    seed_intelligence_catalog(session)
    seed_market_demand_baselines(session)
    seed_manual_preferences_for_owner(session, owner_user_id=owner_user_id)
    seed_release_platform_horizons(session, owner_user_id=owner_user_id)

    tmnt = ReleaseSeries(
        owner_user_id=owner_user_id,
        publisher="IDW",
        series_name="TMNT",
        series_type="ONGOING",
        status="ACTIVE",
    )
    session.add(tmnt)
    session.commit()
    session.refresh(tmnt)
    issue = ReleaseIssue(
        owner_user_id=owner_user_id,
        release_uuid="p51-cert-tmnt-300",
        series_id=int(tmnt.id or 0),
        issue_number="300",
        title="TMNT #300",
        release_status="SCHEDULED",
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)
    session.add(
        ReleaseKeySignal(
            owner_user_id=owner_user_id,
            issue_id=int(issue.id or 0),
            signal_type="MILESTONE_NUMBERING",
            confidence_score=0.9,
            signal_payload_json={"issue_number": "300"},
        )
    )
    session.commit()

    refresh_owner_key_issues(session, owner_user_id=owner_user_id)
    run_spec_scoring(session, owner_user_id=owner_user_id)
    run_spec_recommendations(session, owner_user_id=owner_user_id)
    generate_recommendations_v2(session, owner_user_id=owner_user_id)
