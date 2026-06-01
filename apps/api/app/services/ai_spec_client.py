from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from urllib import error, request

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

PROMPT_VERSION = "P60-03-v1"
FALLBACK_MODEL_NAME = "FALLBACK"
STATUS_SUCCESS = "SUCCESS"
STATUS_FALLBACK = "FALLBACK"


class AiSpecEvaluationStructuredOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ai_score: float = Field(ge=0.0, le=100.0)
    ai_confidence: float = Field(ge=0.0, le=1.0)
    risk_level: str
    ai_rationale: str = Field(min_length=1)


class AiSpecEngineError(Exception):
    pass


def build_ai_spec_json_schema() -> dict:
    return {
        "name": "ai_spec_evaluation",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "ai_score": {"type": "number", "minimum": 0, "maximum": 100},
                "ai_confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "risk_level": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH"]},
                "ai_rationale": {"type": "string", "minLength": 1},
            },
            "required": ["ai_score", "ai_confidence", "risk_level", "ai_rationale"],
        },
    }


SYSTEM_PROMPT = """You are a comic spec evaluation assistant for preorder research.

Rules:
- Review baseline deterministic scores and normalized signals; do not invent facts.
- Produce structured JSON only.
- ai_score is 0-100 spec/preorder interest (not a purchase order).
- ai_confidence is 0-1 based on signal clarity and baseline alignment.
- risk_level is LOW, MEDIUM, or HIGH for preorder/speculation risk.
- ai_rationale must be human-readable and include brief risk commentary.
- Never recommend auto-purchasing or submitting orders.
"""


def canonical_prompt_inputs(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def hash_prompt_inputs(payload: dict) -> str:
    encoded = canonical_prompt_inputs(payload).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_spec_evaluation_prompt(*, prompt_payload: dict) -> str:
    return (
        "Evaluate this spec candidate for preorder monitoring.\n"
        "Use the JSON context below.\n\n"
        f"{canonical_prompt_inputs(prompt_payload)}"
    )


def _normalize_risk_level(value: str) -> str:
    normalized = value.strip().upper()
    if normalized in {"LOW", "MEDIUM", "HIGH"}:
        return normalized
    return "MEDIUM"


def _risk_level_from_baseline_risk(risk_score: float) -> str:
    if risk_score <= 35.0:
        return "LOW"
    if risk_score <= 60.0:
        return "MEDIUM"
    return "HIGH"


@dataclass(frozen=True)
class AiSpecEvaluationResult:
    ai_score: float
    ai_confidence: float
    risk_level: str
    ai_rationale: str
    model_name: str
    evaluation_status: str


def generate_fallback_ai_spec_evaluation(
    *,
    prompt_payload: dict,
    baseline_score: float,
    baseline_confidence: float,
    baseline_risk_score: float,
) -> AiSpecEvaluationResult:
    signals = prompt_payload.get("signal_summary", {})
    normalized = signals.get("normalized_signals", []) if isinstance(signals, dict) else []
    signal_count = len(normalized) if isinstance(normalized, list) else 0
    signal_boost = min(8.0, signal_count * 1.5)
    ai_score = round(min(100.0, max(0.0, float(baseline_score) + signal_boost * 0.25)), 2)
    ai_confidence = round(min(1.0, max(0.0, float(baseline_confidence) * 0.88)), 3)
    risk_level = _risk_level_from_baseline_risk(float(baseline_risk_score))
    title = prompt_payload.get("title", "Release")
    publisher = prompt_payload.get("publisher", "Unknown publisher")
    profile = prompt_payload.get("owner_profile", {})
    profile_type = profile.get("profile_type", "COLLECTOR") if isinstance(profile, dict) else "COLLECTOR"
    rationale = (
        f"FALLBACK evaluation for {title} ({publisher}). "
        f"Baseline spec score {baseline_score:.1f} with risk index {baseline_risk_score:.1f} "
        f"and {signal_count} normalized signal(s). "
        f"Owner profile {profile_type} alignment considered without live AI provider. "
        f"Risk commentary: {risk_level} preorder/spec risk given current signals and baseline confidence "
        f"{baseline_confidence:.3f}."
    )
    return AiSpecEvaluationResult(
        ai_score=ai_score,
        ai_confidence=ai_confidence,
        risk_level=risk_level,
        ai_rationale=rationale,
        model_name=FALLBACK_MODEL_NAME,
        evaluation_status=STATUS_FALLBACK,
    )


def request_openai_ai_spec_evaluation(
    *,
    prompt_payload: dict,
    settings: Settings | None = None,
) -> AiSpecEvaluationResult:
    resolved = settings or get_settings()
    if not resolved.openai_api_key:
        raise AiSpecEngineError("OpenAI API key not configured")

    model_name = resolved.openai_order_parser_model
    user_prompt = build_spec_evaluation_prompt(prompt_payload=prompt_payload)
    body = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": build_ai_spec_json_schema(),
        },
    }
    http_request = request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {resolved.openai_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(http_request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise AiSpecEngineError(f"OpenAI API request failed: {detail or exc.reason}") from exc
    except error.URLError as exc:
        raise AiSpecEngineError("Unable to reach OpenAI API") from exc
    except TimeoutError as exc:
        raise AiSpecEngineError("OpenAI API request timed out") from exc

    try:
        message = payload["choices"][0]["message"]
        if message.get("refusal"):
            raise AiSpecEngineError(f"OpenAI refused request: {message['refusal']}")
        parsed = AiSpecEvaluationStructuredOutput.model_validate(json.loads(message["content"]))
    except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValidationError) as exc:
        raise AiSpecEngineError("OpenAI returned invalid structured evaluation") from exc

    return AiSpecEvaluationResult(
        ai_score=round(float(parsed.ai_score), 2),
        ai_confidence=round(float(parsed.ai_confidence), 3),
        risk_level=_normalize_risk_level(parsed.risk_level),
        ai_rationale=parsed.ai_rationale.strip(),
        model_name=model_name,
        evaluation_status=STATUS_SUCCESS,
    )


def evaluate_ai_spec_candidate(
    *,
    prompt_payload: dict,
    baseline_score: float,
    baseline_confidence: float,
    baseline_risk_score: float,
    settings: Settings | None = None,
) -> AiSpecEvaluationResult:
    resolved = settings or get_settings()
    if not resolved.openai_api_key:
        return generate_fallback_ai_spec_evaluation(
            prompt_payload=prompt_payload,
            baseline_score=baseline_score,
            baseline_confidence=baseline_confidence,
            baseline_risk_score=baseline_risk_score,
        )
    try:
        return request_openai_ai_spec_evaluation(prompt_payload=prompt_payload, settings=resolved)
    except AiSpecEngineError as exc:
        logger.warning("AI spec evaluation fallback triggered: %s", exc)
        return generate_fallback_ai_spec_evaluation(
            prompt_payload=prompt_payload,
            baseline_score=baseline_score,
            baseline_confidence=baseline_confidence,
            baseline_risk_score=baseline_risk_score,
        )
