from __future__ import annotations

from datetime import date

from sqlmodel import Session, select

from app.models.release_intelligence import ReleaseIssue, ReleaseKeySignal, ReleaseSeries, ReleaseVariant
from app.services.personalization_agent import score_issue_for_owner
from app.services.release_horizon_engine import HORIZON_ANNOUNCED, _primary_horizon
from app.services.run_continuity_agent import _inventory_issue_rows, _issue_value
from app.services.spec_scoring_agent import PUBLISHER_STRENGTH, SIGNAL_WEIGHTS, build_spec_score

COMPONENT_NEW_NUMBER_ONE = "NEW_NUMBER_ONE_SCORE"
COMPONENT_FIRST_APPEARANCE = "FIRST_APPEARANCE_SCORE"
COMPONENT_NEW_CHARACTER = "NEW_CHARACTER_SCORE"
COMPONENT_MILESTONE = "MILESTONE_SCORE"
COMPONENT_ANNIVERSARY = "ANNIVERSARY_SCORE"
COMPONENT_MAJOR_DEVELOPMENT = "MAJOR_DEVELOPMENT_SCORE"
COMPONENT_VARIANT_SCARCITY = "VARIANT_SCARCITY_SCORE"
COMPONENT_CREATOR = "CREATOR_SCORE"
COMPONENT_PUBLISHER = "PUBLISHER_SCORE"
COMPONENT_USER_PREFERENCE = "USER_PREFERENCE_SCORE"
COMPONENT_CONTINUITY = "CONTINUITY_SCORE"
COMPONENT_HORIZON_PLANNING = "HORIZON_PLANNING_SCORE"

MAJOR_DEVELOPMENT_SIGNALS = frozenset({"DEATH_ISSUE", "STATUS_QUO_CHANGE", "ORIGIN_ISSUE"})
VARIANT_SIGNALS = frozenset({"VARIANT_RATIO", "INCENTIVE_VARIANT", "HIGH_RATIO_VARIANT", "OPEN_ORDER_VARIANT"})

HORIZON_PLANNING_WEIGHT = {
    HORIZON_ANNOUNCED: 50.0,
    "NEXT_90_DAYS": 45.0,
    "NEXT_60_DAYS": 35.0,
    "NEXT_30_DAYS": 25.0,
    "FOC_APPROACHING": 12.0,
    "RELEASING_SOON": 8.0,
    "RELEASED": 0.0,
}


def _series_owned_issue_values(session: Session, *, owner_user_id: int, publisher: str, series_name: str) -> set[float]:
    owned: set[float] = set()
    key = (publisher.lower(), series_name.lower())
    for row in _inventory_issue_rows(session, owner_user_id=owner_user_id):
        if (row.publisher.lower(), row.series_name.lower()) != key:
            continue
        value = _issue_value(row.issue_number)
        if value is not None:
            owned.add(value)
    return owned


def user_owns_series(session: Session, *, owner_user_id: int, publisher: str, series_name: str) -> bool:
    return bool(_series_owned_issue_values(session, owner_user_id=owner_user_id, publisher=publisher, series_name=series_name))


