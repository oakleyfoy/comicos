from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlmodel import Session, select

from app.models.spec_baseline_score import SpecBaselineScore
from app.models.spec_input import SpecInput
from app.services.industry_opportunity_engine import FRANCHISE_KEYWORDS, PUBLISHER_STRENGTH_BY_CODE
from app.services.industry_publisher_registry import INDUSTRY_PUBLISHER_REGISTRY
from app.services.key_issue_catalog import MILESTONE_ISSUE_NUMBERS
from app.services.lunar_issue_identity import normalize_lunar_issue_number
from app.services.opportunity_scoring import user_owns_series
from app.services.spec_input_builder import build_spec_inputs

FIRST_APPEARANCE_KEY_TYPES = frozenset(
    {
        "FIRST_APPEARANCE",
        "FIRST_FULL_APPEARANCE",
        "FIRST_CAMEO",
        "FIRST_TEAM_APPEARANCE",
        "FIRST_VILLAIN_APPEARANCE",
    }
)

KEY_EVENT_SIGNAL_TYPES = frozenset({"KEY_EVENT", "CROSSOVER", "MAJOR_EVENT"})


@dataclass
class SpecBaselineComputation:
    baseline_score: float
    confidence_score: float
    risk_score: float
    rationale: str


@dataclass
class SpecBaselineGenerateResult:
    computed: int = 0
    skipped: int = 0
    updated: int = 0


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _publisher_code(publisher: str) -> str:
    normalized = publisher.strip().lower()
    for code, name, _priority in INDUSTRY_PUBLISHER_REGISTRY:
        if name.lower() == normalized or code.lower() == normalized:
            return code.upper()
    return publisher.strip().upper().replace(" ", "_")[:32]


def _parse_summary(spec_input: SpecInput) -> dict:
    try:
        return json.loads(spec_input.signal_summary or "{}")
    except json.JSONDecodeError:
        return {}


def _signal_flags(normalized_signals: list[dict], *, issue_number: str) -> dict[str, bool]:
    flags = {
        "number_one": normalize_lunar_issue_number(issue_number.lstrip("#")) == "1",
        "first_appearance": False,
        "ratio_variant": False,
        "milestone": False,
        "anniversary": False,
        "key_event": False,
        "facsimile": False,
    }
    normalized_issue = normalize_lunar_issue_number(issue_number.lstrip("#"))
    if normalized_issue in MILESTONE_ISSUE_NUMBERS:
        flags["milestone"] = True

    for row in normalized_signals:
        kind = str(row.get("kind", ""))
        if kind == "industry_signal":
            signal_type = str(row.get("signal_type", "")).upper()
            if signal_type == "NUMBER_ONE":
                flags["number_one"] = True
            if signal_type == "FIRST_APPEARANCE":
                flags["first_appearance"] = True
            if signal_type == "RATIO_VARIANT":
                flags["ratio_variant"] = True
            if signal_type in {"MILESTONE", "MILESTONE_NUMBERING"}:
                flags["milestone"] = True
            if signal_type == "ANNIVERSARY":
                flags["anniversary"] = True
            if signal_type in KEY_EVENT_SIGNAL_TYPES:
                flags["key_event"] = True
            if signal_type == "FACSIMILE":
                flags["facsimile"] = True
        if kind == "key_issue_profile":
            key_type = str(row.get("key_issue_type", "")).upper()
            if key_type in FIRST_APPEARANCE_KEY_TYPES:
                flags["first_appearance"] = True
            if key_type == "MILESTONE_NUMBERING":
                flags["milestone"] = True
            if key_type == "ANNIVERSARY":
                flags["anniversary"] = True
            if key_type in {"MAJOR_EVENT", "UNIVERSE_LAUNCH", "RELAUNCH"}:
                flags["key_event"] = True
        if kind == "key_issue_signal":
            signal_type = str(row.get("signal_type", "")).upper()
            if signal_type in FIRST_APPEARANCE_KEY_TYPES:
                flags["first_appearance"] = True
            if signal_type in KEY_EVENT_SIGNAL_TYPES:
                flags["key_event"] = True

    return flags


def _franchise_bonus(*, series_name: str, title: str) -> tuple[float, list[str]]:
    haystack = f"{series_name} {title}".upper()
    hits: list[str] = []
    bonus = 0.0
    for keyword in FRANCHISE_KEYWORDS:
        if keyword in haystack and keyword not in hits:
            hits.append(keyword)
            bonus += 3.5
    return min(bonus, 14.0), hits


def _foc_urgency_points(foc_date: date | None) -> tuple[float, str]:
    if foc_date is None:
        return 0.0, "No FOC date on record"
    today = datetime.now(timezone.utc).date()
    days = (foc_date - today).days
    if days < 0:
        return 2.0, "FOC passed (late window)"
    if days <= 3:
        return 10.0, f"FOC urgency ({days} day(s))"
    if days <= 7:
        return 7.0, f"FOC approaching ({days} day(s))"
    if days <= 14:
        return 4.0, f"FOC horizon ({days} day(s))"
    return 1.0, f"FOC scheduled ({days} day(s))"


