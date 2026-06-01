from __future__ import annotations

from sqlmodel import Session, select

from app.models.ai_spec_evaluation import AISpecEvaluation
from app.models.spec_input import SpecInput
from app.schemas.ai_spec_evaluation import (
    AISpecEvaluationLatestRead,
    AISpecEvaluationRead,
    AISpecEvaluationSummaryRead,
)
from app.services.ai_spec_engine import generate_ai_spec_evaluations


def _to_read(row: AISpecEvaluation, *, spec_input: SpecInput | None) -> AISpecEvaluationRead:
    return AISpecEvaluationRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        spec_input_id=int(row.spec_input_id),
        baseline_score_id=int(row.baseline_score_id),
        release_id=int(spec_input.release_id) if spec_input and spec_input.release_id is not None else None,
        title=spec_input.title if spec_input else "",
        publisher=spec_input.publisher if spec_input else "",
        series_name=spec_input.series_name if spec_input else "",
        issue_number=spec_input.issue_number if spec_input else "",
        ai_score=float(row.ai_score),
        ai_confidence=float(row.ai_confidence),
        risk_level=row.risk_level,
        ai_rationale=row.ai_rationale,
        model_name=row.model_name,
        prompt_version=row.prompt_version,
        evaluation_status=row.evaluation_status,
        created_at=row.created_at.isoformat(),
    )


def _input_map(session: Session, *, owner_user_id: int) -> dict[int, SpecInput]:
    rows = session.exec(select(SpecInput).where(SpecInput.owner_user_id == owner_user_id)).all()
    return {int(row.id or 0): row for row in rows if row.id is not None}


def list_ai_spec_evaluations(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AISpecEvaluationRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    inputs = _input_map(session, owner_user_id=owner_user_id)
    rows = session.exec(
        select(AISpecEvaluation)
        .where(AISpecEvaluation.owner_user_id == owner_user_id)
        .order_by(AISpecEvaluation.ai_score.desc(), AISpecEvaluation.id.desc())
    ).all()
    total = len(rows)
    page = rows[offset : offset + limit]
    return [_to_read(row, spec_input=inputs.get(int(row.spec_input_id))) for row in page], total


def refresh_latest_ai_spec_evaluations(session: Session, *, owner_user_id: int) -> AISpecEvaluationLatestRead:
    gen = generate_ai_spec_evaluations(session, owner_user_id=owner_user_id)
    items, _ = list_ai_spec_evaluations(session, owner_user_id=owner_user_id, limit=200, offset=0)
    return AISpecEvaluationLatestRead(
        evaluations_computed=gen.computed,
        evaluations_skipped=gen.skipped,
        evaluations_updated=gen.updated,
        fallback_count=gen.fallback_count,
        items=items,
    )


def build_ai_spec_evaluation_summary(session: Session, *, owner_user_id: int) -> AISpecEvaluationSummaryRead:
    rows = session.exec(select(AISpecEvaluation).where(AISpecEvaluation.owner_user_id == owner_user_id)).all()
    if not rows:
        return AISpecEvaluationSummaryRead()
    scores = [float(row.ai_score) for row in rows]
    confidences = [float(row.ai_confidence) for row in rows]
    return AISpecEvaluationSummaryRead(
        total_evaluations=len(rows),
        success_count=sum(1 for row in rows if row.evaluation_status == "SUCCESS"),
        fallback_count=sum(1 for row in rows if row.evaluation_status == "FALLBACK"),
        average_ai_score=round(sum(scores) / len(scores), 2),
        average_ai_confidence=round(sum(confidences) / len(confidences), 3),
        low_risk_count=sum(1 for row in rows if row.risk_level == "LOW"),
        medium_risk_count=sum(1 for row in rows if row.risk_level == "MEDIUM"),
        high_risk_count=sum(1 for row in rows if row.risk_level == "HIGH"),
    )
