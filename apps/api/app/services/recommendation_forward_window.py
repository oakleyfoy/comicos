"""Forward-looking recommendation window (90-day release horizon) and priority helpers."""

from __future__ import annotations

from datetime import date, timedelta

from sqlmodel import Session, select

from app.models import ComicIssue, ComicTitle, InventoryCopy, Publisher, OrderItem, Variant
from app.models.release_intelligence import ReleaseIssue, ReleaseKeySignal, ReleaseSeries, ReleaseVariant
from app.models.spec_intelligence import SpecRecommendation
from app.services.foc_dates import days_until_foc, utc_today
from app.services.lunar_issue_identity import normalize_lunar_issue_number
FORWARD_RECOMMENDATION_WINDOW_DAYS = 90
FOC_ACTIONABLE_OVERDUE_DAYS = 14

KEY_SIGNAL_TYPES = frozenset(
    {
        "NEW_NUMBER_ONE",
        "KEY_ISSUE",
        "FIRST_APPEARANCE",
        "FIRST_FULL_APPEARANCE",
        "FIRST_CAMEO",
        "ORIGIN",
        "MILESTONE_NUMBERING",
        "UNIVERSE_LAUNCH",
        "RELAUNCH",
        "VARIANT_HOT",
        "RATIO_VARIANT",
        "INCENTIVE_VARIANT",
    }
)

NEW_ONE_SIGNALS = frozenset({"NEW_NUMBER_ONE", "UNIVERSE_LAUNCH", "RELAUNCH"})


def _normalize_issue_number(value: str) -> str:
    return normalize_lunar_issue_number((value or "").strip())


def _normalize_series(value: str) -> str:
    return (value or "").strip().lower()


def _normalize_publisher(value: str) -> str:
    return (value or "").strip().lower()


def issue_in_forward_recommendation_window(issue: ReleaseIssue, *, today: date | None = None) -> bool:
    """True when a release belongs in the forward-looking Top Recommendations window."""
    ref = today or utc_today()
    if issue.release_date is not None:
        release_days = (issue.release_date - ref).days
        if 0 <= release_days <= FORWARD_RECOMMENDATION_WINDOW_DAYS:
            return True
    if issue.foc_date is not None:
        foc_days = days_until_foc(issue.foc_date, today=ref)
        if foc_days is not None and -FOC_ACTIONABLE_OVERDUE_DAYS <= foc_days <= FORWARD_RECOMMENDATION_WINDOW_DAYS:
            return True
    if (issue.release_status or "").upper() == "ANNOUNCED":
        return True
    return False


def foc_deadline_priority(foc_date: date | None, *, today: date | None = None) -> float:
    """Priority tier 1: FOC / preorder deadline risk (0–100)."""
    ref = today or utc_today()
    days = days_until_foc(foc_date, today=ref) if foc_date is not None else None
    if days is None:
        return 74.0
    if days < 0:
        return min(94.0, 88.0 + min(6.0, abs(days) * 0.5))
    if days <= 3:
        return 96.0
    if days <= 7:
        return 93.0
    if days <= 14:
        return 89.0
    if days <= 30:
        return 84.0
    if days <= 60:
        return 78.0
    if days <= 90:
        return 73.0
    return 68.0


def _is_number_one(issue_number: str) -> bool:
    normalized = _normalize_issue_number(issue_number)
    return normalized in {"1", "1.0"} or normalized.startswith("1/")


def _owned_issue_keys(session: Session, *, owner_user_id: int) -> set[tuple[str, str, str]]:
    rows = session.exec(
        select(Publisher.name, ComicTitle.name, ComicIssue.issue_number)
        .join(ComicIssue, ComicIssue.comic_title_id == ComicTitle.id)
        .join(Publisher, ComicTitle.publisher_id == Publisher.id)
        .join(Variant, Variant.comic_issue_id == ComicIssue.id)
        .join(InventoryCopy, InventoryCopy.variant_id == Variant.id)
        .where(InventoryCopy.user_id == owner_user_id)
    ).all()
    keys: set[tuple[str, str, str]] = set()
    for publisher, series_name, issue_number in rows:
        pub = _normalize_publisher(str(publisher))
        series = _normalize_series(str(series_name))
        issue = _normalize_issue_number(str(issue_number))
        if pub and series and issue:
            keys.add((pub, series, issue))
    return keys


