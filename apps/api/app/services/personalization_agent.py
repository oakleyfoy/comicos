from __future__ import annotations

from decimal import Decimal

from sqlmodel import Session, select

from app.models.asset_ledger import Order
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.models.release_watchlist import CollectionRun, ReleaseWatchlist, ReleaseWatchlistItem


def build_owner_preference_profile(session: Session, *, owner_user_id: int) -> dict[str, object]:
    watchlists = session.exec(
        select(ReleaseWatchlist).where(ReleaseWatchlist.owner_user_id == owner_user_id)
    ).all()
    watchlist_ids = [int(row.id or 0) for row in watchlists]
    watchlist_items = (
        session.exec(select(ReleaseWatchlistItem).where(ReleaseWatchlistItem.watchlist_id.in_(watchlist_ids))).all()
        if watchlist_ids
        else []
    )
    runs = session.exec(select(CollectionRun).where(CollectionRun.owner_user_id == owner_user_id)).all()
    orders = session.exec(select(Order).where(Order.user_id == owner_user_id)).all()

    publisher_weights: dict[str, float] = {}
    series_weights: dict[str, float] = {}
    keyword_weights: dict[str, float] = {}

    for run in runs:
        publisher_weights[run.publisher.lower()] = publisher_weights.get(run.publisher.lower(), 0.0) + 0.15
        series_weights[run.series_name.lower()] = series_weights.get(run.series_name.lower(), 0.0) + 0.3
    for item in watchlist_items:
        if item.publisher:
            publisher_weights[item.publisher.lower()] = publisher_weights.get(item.publisher.lower(), 0.0) + 0.3
        if item.series_name:
            series_weights[item.series_name.lower()] = series_weights.get(item.series_name.lower(), 0.0) + 0.45
        for keyword in [item.keyword, item.character_name, item.creator_name]:
            if keyword:
                keyword_weights[keyword.lower()] = keyword_weights.get(keyword.lower(), 0.0) + 0.35

    average_order_total = float(
        sum((order.total_amount or Decimal("0")) for order in orders) / len(orders)
    ) if orders else 0.0
    return {
        "publisher_weights": publisher_weights,
        "series_weights": series_weights,
        "keyword_weights": keyword_weights,
        "purchase_history_count": len(orders),
        "affordable_variant_bias": 0.12 if average_order_total and average_order_total < 50 else 0.0,
    }


def score_issue_for_owner(
    session: Session,
    *,
    owner_user_id: int,
    issue: ReleaseIssue,
    series: ReleaseSeries,
    base_score: float,
    profile: dict[str, object] | None = None,
) -> dict[str, object]:
    if profile is None:
        profile = build_owner_preference_profile(session, owner_user_id=owner_user_id)
    matched_preferences: list[str] = []
    adjustment = 0.0
    publisher_weights = profile["publisher_weights"]
    series_weights = profile["series_weights"]
    keyword_weights = profile["keyword_weights"]
    assert isinstance(publisher_weights, dict)
    assert isinstance(series_weights, dict)
    assert isinstance(keyword_weights, dict)

    publisher_key = series.publisher.lower()
    series_key = series.series_name.lower()
    publisher_bonus = float(publisher_weights.get(publisher_key, 0.0))
    series_bonus = float(series_weights.get(series_key, 0.0))
    if publisher_bonus:
        matched_preferences.append(series.publisher)
        adjustment += publisher_bonus
    if series_bonus:
        matched_preferences.append(series.series_name)
        adjustment += series_bonus

    haystack = " ".join([series.publisher.lower(), series.series_name.lower(), issue.title.lower()])
    for keyword, weight in keyword_weights.items():
        if keyword in haystack:
            matched_preferences.append(keyword)
            adjustment += float(weight)

    if "ratio" in haystack and float(profile["affordable_variant_bias"]) > 0:
        matched_preferences.append("affordable ratio variants")
        adjustment += float(profile["affordable_variant_bias"])

    adjustment += min(float(profile["purchase_history_count"]) * 0.01, 0.15)
    adjusted_score = round(min(100.0, base_score * (1.0 + adjustment)), 2)
    return {
        "base_score": round(base_score, 2),
        "adjusted_score": adjusted_score,
        "weight_multiplier": round(1.0 + adjustment, 3),
        "matched_preferences": sorted(set(matched_preferences)),
    }


def generate_personalized_scores(session: Session, *, owner_user_id: int) -> list[dict[str, object]]:
    from app.services.spec_recommendation_agent import latest_score_rows_for_owner

    scores = latest_score_rows_for_owner(session, owner_user_id=owner_user_id)
    profile = build_owner_preference_profile(session, owner_user_id=owner_user_id)
    issues = {
        int(issue.id or 0): (issue, series)
        for issue, series in session.exec(
            select(ReleaseIssue, ReleaseSeries)
            .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
            .where(ReleaseIssue.owner_user_id == owner_user_id)
        ).all()
    }
    personalized: list[dict[str, object]] = []
    for score in scores:
        issue_pair = issues.get(score.release_issue_id)
        if issue_pair is None:
            continue
        issue, series = issue_pair
        personalization = score_issue_for_owner(
            session,
            owner_user_id=owner_user_id,
            issue=issue,
            series=series,
            base_score=score.score_value,
            profile=profile,
        )
        personalized.append(
            {
                "release_issue_id": score.release_issue_id,
                "score_grade": score.score_grade,
                **personalization,
            }
        )
    personalized.sort(key=lambda row: float(row["adjusted_score"]), reverse=True)
    return personalized
