from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlmodel import Session, select

from app.models.ai_spec_evaluation import AISpecEvaluation
from app.models.future_release_action import FutureReleaseAction
from app.models.industry_opportunity import IndustryOpportunityScore
from app.models.purchase_quantity import PurchaseQuantityRecommendation
from app.models.spec_baseline_score import SpecBaselineScore
from app.models.spec_input import SpecInput
from app.models.top_spec_pick import TopSpecPick
from app.services.ai_spec_engine import generate_ai_spec_evaluations
from app.services.industry_opportunity_engine import _franchise_bonus
from app.services.industry_release_scans import latest_scan_run_id
from app.services.purchase_profiles import get_purchase_preferences, get_purchase_profile

ENGINE_VERSION = "P60-04-v1"
FUTURE_ACTION_BONUS = {
    "PREORDER_NOW": 12.0,
    "PREORDER_THIS_WEEK": 9.0,
    "WATCH": 4.0,
    "MISSED_FOC": -5.0,
}


@dataclass
class TopSpecPickGenerateResult:
    computed: int = 0
    skipped: bool = False


@dataclass(frozen=True)
class _RankedCandidate:
    spec_input_id: int
    release_id: int | None
    title: str
    publisher: str
    issue_number: str
    final_score: float
    confidence_score: float
    risk_level: str
    suggested_quantity: int | None
    foc_date: date | None
    release_date: date | None
    rationale: str
    sort_key: tuple


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _days_until_foc(foc_date: date | None) -> int:
    if foc_date is None:
        return 999_999
    today = datetime.now(timezone.utc).date()
    return (foc_date - today).days


def _foc_urgency_bonus(foc_date: date | None) -> float:
    days = _days_until_foc(foc_date)
    if days == 999_999:
        return 0.0
    if days < 0:
        return 1.0
    if days <= 3:
        return 8.0
    if days <= 7:
        return 5.0
    if days <= 14:
        return 3.0
    return 1.0


def _publisher_title_relevance(*, publisher: str, series_name: str, title: str) -> float:
    franchise_points, _ = _franchise_bonus(series_name=series_name, issue_title=title)
    publisher_bonus = 2.0 if publisher.strip() else 0.0
    return franchise_points + publisher_bonus


def _latest_quantity_by_release(session: Session, *, owner_user_id: int) -> dict[int, PurchaseQuantityRecommendation]:
    rows = session.exec(
        select(PurchaseQuantityRecommendation)
        .where(PurchaseQuantityRecommendation.owner_user_id == owner_user_id)
        .order_by(PurchaseQuantityRecommendation.created_at.desc(), PurchaseQuantityRecommendation.id.desc())
    ).all()
    latest: dict[int, PurchaseQuantityRecommendation] = {}
    for row in rows:
        if row.release_id not in latest:
            latest[row.release_id] = row
    return latest


def _latest_future_actions(session: Session, *, owner_user_id: int) -> dict[int, FutureReleaseAction]:
    rows = session.exec(
        select(FutureReleaseAction)
        .where(FutureReleaseAction.owner_user_id == owner_user_id)
        .where(FutureReleaseAction.release_id.is_not(None))
        .order_by(FutureReleaseAction.created_at.desc(), FutureReleaseAction.id.desc())
    ).all()
    latest: dict[int, FutureReleaseAction] = {}
    for row in rows:
        if row.release_id is None:
            continue
        rid = int(row.release_id)
        if rid not in latest:
            latest[rid] = row
    return latest


def _industry_opportunity_by_release(session: Session, *, owner_user_id: int) -> dict[int, IndustryOpportunityScore]:
    run_id = latest_scan_run_id(session, owner_user_id=owner_user_id)
    if run_id is None:
        return {}
    rows = session.exec(
        select(IndustryOpportunityScore)
        .where(IndustryOpportunityScore.owner_user_id == owner_user_id)
        .where(IndustryOpportunityScore.scan_run_id == run_id)
    ).all()
    latest: dict[int, IndustryOpportunityScore] = {}
    for row in rows:
        rid = int(row.release_id)
        prior = latest.get(rid)
        if prior is None or float(row.opportunity_score) > float(prior.opportunity_score):
            latest[rid] = row
    return latest


def _latest_ai_evaluations(session: Session, *, owner_user_id: int) -> dict[int, AISpecEvaluation]:
    rows = session.exec(
        select(AISpecEvaluation)
        .where(AISpecEvaluation.owner_user_id == owner_user_id)
        .order_by(AISpecEvaluation.created_at.desc(), AISpecEvaluation.id.desc())
    ).all()
    latest: dict[int, AISpecEvaluation] = {}
    for row in rows:
        sid = int(row.spec_input_id)
        if sid not in latest:
            latest[sid] = row
    return latest


