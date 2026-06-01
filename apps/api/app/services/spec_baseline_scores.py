from __future__ import annotations

from sqlmodel import Session, select

from app.models.spec_baseline_score import SpecBaselineScore
from app.models.spec_input import SpecInput
from app.schemas.spec_baseline_score import (
    SpecBaselineScoreLatestRead,
    SpecBaselineScoreRead,
    SpecBaselineScoreSummaryRead,
)
from app.services.spec_baseline_engine import generate_spec_baseline_scores


def _to_read(row: SpecBaselineScore, *, spec_input: SpecInput | None) -> SpecBaselineScoreRead:
    return SpecBaselineScoreRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        spec_input_id=int(row.spec_input_id),
        release_id=int(spec_input.release_id) if spec_input and spec_input.release_id is not None else None,
        title=spec_input.title if spec_input else "",
        publisher=spec_input.publisher if spec_input else "",
        series_name=spec_input.series_name if spec_input else "",
        issue_number=spec_input.issue_number if spec_input else "",
        baseline_score=float(row.baseline_score),
        confidence_score=float(row.confidence_score),
        risk_score=float(row.risk_score),
        rationale=row.rationale,
        created_at=row.created_at.isoformat(),
    )


def _input_map(session: Session, *, owner_user_id: int) -> dict[int, SpecInput]:
    rows = session.exec(select(SpecInput).where(SpecInput.owner_user_id == owner_user_id)).all()
    return {int(row.id or 0): row for row in rows if row.id is not None}


def list_spec_baseline_scores(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[SpecBaselineScoreRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    inputs = _input_map(session, owner_user_id=owner_user_id)
    rows = session.exec(
        select(SpecBaselineScore)
        .where(SpecBaselineScore.owner_user_id == owner_user_id)
        .order_by(SpecBaselineScore.baseline_score.desc(), SpecBaselineScore.id.desc())
    ).all()
    total = len(rows)
    page = rows[offset : offset + limit]
    return [_to_read(row, spec_input=inputs.get(int(row.spec_input_id))) for row in page], total


def get_latest_spec_baseline_scores_read(session: Session, *, owner_user_id: int) -> SpecBaselineScoreLatestRead:
    items, _ = list_spec_baseline_scores(session, owner_user_id=owner_user_id, limit=200, offset=0)
    return SpecBaselineScoreLatestRead(
        scores_computed=0,
        scores_skipped=1,
        scores_updated=0,
        items=items,
    )


def refresh_latest_spec_baseline_scores(session: Session, *, owner_user_id: int) -> SpecBaselineScoreLatestRead:
    gen = generate_spec_baseline_scores(session, owner_user_id=owner_user_id)
    items, _ = list_spec_baseline_scores(session, owner_user_id=owner_user_id, limit=200, offset=0)
    return SpecBaselineScoreLatestRead(
        scores_computed=gen.computed,
        scores_skipped=gen.skipped,
        scores_updated=gen.updated,
        items=items,
    )


def build_spec_baseline_summary(session: Session, *, owner_user_id: int) -> SpecBaselineScoreSummaryRead:
    rows = session.exec(select(SpecBaselineScore).where(SpecBaselineScore.owner_user_id == owner_user_id)).all()
    if not rows:
        return SpecBaselineScoreSummaryRead()
    baselines = [float(row.baseline_score) for row in rows]
    confidences = [float(row.confidence_score) for row in rows]
    risks = [float(row.risk_score) for row in rows]
    return SpecBaselineScoreSummaryRead(
        total_scores=len(rows),
        average_baseline_score=round(sum(baselines) / len(baselines), 2),
        average_confidence_score=round(sum(confidences) / len(confidences), 3),
        average_risk_score=round(sum(risks) / len(risks), 2),
        high_baseline_count=sum(1 for value in baselines if value >= 70.0),
    )
