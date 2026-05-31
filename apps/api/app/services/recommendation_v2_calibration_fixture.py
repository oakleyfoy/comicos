"""Deterministic 10-item V2 calibration fixture (P51-04B)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlmodel import Session

from app.models.key_issue_intelligence import KeyIssueProfile
from app.models.release_intelligence import ReleaseIssue, ReleaseKeySignal, ReleaseSeries, ReleaseVariant
from app.services.intelligence_seed import seed_intelligence_catalog
from app.services.market_demand_seed import seed_market_demand_baselines
from app.services.owner_manual_preference_seed import seed_manual_preferences_for_owner
from app.services.recommendation_v2_components import IssueComponentBundle, score_issue_components_v2
from app.services.recommendation_v2_engine import score_release_issue_v2
from app.models.recommendation_v2 import RecommendationRunV2
from app.services.market_demand_engine import refresh_market_demand
from app.services.user_preference_engine import refresh_user_preferences


@dataclass(frozen=True)
class CalibrationFixtureCase:
    case_id: str
    label: str


FIXTURE_CASES: tuple[CalibrationFixtureCase, ...] = (
    CalibrationFixtureCase("random_weak_number_one", "Random weak #1"),
    CalibrationFixtureCase("strong_investment_number_one", "Strong investment #1"),
    CalibrationFixtureCase("tmnt_milestone_non_one", "TMNT milestone non-#1"),
    CalibrationFixtureCase("gijoe_25_milestone", "GI Joe #25 milestone"),
    CalibrationFixtureCase("transformers_anniversary", "Transformers anniversary"),
    CalibrationFixtureCase("batman_non_one_key", "Batman non-#1 key issue"),
    CalibrationFixtureCase("image_creator_owned_one", "Image creator-owned #1"),
    CalibrationFixtureCase("ratio_variant_weak", "Ratio variant weak property"),
    CalibrationFixtureCase("user_preference_non_one", "User preference non-#1"),
    CalibrationFixtureCase("collector_edition_number_one", "Collector edition / omnibus / puzzle #1"),
)


@dataclass
class FixtureIssueRef:
    case_id: str
    label: str
    issue: ReleaseIssue
    series: ReleaseSeries
    variant: ReleaseVariant | None = None


@dataclass
class FixtureScoreRow:
    case_id: str
    label: str
    bundle: IssueComponentBundle
    rank: int = 0


def _add_issue(
    session: Session,
    *,
    owner_user_id: int,
    series: ReleaseSeries,
    release_uuid: str,
    issue_number: str,
    title: str,
    release_date: date | None = None,
) -> ReleaseIssue:
    issue = ReleaseIssue(
        owner_user_id=owner_user_id,
        release_uuid=release_uuid,
        series_id=int(series.id or 0),
        issue_number=issue_number,
        title=title,
        release_status="SCHEDULED",
        release_date=release_date or (date.today() + timedelta(days=21)),
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)
    return issue


def _add_key_profile(
    session: Session,
    *,
    issue_id: int,
    key_issue_type: str,
    importance: float,
) -> None:
    session.add(
        KeyIssueProfile(
            release_issue_id=issue_id,
            key_issue_type=key_issue_type,
            importance_score=importance,
            confidence_score=0.92,
            source_version="P51-04B-FIXTURE",
        )
    )
    session.commit()


def seed_calibration_fixture(session: Session, *, owner_user_id: int) -> list[FixtureIssueRef]:
    seed_intelligence_catalog(session)
    seed_market_demand_baselines(session)
    seed_manual_preferences_for_owner(session, owner_user_id=owner_user_id)
    refresh_market_demand(session)
    refresh_user_preferences(session, owner_user_id=owner_user_id)

    refs: list[FixtureIssueRef] = []

    weak_series = ReleaseSeries(
        owner_user_id=owner_user_id,
        publisher="INDIE",
        series_name="Obscure Limited QZX",
        series_type="LIMITED",
        status="ACTIVE",
    )
    tmnt_series = ReleaseSeries(
        owner_user_id=owner_user_id,
        publisher="IDW",
        series_name="TMNT",
        series_type="ONGOING",
        status="ACTIVE",
    )
    gijoe_series = ReleaseSeries(
        owner_user_id=owner_user_id,
        publisher="IDW",
        series_name="GI Joe",
        series_type="ONGOING",
        status="ACTIVE",
    )
    tf_series = ReleaseSeries(
        owner_user_id=owner_user_id,
        publisher="IDW",
        series_name="Transformers",
        series_type="ONGOING",
        status="ACTIVE",
    )
    batman_series = ReleaseSeries(
        owner_user_id=owner_user_id,
        publisher="DC",
        series_name="Batman",
        series_type="ONGOING",
        status="ACTIVE",
    )
    invincible_series = ReleaseSeries(
        owner_user_id=owner_user_id,
        publisher="Image Comics",
        series_name="Invincible",
        series_type="ONGOING",
        status="ACTIVE",
    )
    ratio_series = ReleaseSeries(
        owner_user_id=owner_user_id,
        publisher="INDIE",
        series_name="Hammerfist",
        series_type="LIMITED",
        status="ACTIVE",
    )
    collector_series = batman_series
    for s in (weak_series, tmnt_series, gijoe_series, tf_series, batman_series, invincible_series, ratio_series):
        session.add(s)
    session.commit()
    for s in (weak_series, tmnt_series, gijoe_series, tf_series, batman_series, invincible_series, ratio_series):
        session.refresh(s)

    random_one = _add_issue(
        session,
        owner_user_id=owner_user_id,
        series=weak_series,
        release_uuid="fix-random-weak-1",
        issue_number="1",
        title="Obscure Limited QZX #1",
    )
    refs.append(FixtureIssueRef("random_weak_number_one", FIXTURE_CASES[0].label, random_one, weak_series))

    strong_one = _add_issue(
        session,
        owner_user_id=owner_user_id,
        series=tmnt_series,
        release_uuid="fix-strong-tmnt-1",
        issue_number="1",
        title="TMNT #1",
    )
    session.add(
        ReleaseKeySignal(
            owner_user_id=owner_user_id,
            issue_id=int(strong_one.id or 0),
            signal_type="NEW_NUMBER_ONE",
            confidence_score=0.95,
            signal_payload_json={},
        )
    )
    session.commit()
    _add_key_profile(
        session, issue_id=int(strong_one.id or 0), key_issue_type="UNIVERSE_LAUNCH", importance=88.0
    )
    refs.append(FixtureIssueRef("strong_investment_number_one", FIXTURE_CASES[1].label, strong_one, tmnt_series))

    tmnt_milestone = _add_issue(
        session,
        owner_user_id=owner_user_id,
        series=tmnt_series,
        release_uuid="fix-tmnt-100",
        issue_number="100",
        title="TMNT #100",
    )
    _add_key_profile(
        session, issue_id=int(tmnt_milestone.id or 0), key_issue_type="MILESTONE_NUMBERING", importance=90.0
    )
    refs.append(FixtureIssueRef("tmnt_milestone_non_one", FIXTURE_CASES[2].label, tmnt_milestone, tmnt_series))

    gijoe25 = _add_issue(
        session,
        owner_user_id=owner_user_id,
        series=gijoe_series,
        release_uuid="fix-gijoe-25",
        issue_number="25",
        title="GI Joe #25",
    )
    _add_key_profile(session, issue_id=int(gijoe25.id or 0), key_issue_type="MILESTONE_NUMBERING", importance=94.0)
    refs.append(FixtureIssueRef("gijoe_25_milestone", FIXTURE_CASES[3].label, gijoe25, gijoe_series))

    tf_ann = _add_issue(
        session,
        owner_user_id=owner_user_id,
        series=tf_series,
        release_uuid="fix-tf-ann-3",
        issue_number="3",
        title="Transformers The Movie 40th Anniversary Edition #3",
    )
    _add_key_profile(session, issue_id=int(tf_ann.id or 0), key_issue_type="ANNIVERSARY", importance=88.0)
    refs.append(FixtureIssueRef("transformers_anniversary", FIXTURE_CASES[4].label, tf_ann, tf_series))

    batman_key = _add_issue(
        session,
        owner_user_id=owner_user_id,
        series=batman_series,
        release_uuid="fix-batman-12",
        issue_number="12",
        title="Batman #12",
    )
    _add_key_profile(session, issue_id=int(batman_key.id or 0), key_issue_type="MAJOR_STATUS_CHANGE", importance=82.0)
    refs.append(FixtureIssueRef("batman_non_one_key", FIXTURE_CASES[5].label, batman_key, batman_series))

    image_one = _add_issue(
        session,
        owner_user_id=owner_user_id,
        series=invincible_series,
        release_uuid="fix-invincible-1",
        issue_number="1",
        title="Invincible #1",
    )
    refs.append(FixtureIssueRef("image_creator_owned_one", FIXTURE_CASES[6].label, image_one, invincible_series))

    ratio_one = _add_issue(
        session,
        owner_user_id=owner_user_id,
        series=ratio_series,
        release_uuid="fix-hammerfist-1",
        issue_number="1",
        title="Hammerfist #1",
    )
    ratio_variant = ReleaseVariant(
        issue_id=int(ratio_one.id or 0),
        variant_uuid="fix-hammerfist-1-25",
        variant_name="1:25 Retailer Exclusive",
        ratio_value=25,
        ratio_type="ratio",
        variant_type="INCENTIVE",
        source_item_code="FIX-HF-25",
    )
    session.add(ratio_variant)
    session.commit()
    session.refresh(ratio_variant)
    refs.append(
        FixtureIssueRef("ratio_variant_weak", FIXTURE_CASES[7].label, ratio_one, ratio_series, variant=ratio_variant)
    )

    user_pref = _add_issue(
        session,
        owner_user_id=owner_user_id,
        series=batman_series,
        release_uuid="fix-batman-54",
        issue_number="54",
        title="Batman #54",
    )
    refs.append(FixtureIssueRef("user_preference_non_one", FIXTURE_CASES[8].label, user_pref, batman_series))

    collector = _add_issue(
        session,
        owner_user_id=owner_user_id,
        series=collector_series,
        release_uuid="fix-batman-omni-1",
        issue_number="1",
        title="Batman Gotham Adventures Omnibus HC #1",
    )
    refs.append(
        FixtureIssueRef("collector_edition_number_one", FIXTURE_CASES[9].label, collector, collector_series)
    )

    return refs


def score_calibration_fixture(session: Session, *, owner_user_id: int, refs: list[FixtureIssueRef]) -> list[FixtureScoreRow]:
    run = RecommendationRunV2(owner_user_id=owner_user_id, status="COMPLETED")
    session.add(run)
    session.commit()
    session.refresh(run)
    run_id = int(run.id or 0)

    rows: list[FixtureScoreRow] = []
    for ref in refs:
        if ref.variant is not None:
            bundle = score_issue_components_v2(
                session,
                owner_user_id=owner_user_id,
                issue=ref.issue,
                series=ref.series,
                variant=ref.variant,
            )
        else:
            score_release_issue_v2(
                session,
                owner_user_id=owner_user_id,
                run_id=run_id,
                issue=ref.issue,
                series=ref.series,
            )
            bundle = score_issue_components_v2(
                session, owner_user_id=owner_user_id, issue=ref.issue, series=ref.series, variant=ref.variant
            )
        rows.append(FixtureScoreRow(case_id=ref.case_id, label=ref.label, bundle=bundle))

    rows.sort(key=lambda r: r.bundle.total_score, reverse=True)
    for idx, row in enumerate(rows, start=1):
        row.rank = idx
    return rows


def weighted_component_contributions(bundle: IssueComponentBundle) -> dict[str, float]:
    out: dict[str, float] = {}
    for comp in bundle.components:
        sign = -1.0 if comp.component_name == "RISK_SCORE" else 1.0
        out[comp.component_name] = round(sign * comp.component_score * comp.component_weight, 4)
    return out


def dominant_ranking_driver(bundle: IssueComponentBundle) -> tuple[str, float, str]:
    """Return (driver_label, magnitude, kind) where kind is weighted|post_total."""
    contribs = weighted_component_contributions(bundle)
    top_weighted = max(contribs.items(), key=lambda item: item[1])
    post_delta = 0.0
    post_label = ""
    if bundle.score_trace and len(bundle.score_trace) >= 2:
        post_delta = bundle.score_trace[-1][1] - bundle.score_trace[0][1]
        if len(bundle.score_trace) >= 2:
            best_step = max(
                ((label, bundle.score_trace[i + 1][1] - bundle.score_trace[i][1]) for i, (label, _) in enumerate(bundle.score_trace[:-1])),
                key=lambda x: abs(x[1]),
                default=("", 0.0),
            )
            post_label = best_step[0]
            post_delta = best_step[1]
    if abs(post_delta) > top_weighted[1]:
        return post_label or "post_total_adjustments", abs(post_delta), "post_total"
    return top_weighted[0], top_weighted[1], "weighted"


def assert_fixture_ranking_passes(rows: list[FixtureScoreRow]) -> None:
    by_id = {r.case_id: r for r in rows}

    strong = by_id["strong_investment_number_one"].bundle.total_score
    random_weak = by_id["random_weak_number_one"].bundle.total_score
    tmnt = by_id["tmnt_milestone_non_one"].bundle.total_score
    gijoe = by_id["gijoe_25_milestone"].bundle.total_score
    tf = by_id["transformers_anniversary"].bundle.total_score
    batman_key = by_id["batman_non_one_key"].bundle.total_score
    user_pref = by_id["user_preference_non_one"].bundle.total_score
    collector = by_id["collector_edition_number_one"].bundle.total_score
    image_one = by_id["image_creator_owned_one"].bundle.total_score

    assert strong >= 72.0, f"Strong investment #1 should rank in STRONG_BUY+ territory (score={strong})"
    assert strong > random_weak, "Random weak #1 must not beat strong investment #1"
    assert random_weak < tmnt, "Random weak #1 must not beat TMNT milestone"
    assert random_weak < gijoe, "Random weak #1 must not beat GI Joe #25"
    assert random_weak < tf, "Random weak #1 must not beat Transformers anniversary"
    assert tmnt >= 58.0 and gijoe >= 58.0 and tf >= 58.0, (
        f"Key franchise milestones should rank BUY+ (tmnt={tmnt}, gijoe={gijoe}, tf={tf})"
    )
    assert user_pref > batman_key * 0.85 or user_pref >= 55.0, "User preference non-#1 should receive meaningful boost"
    assert collector < strong, "Collector omnibus #1 should be dampened vs strong investment #1"
    assert collector < tmnt, "Collector omnibus #1 should not beat TMNT milestone"
    assert image_one >= random_weak, "#1 Image creator-owned should still beat random weak #1"
    assert by_id["strong_investment_number_one"].rank <= 5, (
        f"Strong investment #1 should rank high (rank={by_id['strong_investment_number_one'].rank}, "
        f"top5={[r.case_id for r in rows[:5]]})"
    )

    top3_ids = {r.case_id for r in rows[:3]}
    key_cases = {"tmnt_milestone_non_one", "gijoe_25_milestone", "transformers_anniversary", "strong_investment_number_one"}
    assert top3_ids & key_cases, "At least one key milestone or strong investment #1 should be top 3"

    number_ones_in_top3 = sum(
        1
        for r in rows[:3]
        if r.case_id
        in {
            "random_weak_number_one",
            "strong_investment_number_one",
            "image_creator_owned_one",
            "collector_edition_number_one",
            "ratio_variant_weak",
        }
    )
    assert number_ones_in_top3 < 3, "Top 3 should not be all #1 issues"