def _latest_baselines(session: Session, *, owner_user_id: int) -> dict[int, SpecBaselineScore]:
    rows = session.exec(
        select(SpecBaselineScore).where(SpecBaselineScore.owner_user_id == owner_user_id)
    ).all()
    return {int(row.spec_input_id): row for row in rows}


def _compute_final_score(
    *,
    ai_score: float,
    baseline_score: float,
    industry_score: float | None,
    action_bonus: float,
    foc_bonus: float,
    relevance: float,
    profile_boost: float,
) -> float:
    industry_component = float(industry_score) if industry_score is not None else 0.0
    raw = (
        ai_score * 0.45
        + baseline_score * 0.25
        + industry_component * 0.15
        + action_bonus
        + foc_bonus
        + min(relevance, 14.0) * 0.35
        + profile_boost
    )
    return round(_clamp(raw, 0.0, 100.0), 2)


def _profile_boost(profile_type: str, *, speculation_score: float) -> float:
    normalized = profile_type.strip().upper()
    boost = 2.0
    if normalized in {"INVESTOR", "VARIANT_HUNTER"}:
        boost += 2.0
    if speculation_score >= 0.6:
        boost += 1.5
    return boost


def _build_candidates(
    session: Session,
    *,
    owner_user_id: int,
    spec_inputs: list[SpecInput],
    ai_by_input: dict[int, AISpecEvaluation],
    baseline_by_input: dict[int, SpecBaselineScore],
    industry_by_release: dict[int, IndustryOpportunityScore],
    actions_by_release: dict[int, FutureReleaseAction],
    quantity_by_release: dict[int, PurchaseQuantityRecommendation],
) -> list[_RankedCandidate]:
    profile = get_purchase_profile(session, owner_user_id=owner_user_id)
    prefs = get_purchase_preferences(session, owner_user_id=owner_user_id)
    profile_boost = _profile_boost(profile.profile_type, speculation_score=float(prefs.speculation_score))

    candidates: list[_RankedCandidate] = []
    for spec_input in spec_inputs:
        if spec_input.id is None:
            continue
        spec_input_id = int(spec_input.id)
        ai_row = ai_by_input.get(spec_input_id)
        baseline_row = baseline_by_input.get(spec_input_id)
        if ai_row is None or baseline_row is None:
            continue

        release_id = int(spec_input.release_id) if spec_input.release_id is not None else None
        industry = industry_by_release.get(release_id) if release_id is not None else None
        action = actions_by_release.get(release_id) if release_id is not None else None
        quantity = quantity_by_release.get(release_id) if release_id is not None else None

        action_bonus = FUTURE_ACTION_BONUS.get(action.action_type, 0.0) if action else 0.0
        foc_bonus = _foc_urgency_bonus(spec_input.foc_date)
        relevance = _publisher_title_relevance(
            publisher=spec_input.publisher,
            series_name=spec_input.series_name,
            title=spec_input.title,
        )
        final_score = _compute_final_score(
            ai_score=float(ai_row.ai_score),
            baseline_score=float(baseline_row.baseline_score),
            industry_score=float(industry.opportunity_score) if industry else None,
            action_bonus=action_bonus,
            foc_bonus=foc_bonus,
            relevance=relevance,
            profile_boost=profile_boost,
        )
        confidence_score = round(
            _clamp(float(ai_row.ai_confidence) * 0.65 + float(baseline_row.confidence_score) * 0.35, 0.0, 1.0),
            3,
        )
        risk_level = ai_row.risk_level
        suggested_quantity = int(quantity.quantity_recommended) if quantity else None

        rationale_parts = [
            f"Top spec rank inputs: AI score {ai_row.ai_score:.1f}, baseline {baseline_row.baseline_score:.1f}.",
        ]
        if industry is not None:
            rationale_parts.append(f"Industry opportunity {industry.opportunity_score:.1f}.")
        if action is not None:
            rationale_parts.append(f"Future release action {action.action_type} (+{action_bonus:.1f}).")
        if suggested_quantity is not None:
            rationale_parts.append(f"Suggested quantity bridge {suggested_quantity} (read-only P53 guidance).")
        rationale_parts.append(ai_row.ai_rationale[:280])
        rationale = " ".join(rationale_parts)

        foc_days = _days_until_foc(spec_input.foc_date)
        sort_key = (
            -final_score,
            -confidence_score,
            foc_days,
            -relevance,
            spec_input_id,
        )
        candidates.append(
            _RankedCandidate(
                spec_input_id=spec_input_id,
                release_id=release_id,
                title=spec_input.title,
                publisher=spec_input.publisher,
                issue_number=spec_input.issue_number,
                final_score=final_score,
                confidence_score=confidence_score,
                risk_level=risk_level,
                suggested_quantity=suggested_quantity,
                foc_date=spec_input.foc_date,
                release_date=spec_input.release_date,
                rationale=rationale,
                sort_key=sort_key,
            )
        )
    return candidates


