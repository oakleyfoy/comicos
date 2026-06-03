"""
P51-04 Recommendation Engine V2 — score component engine.

V1 audit (spec_scoring_agent / spec_recommendation_agent):
- Overweights: NEW_NUMBER_ONE (+18), variant/ratio signals, publisher_strength (Marvel/DC/Image),
  series_history_count, ReleaseKeySignal heuristics without P51 intelligence layers.
- Underweights: character/franchise/creator popularity (P51-01), KeyIssueProfile importance (P51-02),
  market demand & user preferences (P51-03), investment vs random #1 distinction, run-start collection value.

V2 combines P51-01/02/03 with explicit investment #1 and run-start components; #1 still scores but cannot
dominate without franchise/market/user/key-issue support.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlmodel import Session, select

from app.services.recommendation_v2_scoring_context import RecommendationV2ScoringContext

from app.models.collector_market_intelligence import MarketDemandProfile
from app.models.key_issue_intelligence import KeyIssueClassification, KeyIssueProfile
from app.models.release_intelligence import ReleaseIssue, ReleaseKeySignal, ReleaseSeries, ReleaseVariant
from app.models.release_watchlist import CollectionRun, ReleaseWatchlist, ReleaseWatchlistItem
from app.services.intelligence_matching import match_release_issue
from app.services.key_issue_scoring import score_key_issue_profile
from app.services.market_demand_engine import collector_demand_components
from app.services.market_user_intelligence import score_release_market_user_fit
from app.services.popularity_engine import character_score, creator_score, franchise_score

COMPONENT_NAMES = (
    "NEW_NUMBER_ONE_SCORE",
    "INVESTMENT_NUMBER_ONE_SCORE",
    "RUN_START_VALUE_SCORE",
    "CHARACTER_POPULARITY_SCORE",
    "FRANCHISE_STRENGTH_SCORE",
    "CREATOR_STRENGTH_SCORE",
    "KEY_ISSUE_SCORE",
    "FIRST_APPEARANCE_SCORE",
    "MILESTONE_SCORE",
    "ANNIVERSARY_SCORE",
    "VARIANT_SCARCITY_SCORE",
    "MARKET_DEMAND_SCORE",
    "USER_PREFERENCE_SCORE",
    "HORIZON_TIMING_SCORE",
    "CONTINUITY_SCORE",
    "RISK_SCORE",
)

INVESTMENT_FRANCHISE_TOKENS = (
    "batman",
    "spider-man",
    "spiderman",
    "tmnt",
    "teenage mutant ninja turtles",
    "invincible",
    "transformers",
    "g.i. joe",
    "gi joe",
    "gargoyles",
    "spawn",
    "x-men",
    "star wars",
    "venom",
    "wolverine",
    "deadpool",
)

KEY_ISSUE_BOOST_TYPES = {
    "FIRST_APPEARANCE",
    "FIRST_FULL_APPEARANCE",
    "FIRST_CAMEO",
    "ORIGIN",
    "DEATH",
    "RESURRECTION",
    "MAJOR_STATUS_CHANGE",
    "MILESTONE_NUMBERING",
    "ANNIVERSARY",
    "UNIVERSE_LAUNCH",
    "RELAUNCH",
}


@dataclass(frozen=True)
class ScoreComponentResult:
    component_name: str
    component_score: float
    component_weight: float
    explanation: str


@dataclass(frozen=True)
class IssueComponentBundle:
    components: list[ScoreComponentResult]
    total_score: float
    recommendation_tier: str
    recommendation_type: str
    confidence_score: float
    score_trace: tuple[tuple[str, float], ...] = ()


def _normalize_issue_number(value: str) -> str:
    cleaned = value.strip().lstrip("#").lower()
    if cleaned in {"1", "001", "1.0"}:
        return "1"
    return cleaned


def _is_number_one(issue: ReleaseIssue) -> bool:
    return _normalize_issue_number(issue.issue_number) == "1"


def _text_blob(*parts: str) -> str:
    return " ".join(p for p in parts if p).lower()


def _is_collector_edition_number_one(*parts: str) -> bool:
    blob = _text_blob(*parts)
    markers = (
        "omnibus",
        "compendium",
        "facsimile",
        "jigsaw",
        "puzzle",
        "cgc",
        "signed",
        "hardcover",
        " hc",
        " tp",
        "bookplate",
        "box set",
        "anniversary edition",
        "commissioned cover",
        "graded",
        "connecting set",
        "preserves:",
        "first book hc",
    )
    return any(marker in blob for marker in markers)


def _has_investment_franchise_signal(
    session: Session,
    *,
    issue: ReleaseIssue,
    series: ReleaseSeries,
    ctx: RecommendationV2ScoringContext | None = None,
) -> bool:
    if ctx is not None:
        match = ctx.match_release(session, issue=issue, series=series)
    else:
        match = match_release_issue(session, issue=issue, series=series)
    for entity in match.matched_entities:
        if entity.entity_type == "FRANCHISE":
            score = (
                ctx.popularity_score(session, entity_type="FRANCHISE", entity_id=entity.entity_id)
                if ctx is not None
                else franchise_score(session, franchise_id=entity.entity_id)
            )
            if score >= 65.0:
                return True
        if entity.entity_type == "CHARACTER":
            score = (
                ctx.popularity_score(session, entity_type="CHARACTER", entity_id=entity.entity_id)
                if ctx is not None
                else character_score(session, character_id=entity.entity_id)
            )
            if score >= 65.0:
                return True
    series_blob = _text_blob(series.series_name, series.publisher)
    if any(token in series_blob for token in INVESTMENT_FRANCHISE_TOKENS):
        return True
    profiles = ctx.market_demand_profiles if ctx is not None else session.exec(select(MarketDemandProfile)).all()
    for profile in profiles:
        name = profile.entity_name.lower()
        if float(profile.demand_score) >= 72.0 and name in series_blob:
            return True
    return False


def _creator_owned_image_launch(series: ReleaseSeries, issue: ReleaseIssue) -> bool:
    pub = series.publisher.lower()
    return "image" in pub and _is_number_one(issue)


def _affordable_ratio_variant(
    session: Session,
    *,
    issue_id: int,
    ctx: RecommendationV2ScoringContext | None = None,
) -> bool:
    variants = (
        ctx.variants_for(issue_id)
        if ctx is not None
        else session.exec(select(ReleaseVariant).where(ReleaseVariant.issue_id == issue_id)).all()
    )
    for variant in variants:
        if variant.ratio_value and variant.ratio_value <= 25:
            return True
        if variant.ratio_type and "ratio" in variant.ratio_type.lower():
            return True
    return False


def _key_issue_rows(
    session: Session,
    *,
    issue_id: int,
    ctx: RecommendationV2ScoringContext | None = None,
) -> list[KeyIssueProfile]:
    if ctx is not None:
        return list(ctx.key_profiles_for(issue_id))
    return list(session.exec(select(KeyIssueProfile).where(KeyIssueProfile.release_issue_id == issue_id)).all())


def _classification(
    session: Session,
    *,
    issue_id: int,
    ctx: RecommendationV2ScoringContext | None = None,
) -> str | None:
    if ctx is not None:
        return ctx.classification_for(issue_id)
    row = session.exec(
        select(KeyIssueClassification).where(KeyIssueClassification.release_issue_id == issue_id)
    ).first()
    return row.classification if row else None


def is_investment_number_one(
    session: Session,
    *,
    owner_user_id: int,
    issue: ReleaseIssue,
    series: ReleaseSeries,
    ctx: RecommendationV2ScoringContext | None = None,
) -> tuple[bool, list[str]]:
    if not _is_number_one(issue):
        return False, []
    blob = _text_blob(series.series_name, issue.title)
    if "facsimile" in blob or "reprint" in blob:
        return False, []
    if _is_collector_edition_number_one(series.series_name, issue.title, issue.issue_number):
        fit = (
            ctx.market_user_fit(session, issue=issue, series=series)
            if ctx is not None
            else score_release_market_user_fit(session, owner_user_id=owner_user_id, issue=issue, series=series)
        )
        if fit["user_preference_score"] < 72.0 and fit["market_demand_score"] < 78.0:
            profiles = _key_issue_rows(session, issue_id=int(issue.id or 0), ctx=ctx)
            if not any(p.key_issue_type in {"UNIVERSE_LAUNCH", "RELAUNCH", "FIRST_APPEARANCE", "ORIGIN"} for p in profiles):
                return False, ["collector edition #1 — needs stronger key/market/user support"]
    reasons: list[str] = []
    if _has_investment_franchise_signal(session, issue=issue, series=series, ctx=ctx):
        reasons.append("major franchise or character demand")
    if _creator_owned_image_launch(series, issue):
        reasons.append("creator-owned Image launch")
    profiles = _key_issue_rows(session, issue_id=int(issue.id or 0), ctx=ctx)
    for profile in profiles:
        if profile.key_issue_type in {"UNIVERSE_LAUNCH", "RELAUNCH", "FIRST_APPEARANCE", "ORIGIN"}:
            reasons.append(f"key issue signal {profile.key_issue_type}")
    fit = (
        ctx.market_user_fit(session, issue=issue, series=series)
        if ctx is not None
        else score_release_market_user_fit(session, owner_user_id=owner_user_id, issue=issue, series=series)
    )
    if fit["market_demand_score"] >= 75.0:
        reasons.append("strong market demand")
    if fit["user_preference_score"] >= 65.0:
        reasons.append("matches user preferences")
    if _affordable_ratio_variant(session, issue_id=int(issue.id or 0), ctx=ctx):
        reasons.append("affordable ratio variant")
    classification = _classification(session, issue_id=int(issue.id or 0), ctx=ctx)
    if classification in {"UNIVERSE_LAUNCH", "RELAUNCH"}:
        reasons.append(f"classification {classification}")
    if len(reasons) >= 2:
        return True, reasons
    if len(reasons) == 1:
        only = reasons[0]
        if only == "affordable ratio variant":
            return False, reasons
        strong_single = (
            only.startswith("key issue signal")
            or only.startswith("classification")
            or only == "creator-owned Image launch"
            or only == "strong market demand"
            or only == "matches user preferences"
            or (
                only == "major franchise or character demand"
                and (fit["market_demand_score"] >= 58.0 or fit["user_preference_score"] >= 58.0)
            )
        )
        if strong_single:
            return True, reasons
    return False, reasons


def compute_run_start_value_score(
    session: Session,
    *,
    owner_user_id: int,
    issue: ReleaseIssue,
    series: ReleaseSeries,
    ctx: RecommendationV2ScoringContext | None = None,
) -> tuple[float, str]:
    if not _is_number_one(issue):
        return 0.0, "Not a #1 issue"
    if series.series_type not in {"ONGOING", "LIMITED", "MINI"} and series.status not in {"ACTIVE", "ONGOING"}:
        base = 35.0
    else:
        base = 48.0
    blob = _text_blob(series.series_name, issue.title)
    if "facsimile" in blob or "reprint" in blob:
        return min(base, 28.0), "Facsimile/reprint #1 — limited run-start value"
    support = 0.0
    if _has_investment_franchise_signal(session, issue=issue, series=series, ctx=ctx):
        support += 22.0
    fit = (
        ctx.market_user_fit(session, issue=issue, series=series)
        if ctx is not None
        else score_release_market_user_fit(session, owner_user_id=owner_user_id, issue=issue, series=series)
    )
    support += min(fit["user_preference_score"] * 0.25, 18.0)
    support += min(fit["market_demand_score"] * 0.2, 16.0)
    score = round(min(72.0, base + support), 2)
    if _has_investment_franchise_signal(session, issue=issue, series=series, ctx=ctx) and fit["user_preference_score"] >= 70.0:
        score = round(min(78.0, base + support), 2)
    if _is_collector_edition_number_one(series.series_name, issue.title, issue.issue_number):
        score = round(min(score, 38.0), 2)
        return score, "Collector/reprint-style #1 — limited run-start value"
    return score, "Run-starting #1 with collection continuity potential" if score >= 55 else "Weak run-start signals"


def _tier_from_score(total: float) -> str:
    if total >= 85.0:
        return "MUST_BUY"
    if total >= 72.0:
        return "STRONG_BUY"
    if total >= 58.0:
        return "BUY"
    if total >= 40.0:
        return "WATCH"
    return "PASS"


def _pick_recommendation_type(
    *,
    is_investment: bool,
    run_start: float,
    key_types: set[str],
    key_overall: float,
    user_score: float,
    market_score: float,
    has_ratio: bool,
    is_new_one: bool,
) -> str:
    if is_investment:
        return "INVESTMENT_NUMBER_ONE"
    if key_overall >= 65.0 and key_types & KEY_ISSUE_BOOST_TYPES:
        return "KEY_ISSUE"
    if run_start >= 60.0:
        return "START_RUN"
    if key_types & KEY_ISSUE_BOOST_TYPES:
        return "KEY_ISSUE"
    if "MILESTONE_NUMBERING" in key_types:
        return "MILESTONE"
    if user_score >= 70.0:
        return "USER_PREFERENCE_MATCH"
    if market_score >= 78.0:
        return "MARKET_DEMAND_PLAY"
    if has_ratio:
        return "RATIO_VARIANT"
    if is_new_one:
        return "NEW_OPPORTUNITY"
    return "FRANCHISE_OPPORTUNITY"


def score_issue_components_v2(
    session: Session,
    *,
    owner_user_id: int,
    issue: ReleaseIssue,
    series: ReleaseSeries,
    variant: ReleaseVariant | None = None,
    ctx: RecommendationV2ScoringContext | None = None,
) -> IssueComponentBundle:
    issue_id = int(issue.id or 0)
    is_new_one = _is_number_one(issue)
    if ctx is not None:
        match = ctx.match_release(session, issue=issue, series=series, variant=variant)
    else:
        match = match_release_issue(session, issue=issue, series=series, variant=variant)
    char_score = 0.0
    fr_score = 0.0
    cr_score = 0.0
    for entity in match.matched_entities:
        conf = entity.match_confidence
        if entity.entity_type == "CHARACTER":
            raw = (
                ctx.popularity_score(session, entity_type="CHARACTER", entity_id=entity.entity_id)
                if ctx is not None
                else character_score(session, character_id=entity.entity_id)
            )
            char_score = max(char_score, raw * conf)
        elif entity.entity_type == "FRANCHISE":
            raw = (
                ctx.popularity_score(session, entity_type="FRANCHISE", entity_id=entity.entity_id)
                if ctx is not None
                else franchise_score(session, franchise_id=entity.entity_id)
            )
            fr_score = max(fr_score, raw * conf)
        elif entity.entity_type == "CREATOR":
            raw = (
                ctx.popularity_score(session, entity_type="CREATOR", entity_id=entity.entity_id)
                if ctx is not None
                else creator_score(session, creator_id=entity.entity_id)
            )
            cr_score = max(cr_score, raw * conf)

    key_profiles = _key_issue_rows(session, issue_id=issue_id, ctx=ctx)
    key_types = {p.key_issue_type for p in key_profiles}
    key_overall = 0.0
    first_app = 0.0
    milestone = 0.0
    anniversary = 0.0
    for profile in key_profiles:
        breakdown = score_key_issue_profile(session, profile=profile, issue=issue, series=series)
        key_overall = max(key_overall, breakdown.overall_key_issue_score)
        if profile.key_issue_type in {"FIRST_APPEARANCE", "FIRST_FULL_APPEARANCE", "FIRST_CAMEO"}:
            first_app = max(first_app, breakdown.overall_key_issue_score)
        if profile.key_issue_type == "MILESTONE_NUMBERING":
            milestone = max(milestone, breakdown.overall_key_issue_score)
        if profile.key_issue_type == "ANNIVERSARY":
            anniversary = max(anniversary, breakdown.overall_key_issue_score)

    fit = (
        ctx.market_user_fit(session, issue=issue, series=series)
        if ctx is not None
        else score_release_market_user_fit(session, owner_user_id=owner_user_id, issue=issue, series=series)
    )
    market_score = float(fit["market_demand_score"])
    user_score = float(fit["user_preference_score"])
    collector = (
        ctx.collector_demand(session, entity_name=series.series_name)
        if ctx is not None
        else collector_demand_components(session, entity_type="FRANCHISE", entity_name=series.series_name)
    )
    market_score = round((market_score + collector["long_term_score"]) / 2.0, 2)
    series_blob = _text_blob(series.series_name, series.publisher)
    demand_profiles = ctx.market_demand_profiles if ctx is not None else session.exec(select(MarketDemandProfile)).all()
    for profile in demand_profiles:
        if profile.entity_name.lower() in series_blob:
            market_score = max(market_score, float(profile.demand_score))
    if fr_score < 55.0 and market_score >= 75.0:
        fr_score = round(market_score * 0.88, 2)

    variants = ctx.variants_for(issue_id) if ctx is not None else session.exec(
        select(ReleaseVariant).where(ReleaseVariant.issue_id == issue_id)
    ).all()
    variant_scarcity = 0.0
    has_ratio = False
    for v in variants:
        if v.ratio_value:
            has_ratio = True
            variant_scarcity = max(variant_scarcity, min(100.0, 40.0 + v.ratio_value * 1.5))
        if v.is_incentive_variant:
            variant_scarcity = max(variant_scarcity, 55.0)
    if variant:
        if variant.ratio_value:
            variant_scarcity = max(variant_scarcity, min(100.0, 42.0 + variant.ratio_value * 1.5))

    new_one_score = 0.0
    if is_new_one:
        new_one_score = 36.0
        signals = ctx.signals_for(issue_id) if ctx is not None else session.exec(
            select(ReleaseKeySignal).where(ReleaseKeySignal.issue_id == issue_id)
        ).all()
        if any(s.signal_type == "NEW_NUMBER_ONE" for s in signals):
            new_one_score = 40.0

    investment_flag, investment_reasons = is_investment_number_one(
        session, owner_user_id=owner_user_id, issue=issue, series=series, ctx=ctx
    )
    investment_score = 0.0
    if is_new_one and investment_flag:
        investment_score = max(investment_score, min(100.0, 72.0 + len(investment_reasons) * 5.0))
    elif is_new_one:
        investment_score = 18.0

    run_start, run_explain = compute_run_start_value_score(
        session, owner_user_id=owner_user_id, issue=issue, series=series, ctx=ctx
    )

    horizon_score = 50.0
    if issue.release_date:
        days = (issue.release_date - date.today()).days
        if 0 <= days <= 14:
            horizon_score = 85.0
        elif 15 <= days <= 45:
            horizon_score = 72.0
        elif 46 <= days <= 90:
            horizon_score = 58.0
        elif days < 0:
            horizon_score = 35.0

    continuity_score = 0.0
    series_lower = series.series_name.lower()
    if ctx is not None:
        if series_lower in ctx.collection_run_series:
            continuity_score = 75.0
        if series_lower in ctx.watchlist_series:
            continuity_score = max(continuity_score, 68.0)
    else:
        runs = session.exec(select(CollectionRun).where(CollectionRun.owner_user_id == owner_user_id)).all()
        for run in runs:
            if run.series_name.lower() == series_lower:
                continuity_score = 75.0
                break
        watchlists = session.exec(
            select(ReleaseWatchlist).where(ReleaseWatchlist.owner_user_id == owner_user_id)
        ).all()
        wids = [int(w.id or 0) for w in watchlists]
        if wids:
            items = session.exec(
                select(ReleaseWatchlistItem).where(ReleaseWatchlistItem.watchlist_id.in_(wids))
            ).all()
            for item in items:
                if item.series_name and item.series_name.lower() == series_lower:
                    continuity_score = max(continuity_score, 68.0)

    risk_score = 0.0
    if is_new_one and not investment_flag and fr_score < 50 and key_overall < 45:
        risk_score = 72.0
    elif is_new_one and not investment_flag and key_overall < 52 and user_score < 58 and market_score < 58:
        risk_score = 58.0
    elif is_new_one and investment_flag:
        risk_score = 0.0
    if market_score < 45 and user_score < 52:
        risk_score = max(risk_score, 55.0)
    if len(variants) >= 5 and fr_score < 55:
        risk_score = max(risk_score, 50.0)

    components: list[ScoreComponentResult] = [
        ScoreComponentResult("NEW_NUMBER_ONE_SCORE", new_one_score, 0.04, "New #1 baseline credit" if is_new_one else "Not #1"),
        ScoreComponentResult(
            "INVESTMENT_NUMBER_ONE_SCORE",
            investment_score,
            0.11,
            "; ".join(investment_reasons) if investment_reasons else "Random or weak-demand #1",
        ),
        ScoreComponentResult("RUN_START_VALUE_SCORE", run_start, 0.09, run_explain),
        ScoreComponentResult("CHARACTER_POPULARITY_SCORE", round(char_score, 2), 0.07, "P51-01 character match"),
        ScoreComponentResult("FRANCHISE_STRENGTH_SCORE", round(fr_score, 2), 0.11, "P51-01 franchise match"),
        ScoreComponentResult("CREATOR_STRENGTH_SCORE", round(cr_score, 2), 0.04, "P51-01 creator match"),
        ScoreComponentResult("KEY_ISSUE_SCORE", round(key_overall, 2), 0.17, "P51-02 key issue importance"),
        ScoreComponentResult("FIRST_APPEARANCE_SCORE", round(first_app, 2), 0.04, "First appearance key issue"),
        ScoreComponentResult("MILESTONE_SCORE", round(milestone, 2), 0.04, "Milestone numbering"),
        ScoreComponentResult("ANNIVERSARY_SCORE", round(anniversary, 2), 0.03, "Anniversary issue"),
        ScoreComponentResult("VARIANT_SCARCITY_SCORE", round(variant_scarcity, 2), 0.03, "Variant/ratio scarcity"),
        ScoreComponentResult("MARKET_DEMAND_SCORE", round(market_score, 2), 0.12, "P51-03 market demand"),
        ScoreComponentResult("USER_PREFERENCE_SCORE", round(user_score, 2), 0.14, "P51-03 user preference fit"),
        ScoreComponentResult("HORIZON_TIMING_SCORE", horizon_score, 0.05, "Release horizon timing"),
        ScoreComponentResult("CONTINUITY_SCORE", continuity_score, 0.04, "Watchlist/collection continuity"),
        ScoreComponentResult("RISK_SCORE", risk_score, 0.12, "Risk penalty (subtracted)"),
    ]

    weighted_sum = 0.0
    weight_total = 0.0
    for comp in components:
        if comp.component_name == "RISK_SCORE":
            weighted_sum -= comp.component_score * comp.component_weight
            weight_total += comp.component_weight
        else:
            weighted_sum += comp.component_score * comp.component_weight
            weight_total += comp.component_weight
    total = round(max(0.0, min(100.0, weighted_sum / max(weight_total, 0.01))), 2)
    trace: list[tuple[str, float]] = [("weighted_component_mean", total)]

    def _step(label: str, new_total: float) -> float:
        nonlocal total
        total = round(max(0.0, min(100.0, new_total)), 2)
        trace.append((label, total))
        return total

    if is_new_one and not investment_flag:
        weak_support = key_overall < 52 and user_score < 58 and market_score < 58 and fr_score < 52
        if weak_support:
            _step("weak_random_number_one_dampener", total * 0.66)
        elif key_overall < 48 and user_score < 56 and market_score < 56:
            _step("unsupported_number_one_penalty", total - 10.0)
    if key_overall >= 62.0:
        key_boost = min(18.0, (key_overall - 55.0) * 0.32)
        if not is_new_one:
            key_boost += 5.0
        _step("key_issue_total_boost", total + key_boost)
    if user_score >= 62.0:
        _step("user_preference_total_boost", total + (user_score - 50.0) * 0.18)
    if not is_new_one and user_score >= 72.0:
        _step("user_preference_non_one_boost", total + 12.0 + (user_score - 72.0) * 0.2)
    if not is_new_one and user_score >= 78.0:
        _step("user_preference_high_non_one_boost", total + 10.0 + (user_score - 78.0) * 0.35)
    if not is_new_one and user_score >= 68.0 and key_overall >= 40.0:
        _step("user_pref_key_issue_combo_boost", total + 8.0 + key_overall * 0.06)
    if investment_flag and is_new_one:
        if _is_collector_edition_number_one(series.series_name, issue.title, issue.issue_number):
            _step("collector_edition_number_one_cap", min(total, 66.0))
        elif len(investment_reasons) >= 2:
            boost = 8.0 + len(investment_reasons) * 2.0 + max(0.0, user_score - 70.0) * 0.15
            if len(investment_reasons) >= 3:
                boost += 8.0
            _step("strong_investment_number_one_boost", total + boost)
        else:
            _step("investment_number_one_cap", min(total, 76.0))
    if key_overall >= 78.0 and total < 72.0:
        _step("high_key_issue_floor_boost", total + 8.0)

    tier = _tier_from_score(total)
    rec_type = _pick_recommendation_type(
        is_investment=investment_flag,
        run_start=run_start,
        key_types=key_types,
        key_overall=key_overall,
        user_score=user_score,
        market_score=market_score,
        has_ratio=has_ratio,
        is_new_one=is_new_one,
    )
    if (
        key_overall >= 64.0
        and key_types & KEY_ISSUE_BOOST_TYPES
        and rec_type == "INVESTMENT_NUMBER_ONE"
        and not is_new_one
    ):
        rec_type = "KEY_ISSUE"
    elif (
        key_overall >= 68.0
        and key_types & KEY_ISSUE_BOOST_TYPES
        and rec_type == "INVESTMENT_NUMBER_ONE"
        and _is_collector_edition_number_one(series.series_name, issue.title, issue.issue_number)
    ):
        rec_type = "KEY_ISSUE"
    elif user_score >= 72.0 and not investment_flag and user_score >= market_score:
        rec_type = "USER_PREFERENCE_MATCH"
    confidence = round(min(0.98, 0.35 + len(match.matched_entities) * 0.06 + len(key_profiles) * 0.05), 3)
    return IssueComponentBundle(
        components=components,
        total_score=total,
        recommendation_tier=tier,
        recommendation_type=rec_type,
        confidence_score=confidence,
        score_trace=tuple(trace),
    )
