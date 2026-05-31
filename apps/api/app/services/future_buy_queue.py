from __future__ import annotations

from sqlmodel import Session

from app.schemas.release_intelligence import ReleaseIssueRead, ReleaseSeriesRead
from app.schemas.release_platform import FutureBuyQueueItemRead, FutureBuyQueueRead
from app.services.release_horizon_engine import list_issues_in_horizon_window
from app.services.spec_recommendation_agent import list_recommendations_for_owner


def _buy_category(recommendation_type: str) -> str:
    return {
        "STRONG_BUY": "MUST_BUY",
        "BUY": "STRONG_BUY",
        "WATCH": "WATCH",
        "PASS": "PASS",
    }.get(recommendation_type, "PASS")


def _default_score_for_issue(recommendation_type: str) -> float:
    return {
        "STRONG_BUY": 90.0,
        "BUY": 70.0,
        "WATCH": 45.0,
        "PASS": 20.0,
    }.get(recommendation_type, 20.0)


def build_future_buy_queue(session: Session, *, owner_user_id: int) -> FutureBuyQueueRead:
    recommendations, _ = list_recommendations_for_owner(session, owner_user_id=owner_user_id, limit=500, offset=0)
    rec_by_issue = {row.release_issue_id: row for row in recommendations}

    def window_items(max_days: int, horizon_window: str) -> list[FutureBuyQueueItemRead]:
        items: list[FutureBuyQueueItemRead] = []
        for issue, series in list_issues_in_horizon_window(
            session, owner_user_id=owner_user_id, max_release_days=max_days
        ):
            rec = rec_by_issue.get(int(issue.id or 0))
            rec_type = rec.recommendation_type if rec else "PASS"
            score = rec.recommendation_score if rec else _default_score_for_issue(rec_type)
            items.append(
                FutureBuyQueueItemRead(
                    horizon_window=horizon_window,
                    buy_category=_buy_category(rec_type),
                    release_issue_id=int(issue.id or 0),
                    issue=ReleaseIssueRead.model_validate(issue),
                    series=ReleaseSeriesRead.model_validate(series),
                    ranking_score=round(score, 2),
                )
            )
        items.sort(key=lambda row: row.ranking_score, reverse=True)
        return items

    return FutureBuyQueueRead(
        next_30_days=window_items(30, "NEXT_30_DAYS"),
        next_60_days=window_items(60, "NEXT_60_DAYS"),
        next_90_days=window_items(90, "NEXT_90_DAYS"),
    )
