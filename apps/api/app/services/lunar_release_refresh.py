from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session

from app.services.auto_watchlist_agent import run_auto_watchlists
from app.services.future_buy_queue import build_future_buy_queue
from app.services.key_issue_agent import detect_key_issues
from app.services.new_number_one_agent import detect_new_number_ones
from app.services.run_continuity_agent import run_continuity_detection
from app.services.spec_recommendation_agent import run_spec_recommendations
from app.services.spec_scoring_agent import run_spec_scoring
from app.services.variant_intelligence_agent import detect_variant_signals


@dataclass(frozen=True)
class LunarReleaseRefreshSummary:
    release_signals_refreshed: bool
    watchlist_refreshed: bool
    continuity_refreshed: bool
    spec_scoring_refreshed: bool
    spec_recommendations_refreshed: bool
    future_buy_queue_available: bool


def refresh_release_intelligence_after_lunar_import(
    session: Session,
    *,
    owner_user_id: int,
) -> LunarReleaseRefreshSummary:
    detect_new_number_ones(session, owner_user_id=owner_user_id)
    detect_key_issues(session, owner_user_id=owner_user_id)
    detect_variant_signals(session, owner_user_id=owner_user_id)
    run_continuity_detection(session, owner_user_id=owner_user_id)
    run_auto_watchlists(session, owner_user_id=owner_user_id)
    run_spec_scoring(session, owner_user_id=owner_user_id)
    run_spec_recommendations(session, owner_user_id=owner_user_id)
    build_future_buy_queue(session, owner_user_id=owner_user_id)
    return LunarReleaseRefreshSummary(
        release_signals_refreshed=True,
        watchlist_refreshed=True,
        continuity_refreshed=True,
        spec_scoring_refreshed=True,
        spec_recommendations_refreshed=True,
        future_buy_queue_available=True,
    )
