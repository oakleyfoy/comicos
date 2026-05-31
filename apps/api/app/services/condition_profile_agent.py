from __future__ import annotations

from sqlmodel import Session, select

from app.models.condition_intelligence import ConditionDefect, ConditionProfile, ScanAnalysis, ScanQualityAssessment
from app.schemas.condition_intelligence import ConditionProfileRead
from app.services.condition_intelligence import AGENT_CONDITION_PROFILE, run_with_execution

_SEVERITY_PENALTY = {"LOW": 3.0, "MEDIUM": 8.0, "HIGH": 15.0}


def calculate_condition_score(
    *,
    quality_score: float | None,
    defects: list[ConditionDefect],
) -> tuple[float, float]:
    base = quality_score if quality_score is not None else 75.0
    penalty = sum(_SEVERITY_PENALTY.get(defect.defect_severity, 5.0) for defect in defects)
    score = max(0.0, min(100.0, round(base - penalty, 2)))
    if not defects:
        confidence = 0.65
    else:
        confidence = round(min(0.95, 0.55 + sum(d.confidence_score for d in defects) / max(len(defects), 1) * 0.35), 3)
    return score, confidence


def build_condition_profile(session: Session, *, analysis: ScanAnalysis) -> ConditionProfileRead:
    quality = session.exec(
        select(ScanQualityAssessment)
        .where(ScanQualityAssessment.analysis_id == analysis.id)
        .order_by(ScanQualityAssessment.created_at.desc(), ScanQualityAssessment.id.desc())
    ).first()
    defects = session.exec(select(ConditionDefect).where(ConditionDefect.analysis_id == analysis.id)).all()
    quality_score = quality.image_quality_score if quality else None
    overall, confidence = calculate_condition_score(quality_score=quality_score, defects=defects)

    row = ConditionProfile(
        analysis_id=int(analysis.id),
        overall_condition_score=overall,
        confidence_score=confidence,
    )
    session.add(row)
    analysis.analysis_status = "PROFILED"
    session.add(analysis)
    session.commit()
    session.refresh(row)
    return ConditionProfileRead.model_validate(row)


def run_condition_profile_agent(session: Session, *, analysis: ScanAnalysis) -> ConditionProfileRead:
    def _run() -> ConditionProfileRead:
        return build_condition_profile(session, analysis=analysis)

    result, _ = run_with_execution(session, analysis_id=int(analysis.id), agent_code=AGENT_CONDITION_PROFILE, runner=_run)
    return result
