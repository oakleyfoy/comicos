"""P52-02 Pull List Decision Engine — deterministic collector actions from V2 + pull lists."""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, select

from app.models.key_issue_intelligence import KeyIssueProfile
from app.models.pull_list import PullList, PullListIssue
from app.models.recommendation_v2 import RecommendationScoreV2
from app.models.release_intelligence import ReleaseIssue, ReleaseKeySignal, ReleaseSeries
from app.models.user_preference_intelligence import UserPreferenceProfile

DECISION_START_RUN = "START_RUN"
DECISION_CONTINUE_RUN = "CONTINUE_RUN"
DECISION_WATCH = "WATCH"
DECISION_PASS = "PASS"

BUY_TIERS = frozenset({"BUY", "STRONG_BUY", "MUST_BUY"})
MIN_START_RUN_CONFIDENCE = 0.55

START_RUN_REC_TYPES = frozenset(
    {
        "INVESTMENT_NUMBER_ONE",
        "START_RUN",
        "NEW_OPPORTUNITY",
    }
)
START_RUN_KEY_TYPES = frozenset({"UNIVERSE_LAUNCH", "RELAUNCH"})


@dataclass(frozen=True)
class PullListDecisionResult:
    decision_type: str
    confidence_score: float
    reasons: tuple[str, ...]


def _normalize_issue_number(value: str) -> str:
    cleaned = value.strip().lstrip("#").lower()
    if cleaned in {"1", "001", "1.0"}:
        return "1"
    return cleaned


def _is_number_one(issue: ReleaseIssue) -> bool:
    return _normalize_issue_number(issue.issue_number) == "1"


def _active_pull_list_for_release(
    session: Session,
    *,
    owner_user_id: int,
    release_id: int,
    series: ReleaseSeries,
) -> tuple[PullList | None, PullListIssue | None, int]:
    """Return (pull_list, issue_row, prior_issue_count) for continue-run context."""
    issue_row = session.exec(
        select(PullListIssue)
        .join(PullList, PullList.id == PullListIssue.pull_list_id)
        .where(PullList.owner_user_id == owner_user_id)
        .where(PullList.status == "ACTIVE")
        .where(PullListIssue.release_id == release_id)
    ).first()
    if issue_row is not None:
        pull_list = session.get(PullList, issue_row.pull_list_id)
        prior = session.exec(
            select(PullListIssue).where(PullListIssue.pull_list_id == int(issue_row.pull_list_id or 0))
        ).all()
        return pull_list, issue_row, len(prior)

    pull_list = session.exec(
        select(PullList)
        .where(PullList.owner_user_id == owner_user_id)
        .where(PullList.status == "ACTIVE")
        .where(PullList.publisher == series.publisher)
        .where(PullList.series_name == series.series_name)
    ).first()
    if pull_list is None:
        return None, None, 0
    prior = session.exec(
        select(PullListIssue).where(PullListIssue.pull_list_id == int(pull_list.id or 0))
    ).all()
    return pull_list, None, len(prior)


def _start_run_launch_signals(
    session: Session,
    *,
    issue: ReleaseIssue,
    series: ReleaseSeries,
    v2: RecommendationScoreV2 | None,
) -> list[str]:
    signals: list[str] = []
    if _is_number_one(issue):
        signals.append("New #1 issue")
    if v2 and v2.recommendation_type in START_RUN_REC_TYPES:
        signals.append(f"Recommendation type {v2.recommendation_type}")
    key_rows = session.exec(select(KeyIssueProfile).where(KeyIssueProfile.release_issue_id == int(issue.id or 0))).all()
    for profile in key_rows:
        if profile.key_issue_type in START_RUN_KEY_TYPES:
            signals.append(f"Key issue signal {profile.key_issue_type}")
    key_signals = session.exec(select(ReleaseKeySignal).where(ReleaseKeySignal.issue_id == int(issue.id or 0))).all()
    for sig in key_signals:
        if sig.signal_type in {"NEW_NUMBER_ONE", "RELAUNCH", "UNIVERSE_LAUNCH"}:
            signals.append(f"Release signal {sig.signal_type}")
    blob = f"{series.series_name} {series.publisher}".lower()
    if any(token in blob for token in ("batman", "spider-man", "tmnt", "x-men", "transformers", "spawn")):
        if _is_number_one(issue) or (v2 and v2.recommendation_type == "INVESTMENT_NUMBER_ONE"):
            signals.append("Major franchise launch")
    if "volume" in (issue.title or "").lower() or series.series_type in {"LIMITED", "MINI"} and _is_number_one(issue):
        signals.append("New volume")
    return signals