def compute_opportunity_score_components(
    session: Session,
    *,
    owner_user_id: int,
    issue: ReleaseIssue,
    series: ReleaseSeries,
    signal_types: set[str],
    today: date | None = None,
) -> dict[str, float]:
    today = today or date.today()
    signals = session.exec(select(ReleaseKeySignal).where(ReleaseKeySignal.issue_id == int(issue.id or 0))).all()
    variants = session.exec(select(ReleaseVariant).where(ReleaseVariant.issue_id == int(issue.id or 0))).all()
    signal_type_set = signal_types or {row.signal_type for row in signals}

    components: dict[str, float] = {
        COMPONENT_NEW_NUMBER_ONE: 0.0,
        COMPONENT_FIRST_APPEARANCE: 0.0,
        COMPONENT_NEW_CHARACTER: 0.0,
        COMPONENT_MILESTONE: 0.0,
        COMPONENT_ANNIVERSARY: 0.0,
        COMPONENT_MAJOR_DEVELOPMENT: 0.0,
        COMPONENT_VARIANT_SCARCITY: 0.0,
        COMPONENT_CREATOR: 0.0,
        COMPONENT_PUBLISHER: round(PUBLISHER_STRENGTH.get(series.publisher.upper(), 4.0), 2),
        COMPONENT_USER_PREFERENCE: 0.0,
        COMPONENT_CONTINUITY: 0.0,
        COMPONENT_HORIZON_PLANNING: 0.0,
    }

    if "NEW_NUMBER_ONE" in signal_type_set:
        components[COMPONENT_NEW_NUMBER_ONE] = SIGNAL_WEIGHTS.get("NEW_NUMBER_ONE", 18.0)
    if "FIRST_APPEARANCE" in signal_type_set:
        components[COMPONENT_FIRST_APPEARANCE] = SIGNAL_WEIGHTS.get("FIRST_APPEARANCE", 24.0)
    if "NEW_CHARACTER" in signal_type_set:
        components[COMPONENT_NEW_CHARACTER] = 20.0
    elif "FIRST_APPEARANCE" in signal_type_set:
        components[COMPONENT_NEW_CHARACTER] = 12.0
    if "MILESTONE_NUMBERING" in signal_type_set:
        components[COMPONENT_MILESTONE] = SIGNAL_WEIGHTS.get("MILESTONE_NUMBERING", 12.0)
    if "ANNIVERSARY_ISSUE" in signal_type_set:
        components[COMPONENT_ANNIVERSARY] = SIGNAL_WEIGHTS.get("ANNIVERSARY_ISSUE", 8.0)

    major = signal_type_set.intersection(MAJOR_DEVELOPMENT_SIGNALS)
    if major:
        components[COMPONENT_MAJOR_DEVELOPMENT] = round(
            sum(SIGNAL_WEIGHTS.get(signal, 10.0) for signal in major),
            2,
        )

    variant_score = 0.0
    for signal in signals:
        if signal.signal_type not in VARIANT_SIGNALS:
            continue
        variant_score += SIGNAL_WEIGHTS.get(signal.signal_type, 0.0)
        ratio = signal.signal_payload_json.get("ratio_value")
        if isinstance(ratio, int):
            variant_score += min(float(ratio) / 10.0, 10.0)
    for variant in variants:
        if variant.ratio_value:
            variant_score += min(float(variant.ratio_value) / 8.0, 8.0)
    components[COMPONENT_VARIANT_SCARCITY] = round(min(variant_score, 30.0), 2)

    creator_bonus = sum(2.0 for variant in variants if variant.cover_artist)
    components[COMPONENT_CREATOR] = round(min(creator_bonus, 12.0), 2)

    owned_values = _series_owned_issue_values(
        session,
        owner_user_id=owner_user_id,
        publisher=series.publisher,
        series_name=series.series_name,
    )
    target_value = _issue_value(issue.issue_number)
    if owned_values and target_value is not None:
        latest = max(owned_values)
        if target_value == latest + 1 and len(owned_values) >= 2:
            components[COMPONENT_CONTINUITY] = 22.0
        elif target_value == latest + 1:
            components[COMPONENT_CONTINUITY] = 10.0
        elif target_value in {300.0, 500.0, 1000.0} and latest >= target_value - 3:
            components[COMPONENT_CONTINUITY] = 18.0
    elif not owned_values:
        discovery_bonus = 8.0
        if "NEW_NUMBER_ONE" in signal_type_set or "FIRST_APPEARANCE" in signal_type_set:
            discovery_bonus = 16.0
        components[COMPONENT_CONTINUITY] = discovery_bonus

    base = build_spec_score(session, issue=issue, series=series).score_value
    personalization = score_issue_for_owner(
        session,
        owner_user_id=owner_user_id,
        issue=issue,
        series=series,
        base_score=base,
    )
    components[COMPONENT_USER_PREFERENCE] = round(
        float(personalization["adjusted_score"]) - float(personalization.get("base_score", base)),
        2,
    )

    primary = _primary_horizon(issue, today=today)
    components[COMPONENT_HORIZON_PLANNING] = HORIZON_PLANNING_WEIGHT.get(primary, 0.0)

    return components


def compute_opportunity_ranking_score(
    session: Session,
    *,
    owner_user_id: int,
    issue: ReleaseIssue,
    series: ReleaseSeries,
    signal_types: set[str],
    today: date | None = None,
) -> tuple[float, dict[str, float]]:
    components = compute_opportunity_score_components(
        session,
        owner_user_id=owner_user_id,
        issue=issue,
        series=series,
        signal_types=signal_types,
        today=today,
    )
    total = round(sum(components.values()), 2)
    return total, components


def is_strong_new_opportunity(signal_types: set[str], ranking_score: float) -> bool:
    if "NEW_NUMBER_ONE" in signal_types or "FIRST_APPEARANCE" in signal_types or "NEW_CHARACTER" in signal_types:
        return True
    if "MILESTONE_NUMBERING" in signal_types and ranking_score >= 40:
        return True
    if signal_types.intersection(MAJOR_DEVELOPMENT_SIGNALS) and ranking_score >= 35:
        return True
    return ranking_score >= 55
