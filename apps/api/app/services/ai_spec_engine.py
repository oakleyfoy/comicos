from __future__ import annotations

import json
from dataclasses import dataclass

from sqlmodel import Session, select

from app.models.ai_spec_evaluation import AISpecEvaluation
from app.models.spec_baseline_score import SpecBaselineScore
from app.models.spec_input import SpecInput
from app.services.ai_spec_client import (
    PROMPT_VERSION,
    evaluate_ai_spec_candidate,
    hash_prompt_inputs,
)
from app.services.spec_baseline_engine import generate_spec_baseline_scores


@dataclass
class AISpecEvaluationGenerateResult:
    computed: int = 0
    skipped: int = 0
    updated: int = 0
    fallback_count: int = 0


def _parse_signal_summary(raw: str) -> dict:
    try:
        return json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}


def _build_prompt_payload(*, spec_input: SpecInput, baseline: SpecBaselineScore) -> dict:
    summary = _parse_signal_summary(spec_input.signal_summary)
    purchase_context = summary.get("purchase_context", {})
    return {
        "prompt_version": PROMPT_VERSION,
        "title": spec_input.title,
        "publisher": spec_input.publisher,
        "series_name": spec_input.series_name,
        "issue_number": spec_input.issue_number,
        "foc_date": spec_input.foc_date.isoformat() if spec_input.foc_date else None,
        "release_date": spec_input.release_date.isoformat() if spec_input.release_date else None,
        "signal_summary": summary,
        "baseline_score": float(baseline.baseline_score),
        "baseline_confidence": float(baseline.confidence_score),
        "baseline_risk_score": float(baseline.risk_score),
        "baseline_rationale": baseline.rationale,
        "owner_profile": purchase_context,
    }


def _upsert_evaluation(
    session: Session,
    *,
    owner_user_id: int,
    spec_input_id: int,
    baseline_score_id: int,
    prompt_inputs_hash: str,
    result,
) -> str:
    row = session.exec(
        select(AISpecEvaluation)
        .where(AISpecEvaluation.owner_user_id == owner_user_id)
        .where(AISpecEvaluation.spec_input_id == spec_input_id)
        .where(AISpecEvaluation.baseline_score_id == baseline_score_id)
        .where(AISpecEvaluation.prompt_version == PROMPT_VERSION)
    ).first()
    if row is None:
        row = AISpecEvaluation(
            owner_user_id=owner_user_id,
            spec_input_id=spec_input_id,
            baseline_score_id=baseline_score_id,
            ai_score=result.ai_score,
            ai_confidence=result.ai_confidence,
            risk_level=result.risk_level,
            ai_rationale=result.ai_rationale,
            model_name=result.model_name,
            prompt_version=PROMPT_VERSION,
            evaluation_status=result.evaluation_status,
            prompt_inputs_hash=prompt_inputs_hash,
        )
        session.add(row)
        return "computed"

    unchanged = (
        row.prompt_inputs_hash == prompt_inputs_hash
        and float(row.ai_score) == float(result.ai_score)
        and float(row.ai_confidence) == float(result.ai_confidence)
        and row.risk_level == result.risk_level
        and row.ai_rationale == result.ai_rationale
        and row.model_name == result.model_name
        and row.evaluation_status == result.evaluation_status
    )
    if unchanged:
        return "skipped"

    row.prompt_inputs_hash = prompt_inputs_hash
    row.ai_score = result.ai_score
    row.ai_confidence = result.ai_confidence
    row.risk_level = result.risk_level
    row.ai_rationale = result.ai_rationale
    row.model_name = result.model_name
    row.evaluation_status = result.evaluation_status
    session.add(row)
    return "updated"


def generate_ai_spec_evaluations(session: Session, *, owner_user_id: int) -> AISpecEvaluationGenerateResult:
    generate_spec_baseline_scores(session, owner_user_id=owner_user_id)
    outcome = AISpecEvaluationGenerateResult()

    baselines = session.exec(
        select(SpecBaselineScore).where(SpecBaselineScore.owner_user_id == owner_user_id)
    ).all()
    if not baselines:
        session.commit()
        return outcome

    inputs = {
        int(row.id or 0): row
        for row in session.exec(select(SpecInput).where(SpecInput.owner_user_id == owner_user_id)).all()
        if row.id is not None
    }

    for baseline in baselines:
        if baseline.id is None:
            continue
        spec_input = inputs.get(int(baseline.spec_input_id))
        if spec_input is None:
            continue
        prompt_payload = _build_prompt_payload(spec_input=spec_input, baseline=baseline)
        prompt_hash = hash_prompt_inputs(prompt_payload)
        evaluation = evaluate_ai_spec_candidate(
            prompt_payload=prompt_payload,
            baseline_score=float(baseline.baseline_score),
            baseline_confidence=float(baseline.confidence_score),
            baseline_risk_score=float(baseline.risk_score),
        )
        action = _upsert_evaluation(
            session,
            owner_user_id=owner_user_id,
            spec_input_id=int(spec_input.id or 0),
            baseline_score_id=int(baseline.id),
            prompt_inputs_hash=prompt_hash,
            result=evaluation,
        )
        if action == "computed":
            outcome.computed += 1
        elif action == "updated":
            outcome.updated += 1
        else:
            outcome.skipped += 1
        if action in {"computed", "updated"} and evaluation.evaluation_status == "FALLBACK":
            outcome.fallback_count += 1

    session.commit()
    return outcome