def _profile_alignment(
    purchase_context: dict,
    *,
    flags: dict[str, bool],
    collection_points: float,
) -> tuple[float, str]:
    profile_type = str(purchase_context.get("profile_type", "COLLECTOR")).upper()
    speculation = float(purchase_context.get("speculation_score", 0.5))
    variant_interest = float(purchase_context.get("variant_interest", 0.5))
    completionist = float(purchase_context.get("completionist_score", 0.5))

    points = 4.0
    notes = [f"Base profile alignment ({profile_type})"]

    if profile_type == "VARIANT_HUNTER" and flags["ratio_variant"]:
        points += 5.0
        notes.append("Variant hunter + ratio variant")
    if profile_type in {"COLLECTOR", "LONG_TERM_HOLD"} and collection_points >= 6.0:
        points += 4.0
        notes.append("Collector profile + series relevance")
    if profile_type == "INVESTOR" and (flags["first_appearance"] or flags["number_one"]):
        points += 5.0
        notes.append("Investor profile + spec issue signal")
    if speculation >= 0.6 and (flags["first_appearance"] or flags["number_one"]):
        points += 2.0
        notes.append("High speculation preference")
    if variant_interest >= 0.6 and flags["ratio_variant"]:
        points += 2.0
        notes.append("High variant interest")
    if completionist >= 0.6 and collection_points >= 4.0:
        points += 2.0
        notes.append("Completionist + owned series")

    return min(points, 12.0), "; ".join(notes)


def _collection_relevance(
    session: Session,
    *,
    owner_user_id: int,
    spec_input: SpecInput,
    normalized_signals: list[dict],
) -> tuple[float, str]:
    points = 0.0
    notes: list[str] = []
    if spec_input.publisher and spec_input.series_name:
        if user_owns_series(
            session,
            owner_user_id=owner_user_id,
            publisher=spec_input.publisher,
            series_name=spec_input.series_name,
        ):
            points += 6.0
            notes.append("Series in owner collection")

    for row in normalized_signals:
        if row.get("kind") == "pull_list_decision":
            decision = str(row.get("decision_type", "")).upper()
            if decision in {"START_RUN", "CONTINUE_RUN"}:
                points += 8.0
                notes.append(f"Pull list {decision}")
            elif decision == "WATCH":
                points += 3.0
                notes.append("Pull list WATCH")
        if row.get("kind") == "future_release_match":
            confidence = float(row.get("confidence", 0.0))
            if confidence >= 0.75:
                points += 4.0
                notes.append(f"Future release match ({confidence:.2f})")

    return min(points, 10.0), "; ".join(notes) if notes else "No collection linkage"


def _confidence_from_signals(normalized_signals: list[dict], *, factor_count: int) -> float:
    confidences: list[float] = []
    for row in normalized_signals:
        if "confidence_score" in row:
            confidences.append(float(row["confidence_score"]))
        elif row.get("kind") == "future_release_match" and "confidence" in row:
            confidences.append(float(row["confidence"]))
        elif row.get("kind") == "opportunity_score" and "confidence_score" in row:
            confidences.append(float(row["confidence_score"]))
    base = sum(confidences) / len(confidences) if confidences else 0.45
    coverage_boost = min(0.25, factor_count * 0.03)
    return round(_clamp(base + coverage_boost, 0.0, 1.0), 3)


