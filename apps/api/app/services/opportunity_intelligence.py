from __future__ import annotations



from sqlmodel import Session, select



from app.models.release_intelligence import ReleaseIssue, ReleaseKeySignal, ReleaseSeries

from app.schemas.release_intelligence import ReleaseIssueRead, ReleaseSeriesRead

from app.schemas.release_platform import OpportunityIntelligenceRead, RankedOpportunityRead

from app.schemas.spec_intelligence import SpecRecommendationRead

from app.services.opportunity_scoring import compute_opportunity_ranking_score, user_owns_series

from app.services.spec_recommendation_agent import list_recommendations_for_owner





def _latest_recommendations_by_issue(session: Session, *, owner_user_id: int) -> dict[int, SpecRecommendationRead]:

    rows, _ = list_recommendations_for_owner(session, owner_user_id=owner_user_id, limit=500, offset=0)

    latest: dict[int, SpecRecommendationRead] = {}

    for row in rows:

        if row.release_issue_id not in latest:

            latest[row.release_issue_id] = row

    return latest





def _ranked_entry(

    *,

    category: str,

    issue: ReleaseIssue,

    series: ReleaseSeries,

    ranking_score: float,

    score_components: dict[str, float],

    recommendations: dict[int, SpecRecommendationRead],

) -> RankedOpportunityRead:

    return RankedOpportunityRead(

        category=category,

        release_issue_id=int(issue.id or 0),

        issue=ReleaseIssueRead.model_validate(issue),

        series=ReleaseSeriesRead.model_validate(series),

        ranking_score=round(ranking_score, 2),

        score_components=score_components,

        recommendation=recommendations.get(int(issue.id or 0)),

    )





def build_opportunity_intelligence(session: Session, *, owner_user_id: int) -> OpportunityIntelligenceRead:

    rows = session.exec(

        select(ReleaseIssue, ReleaseSeries)

        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)

        .where(ReleaseIssue.owner_user_id == owner_user_id)

    ).all()

    signals_by_issue: dict[int, set[str]] = {}

    for signal in session.exec(

        select(ReleaseKeySignal).where(ReleaseKeySignal.owner_user_id == owner_user_id)

    ).all():

        signals_by_issue.setdefault(signal.issue_id, set()).add(signal.signal_type)



    recommendations = _latest_recommendations_by_issue(session, owner_user_id=owner_user_id)

    ranked: list[RankedOpportunityRead] = []

    for issue, series in rows:

        issue_signals = signals_by_issue.get(int(issue.id or 0), set())

        score, components = compute_opportunity_ranking_score(

            session,

            owner_user_id=owner_user_id,

            issue=issue,

            series=series,

            signal_types=issue_signals,

        )

        ranked.append(

            _ranked_entry(

                category="TOP_NEW_OPPORTUNITIES",

                issue=issue,

                series=series,

                ranking_score=score,

                score_components=components,

                recommendations=recommendations,

            )

        )



    ranked.sort(key=lambda row: row.ranking_score, reverse=True)

    unowned_ranked = [

        row

        for row in ranked

        if not user_owns_series(

            session,

            owner_user_id=owner_user_id,

            publisher=row.series.publisher,

            series_name=row.series.series_name,

        )

    ]



    def filter_category(signal_type: str, category: str) -> list[RankedOpportunityRead]:

        items: list[RankedOpportunityRead] = []

        for issue, series in rows:

            if signal_type not in signals_by_issue.get(int(issue.id or 0), set()):

                continue

            issue_signals = signals_by_issue.get(int(issue.id or 0), set())

            score, components = compute_opportunity_ranking_score(

                session,

                owner_user_id=owner_user_id,

                issue=issue,

                series=series,

                signal_types=issue_signals,

            )

            items.append(

                _ranked_entry(

                    category=category,

                    issue=issue,

                    series=series,

                    ranking_score=score,

                    score_components=components,

                    recommendations=recommendations,

                )

            )

        items.sort(key=lambda row: row.ranking_score, reverse=True)

        return items[:15]



    variant_types = {"VARIANT_RATIO", "INCENTIVE_VARIANT", "HIGH_RATIO_VARIANT", "OPEN_ORDER_VARIANT"}

    variant_items: list[RankedOpportunityRead] = []

    for issue, series in rows:

        issue_signals = signals_by_issue.get(int(issue.id or 0), set())

        if not issue_signals.intersection(variant_types):

            continue

        score, components = compute_opportunity_ranking_score(

            session,

            owner_user_id=owner_user_id,

            issue=issue,

            series=series,

            signal_types=issue_signals,

        )

        variant_items.append(

            _ranked_entry(

                category="TOP_VARIANT_OPPORTUNITIES",

                issue=issue,

                series=series,

                ranking_score=score,

                score_components=components,

                recommendations=recommendations,

            )

        )

    variant_items.sort(key=lambda row: row.ranking_score, reverse=True)



    return OpportunityIntelligenceRead(

        top_new_opportunities=unowned_ranked[:15],

        top_spec_opportunities=ranked[:15],

        top_variant_opportunities=variant_items[:15],

        top_first_appearances=filter_category("FIRST_APPEARANCE", "TOP_FIRST_APPEARANCES"),

        top_milestone_books=filter_category("MILESTONE_NUMBERING", "TOP_MILESTONE_BOOKS"),

        top_new_number_ones=filter_category("NEW_NUMBER_ONE", "TOP_NEW_NUMBER_ONES"),

    )