def _latest_spec_by_issue(session: Session, *, owner_user_id: int) -> dict[int, SpecRecommendation]:
    rows = session.exec(
        select(SpecRecommendation)
        .join(ReleaseIssue, SpecRecommendation.release_issue_id == ReleaseIssue.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .order_by(SpecRecommendation.created_at.desc(), SpecRecommendation.id.desc())
    ).all()
    latest: dict[int, SpecRecommendation] = {}
    for row in rows:
        if row.release_issue_id not in latest:
            latest[row.release_issue_id] = row
    return latest


def _key_signals_by_issue(session: Session, *, issue_ids: list[int]) -> dict[int, list[str]]:
    if not issue_ids:
        return {}
    rows = session.exec(select(ReleaseKeySignal).where(ReleaseKeySignal.issue_id.in_(issue_ids))).all()
    grouped: dict[int, list[str]] = {}
    for row in rows:
        grouped.setdefault(int(row.issue_id), []).append(str(row.signal_type))
    return grouped


def hot_variants_for_issue(session: Session, *, issue_id: int) -> list[ReleaseVariant]:
    return list(session.exec(select(ReleaseVariant).where(ReleaseVariant.issue_id == issue_id)).all())


def compute_forward_catalog_priority(
    *,
    issue: ReleaseIssue,
    series: ReleaseSeries,
    owned: bool,
    key_signals: list[str],
    v2_total_score: float | None,
    spec_type: str | None,
    has_ratio_variant: bool,
    has_incentive_variant: bool = False,
    enrichment: "RecommendationPriorityEnrichment | None" = None,
    today: date | None = None,
) -> tuple[float, str, float | None]:
    """Return (priority_score, rationale_snippet, confidence_score) with additive signal separation."""
    from app.services.recommendation_priority_enrichment import (
        RecommendationPriorityEnrichment,
        generic_number_one_bonus,
    )

    ref = today or utc_today()
    base = foc_deadline_priority(issue.foc_date, today=ref)
    bonus = 0.0
    rationale_parts: list[str] = []

    if enrichment is not None:
        bonus += enrichment.franchise_bonus
        bonus += enrichment.publisher_bonus
        bonus += enrichment.historical_demand_bonus
        bonus += enrichment.continuity_bonus
        rationale_parts.extend(enrichment.rationale_bits)
    else:
        from app.services.recommendation_catalog_quality import publisher_boost_for

        bonus += publisher_boost_for(series.publisher) * 0.75

    signal_set = {s.upper() for s in key_signals}
    bonus += min(8.5, len(signal_set) * 1.1)

    franchise_tier = enrichment.franchise_bonus if enrichment is not None else 0.0
    number_one_bonus = generic_number_one_bonus(
        issue_number=issue.issue_number,
        key_signals=key_signals,
        franchise_bonus=franchise_tier,
    )
    if number_one_bonus > 0:
        bonus += number_one_bonus
        rationale_parts.append("Upcoming #1 or launch issue.")
    elif signal_set.intersection(NEW_ONE_SIGNALS):
        bonus += 2.75
        rationale_parts.append("Universe launch or relaunch signal.")
    elif signal_set.intersection(KEY_SIGNAL_TYPES):
        bonus += 3.5
        rationale_parts.append("Key or special issue signal.")

    if spec_type == "STRONG_BUY":
        bonus += 7.75
        rationale_parts.append("Spec/market heat (Strong Buy).")
    elif spec_type == "BUY":
        bonus += 5.25
        rationale_parts.append("Spec/market heat (Buy).")
    elif spec_type == "WATCH":
        bonus += 1.85

    if v2_total_score is not None:
        bonus += min(11.5, max(0.0, (float(v2_total_score) - 48.0) * 0.34))
        rationale_parts.append("Matches collector profile (V2 scoring).")

    if has_ratio_variant:
        bonus += 3.35
    if has_incentive_variant:
        bonus += 2.85
    if has_ratio_variant or has_incentive_variant:
        rationale_parts.append("Ratio or incentive variant worth watching.")

    if owned and (enrichment is None or enrichment.continuity_bonus < 2.0):
        bonus += 2.35
        rationale_parts.append("Run continuation — already collecting this series.")
    elif spec_type in {"STRONG_BUY", "BUY", "WATCH"}:
        rationale_parts.append("Not in inventory — forward acquisition target.")

    if issue.foc_date is not None:
        foc_days = days_until_foc(issue.foc_date, today=ref)
        if foc_days is not None:
            bonus += max(-0.25, min(3.75, (21 - float(foc_days)) * 0.13))
            if foc_days <= FORWARD_RECOMMENDATION_WINDOW_DAYS:
                rationale_parts.append(f"FOC window ({foc_days} days).")
    elif issue.release_date is not None:
        release_days = (issue.release_date - ref).days
        if 0 <= release_days <= FORWARD_RECOMMENDATION_WINDOW_DAYS:
            bonus += max(0.0, min(2.75, (45 - float(release_days)) * 0.05))
            rationale_parts.append(f"Release in {release_days} days.")

    issue_id = int(issue.id or 0)
    series_ord = sum(ord(c) for c in (series.series_name or "")[:12])
    bonus += (issue_id % 53) * 0.12 + (series_ord % 37) * 0.09

    priority = min(99.99, base + bonus)
    confidence = enrichment.confidence_score if enrichment is not None else None
    return round(max(0.0, priority), 2), " ".join(dict.fromkeys(rationale_parts)).strip(), confidence


def iter_forward_release_rows(
    session: Session,
    *,
    owner_user_id: int,
    today: date | None = None,
) -> list[tuple[ReleaseIssue, ReleaseSeries]]:
    ref = today or utc_today()
    rows = session.exec(
        select(ReleaseIssue, ReleaseSeries)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .order_by(ReleaseIssue.foc_date.asc().nulls_last(), ReleaseIssue.release_date.asc().nulls_last())
    ).all()
    return [(issue, series) for issue, series in rows if issue_in_forward_recommendation_window(issue, today=ref)]


def forward_window_diagnostics(session: Session, *, owner_user_id: int) -> dict[str, int]:
    from app.services.recommendation_v2_engine import _latest_scores_by_issue

    ref = utc_today()
    forward_rows = iter_forward_release_rows(session, owner_user_id=owner_user_id, today=ref)
    issue_ids = [int(i.id or 0) for i, _ in forward_rows if i.id is not None]
    owned = _owned_issue_keys(session, owner_user_id=owner_user_id)
    not_owned = 0
    for issue, series in forward_rows:
        key = (
            _normalize_publisher(series.publisher),
            _normalize_series(series.series_name),
            _normalize_issue_number(issue.issue_number),
        )
        if key not in owned:
            not_owned += 1
    return {
        "forward_window_days": FORWARD_RECOMMENDATION_WINDOW_DAYS,
        "forward_release_issues": len(forward_rows),
        "forward_not_in_inventory": not_owned,
        "v2_scored_issues": len(_latest_scores_by_issue(session, owner_user_id=owner_user_id)),
        "spec_recommendations": len(_latest_spec_by_issue(session, owner_user_id=owner_user_id)),
    }