def _dedupe_candidates(candidates: list[_RankedCandidate]) -> list[_RankedCandidate]:
    by_spec: dict[int, _RankedCandidate] = {}
    for candidate in sorted(candidates, key=lambda row: row.sort_key):
        prior = by_spec.get(candidate.spec_input_id)
        if prior is None or candidate.sort_key < prior.sort_key:
            by_spec[candidate.spec_input_id] = candidate

    by_release: dict[int, _RankedCandidate] = {}
    without_release: list[_RankedCandidate] = []
    for candidate in by_spec.values():
        if candidate.release_id is None:
            without_release.append(candidate)
            continue
        rid = int(candidate.release_id)
        prior = by_release.get(rid)
        if prior is None or candidate.sort_key < prior.sort_key:
            by_release[rid] = candidate

    merged = [*by_release.values(), *without_release]
    merged.sort(key=lambda row: row.sort_key)
    return merged


def _fingerprint(picks: list[_RankedCandidate]) -> str:
    payload = [
        {
            "rank": index,
            "spec_input_id": row.spec_input_id,
            "release_id": row.release_id,
            "final_score": row.final_score,
            "confidence_score": row.confidence_score,
            "risk_level": row.risk_level,
            "suggested_quantity": row.suggested_quantity,
        }
        for index, row in enumerate(picks, start=1)
    ]
    encoded = json.dumps({"version": ENGINE_VERSION, "picks": payload}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _existing_fingerprint(session: Session, *, owner_user_id: int) -> str | None:
    rows = session.exec(
        select(TopSpecPick)
        .where(TopSpecPick.owner_user_id == owner_user_id)
        .order_by(TopSpecPick.rank.asc(), TopSpecPick.id.asc())
    ).all()
    if not rows:
        return None
    payload = [
        {
            "rank": int(row.rank),
            "spec_input_id": int(row.spec_input_id),
            "release_id": int(row.release_id) if row.release_id is not None else None,
            "final_score": float(row.final_score),
            "confidence_score": float(row.confidence_score),
            "risk_level": row.risk_level,
            "suggested_quantity": int(row.suggested_quantity) if row.suggested_quantity is not None else None,
        }
        for row in rows
    ]
    encoded = json.dumps({"version": ENGINE_VERSION, "picks": payload}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def generate_top_spec_picks(session: Session, *, owner_user_id: int, limit: int = 20) -> TopSpecPickGenerateResult:
    limit = min(max(int(limit), 1), 20)
    generate_ai_spec_evaluations(session, owner_user_id=owner_user_id)

    spec_inputs = session.exec(select(SpecInput).where(SpecInput.owner_user_id == owner_user_id)).all()
    candidates = _build_candidates(
        session,
        owner_user_id=owner_user_id,
        spec_inputs=spec_inputs,
        ai_by_input=_latest_ai_evaluations(session, owner_user_id=owner_user_id),
        baseline_by_input=_latest_baselines(session, owner_user_id=owner_user_id),
        industry_by_release=_industry_opportunity_by_release(session, owner_user_id=owner_user_id),
        actions_by_release=_latest_future_actions(session, owner_user_id=owner_user_id),
        quantity_by_release=_latest_quantity_by_release(session, owner_user_id=owner_user_id),
    )
    ranked = _dedupe_candidates(candidates)[:limit]
    new_fp = _fingerprint(ranked)
    existing_fp = _existing_fingerprint(session, owner_user_id=owner_user_id)
    if existing_fp == new_fp:
        session.commit()
        return TopSpecPickGenerateResult(skipped=True)

    prior_rows = session.exec(select(TopSpecPick).where(TopSpecPick.owner_user_id == owner_user_id)).all()
    for row in prior_rows:
        session.delete(row)
    session.flush()

    created = 0
    for index, pick in enumerate(ranked, start=1):
        session.add(
            TopSpecPick(
                owner_user_id=owner_user_id,
                rank=index,
                release_id=pick.release_id,
                spec_input_id=pick.spec_input_id,
                title=pick.title,
                publisher=pick.publisher,
                issue_number=pick.issue_number,
                final_score=pick.final_score,
                confidence_score=pick.confidence_score,
                risk_level=pick.risk_level,
                suggested_quantity=pick.suggested_quantity,
                foc_date=pick.foc_date,
                release_date=pick.release_date,
                rationale=pick.rationale,
            )
        )
        created += 1

    session.commit()
    return TopSpecPickGenerateResult(computed=created)