def compute_spec_baseline_for_input(
    session: Session,
    *,
    owner_user_id: int,
    spec_input: SpecInput,
) -> SpecBaselineComputation:
    summary = _parse_summary(spec_input)
    normalized_signals: list[dict] = list(summary.get("normalized_signals", []))
    purchase_context: dict = dict(summary.get("purchase_context", {}))

    flags = _signal_flags(normalized_signals, issue_number=spec_input.issue_number)
    rationale_parts: list[str] = []
    raw_score = 0.0
    factor_count = 0

    if flags["number_one"]:
        raw_score += 15.0
        factor_count += 1
        rationale_parts.append("#1 issue: +15.0")
    if flags["first_appearance"]:
        raw_score += 18.0
        factor_count += 1
        rationale_parts.append("First appearance: +18.0")
    if flags["ratio_variant"]:
        raw_score += 10.0
        factor_count += 1
        rationale_parts.append("Ratio variant: +10.0")
    if flags["milestone"]:
        raw_score += 10.0
        factor_count += 1
        rationale_parts.append("Milestone issue: +10.0")
    if flags["anniversary"]:
        raw_score += 7.0
        factor_count += 1
        rationale_parts.append("Anniversary: +7.0")
    if flags["key_event"]:
        raw_score += 8.0
        factor_count += 1
        rationale_parts.append("Key event: +8.0")

    publisher_code = _publisher_code(spec_input.publisher)
    publisher_points = PUBLISHER_STRENGTH_BY_CODE.get(publisher_code, 5.0)
    raw_score += publisher_points
    factor_count += 1
    rationale_parts.append(f"Publisher strength ({spec_input.publisher or publisher_code}): +{publisher_points:.1f}")

    franchise_points, franchise_hits = _franchise_bonus(series_name=spec_input.series_name, title=spec_input.title)
    if franchise_points:
        raw_score += franchise_points
        factor_count += 1
        rationale_parts.append(f"Franchise/title strength ({', '.join(franchise_hits)}): +{franchise_points:.1f}")

    collection_points, collection_note = _collection_relevance(
        session,
        owner_user_id=owner_user_id,
        spec_input=spec_input,
        normalized_signals=normalized_signals,
    )
    if collection_points:
        raw_score += collection_points
        factor_count += 1
        rationale_parts.append(f"Collection relevance: +{collection_points:.1f} ({collection_note})")

    profile_points, profile_note = _profile_alignment(
        purchase_context,
        flags=flags,
        collection_points=collection_points,
    )
    raw_score += profile_points
    factor_count += 1
    rationale_parts.append(f"Owner profile alignment: +{profile_points:.1f} ({profile_note})")

    foc_points, foc_note = _foc_urgency_points(spec_input.foc_date)
    raw_score += foc_points
    if foc_points:
        factor_count += 1
    rationale_parts.append(f"FOC urgency: +{foc_points:.1f} ({foc_note})")

    baseline_score = round(_clamp(raw_score, 0.0, 100.0), 2)
    confidence_score = _confidence_from_signals(normalized_signals, factor_count=factor_count)

    risk_score = 50.0
    if flags["facsimile"]:
        risk_score += 25.0
    if baseline_score >= 70.0:
        risk_score -= 18.0
    elif baseline_score >= 45.0:
        risk_score -= 8.0
    if confidence_score >= 0.75:
        risk_score -= 12.0
    elif confidence_score < 0.45:
        risk_score += 10.0
    if flags["first_appearance"] or flags["number_one"]:
        risk_score -= 8.0
    if collection_points >= 6.0:
        risk_score -= 6.0
    risk_tolerance = float(purchase_context.get("risk_tolerance", 0.5))
    if risk_tolerance < 0.4 and flags["ratio_variant"] and not flags["first_appearance"]:
        risk_score += 8.0
    risk_score = round(_clamp(risk_score, 0.0, 100.0), 2)

    rationale_parts.append(f"Baseline={baseline_score:.1f}, confidence={confidence_score:.3f}, risk={risk_score:.1f}")
    return SpecBaselineComputation(
        baseline_score=baseline_score,
        confidence_score=confidence_score,
        risk_score=risk_score,
        rationale="; ".join(rationale_parts),
    )


def _upsert_baseline_score(
    session: Session,
    *,
    owner_user_id: int,
    spec_input_id: int,
    computation: SpecBaselineComputation,
) -> tuple[SpecBaselineScore, str]:
    row = session.exec(
        select(SpecBaselineScore)
        .where(SpecBaselineScore.owner_user_id == owner_user_id)
        .where(SpecBaselineScore.spec_input_id == spec_input_id)
    ).first()
    if row is None:
        row = SpecBaselineScore(
            owner_user_id=owner_user_id,
            spec_input_id=spec_input_id,
            baseline_score=computation.baseline_score,
            confidence_score=computation.confidence_score,
            risk_score=computation.risk_score,
            rationale=computation.rationale,
        )
        session.add(row)
        return row, "computed"

    unchanged = (
        float(row.baseline_score) == float(computation.baseline_score)
        and float(row.confidence_score) == float(computation.confidence_score)
        and float(row.risk_score) == float(computation.risk_score)
        and row.rationale == computation.rationale
    )
    if unchanged:
        return row, "skipped"

    row.baseline_score = computation.baseline_score
    row.confidence_score = computation.confidence_score
    row.risk_score = computation.risk_score
    row.rationale = computation.rationale
    session.add(row)
    return row, "updated"


def generate_spec_baseline_scores(session: Session, *, owner_user_id: int) -> SpecBaselineGenerateResult:
    build_spec_inputs(session, owner_user_id=owner_user_id)
    result = SpecBaselineGenerateResult()
    inputs = session.exec(select(SpecInput).where(SpecInput.owner_user_id == owner_user_id)).all()
    for spec_input in inputs:
        if spec_input.id is None:
            continue
        computation = compute_spec_baseline_for_input(session, owner_user_id=owner_user_id, spec_input=spec_input)
        _, action = _upsert_baseline_score(
            session,
            owner_user_id=owner_user_id,
            spec_input_id=int(spec_input.id),
            computation=computation,
        )
        if action == "computed":
            result.computed += 1
        elif action == "updated":
            result.updated += 1
        else:
            result.skipped += 1
    session.commit()
    return result