def _owner_has_preferences(session: Session, *, owner_user_id: int) -> bool:
    count = session.exec(
        select(UserPreferenceProfile).where(
            UserPreferenceProfile.owner_user_id == owner_user_id,
            UserPreferenceProfile.status == "ACTIVE",
        )
    ).all()
    return len(count) > 0


def evaluate_pull_list_decision(
    session: Session,
    *,
    owner_user_id: int,
    issue: ReleaseIssue,
    series: ReleaseSeries,
    v2: RecommendationScoreV2 | None,
) -> PullListDecisionResult:
    pull_list, issue_row, prior_count = _active_pull_list_for_release(
        session, owner_user_id=owner_user_id, release_id=int(issue.id or 0), series=series
    )

    if pull_list is not None and (issue_row is not None or prior_count >= 1):
        reasons: list[str] = ["Active pull list", f"Series {series.series_name} tracked"]
        if issue_row is not None:
            reasons.append("Release attached to pull list")
        if prior_count >= 1:
            reasons.append("Prior issues tracked on pull list")
        if issue.release_date:
            reasons.append("Upcoming release on calendar")
        confidence = 0.92 if issue_row is not None else 0.85
        if v2:
            confidence = round(min(0.98, max(confidence, float(v2.confidence_score))), 3)
        return PullListDecisionResult(
            decision_type=DECISION_CONTINUE_RUN,
            confidence_score=confidence,
            reasons=tuple(reasons),
        )

    if v2 is None:
        return PullListDecisionResult(
            decision_type=DECISION_PASS,
            confidence_score=0.35,
            reasons=("No Recommendation V2 score available", "Weak signals for collector action"),
        )

    launch_signals = _start_run_launch_signals(session, issue=issue, series=series, v2=v2)
    tier_ok = v2.recommendation_tier in BUY_TIERS
    confidence_ok = float(v2.confidence_score) >= MIN_START_RUN_CONFIDENCE

    if tier_ok and confidence_ok and launch_signals:
        reasons = [
            f"Recommendation tier {v2.recommendation_tier}",
            f"Recommendation score {v2.total_score:.1f}",
            *launch_signals[:4],
        ]
        if _owner_has_preferences(session, owner_user_id=owner_user_id):
            reasons.append("Owner preference profile available")
        return PullListDecisionResult(
            decision_type=DECISION_START_RUN,
            confidence_score=round(float(v2.confidence_score), 3),
            reasons=tuple(reasons),
        )

    if v2.recommendation_tier == "PASS" and float(v2.total_score) < 42.0:
        return PullListDecisionResult(
            decision_type=DECISION_PASS,
            confidence_score=round(min(0.5, float(v2.confidence_score)), 3),
            reasons=(
                f"Recommendation tier {v2.recommendation_tier}",
                "Weak signals",
                "Below collector action thresholds",
            ),
        )

    return PullListDecisionResult(
        decision_type=DECISION_WATCH,
        confidence_score=round(max(0.4, float(v2.confidence_score) * 0.85), 3),
        reasons=(
            f"Recommendation tier {v2.recommendation_tier}",
            "Moderate signals",
            "Insufficient conviction for start or continue run",
        ),
    )
