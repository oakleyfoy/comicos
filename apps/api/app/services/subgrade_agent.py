from __future__ import annotations

from sqlmodel import Session, select

from app.models.condition_intelligence import ConditionDefect, ConditionProfile, ConditionSubgrade, ScanAnalysis, ScanQualityAssessment
from app.schemas.condition_intelligence import ConditionSubgradeRead
from app.services.condition_intelligence import AGENT_SUBGRADE, run_with_execution

SUBGRADE_TYPES = ("CENTERING", "CORNERS", "EDGES", "SURFACE")


def _score_from_signals(base: float, penalty: float) -> float:
    return max(0.0, min(100.0, round(base - penalty, 2)))


def generate_subgrades(session: Session, *, analysis: ScanAnalysis) -> list[ConditionSubgradeRead]:
    profile = session.exec(
        select(ConditionProfile)
        .where(ConditionProfile.analysis_id == analysis.id)
        .order_by(ConditionProfile.created_at.desc(), ConditionProfile.id.desc())
    ).first()
    quality = session.exec(
        select(ScanQualityAssessment)
        .where(ScanQualityAssessment.analysis_id == analysis.id)
        .order_by(ScanQualityAssessment.created_at.desc(), ScanQualityAssessment.id.desc())
    ).first()
    defects = session.exec(select(ConditionDefect).where(ConditionDefect.analysis_id == analysis.id)).all()

    base = profile.overall_condition_score if profile else (quality.image_quality_score if quality else 70.0)
    corner_penalty = sum(6.0 for d in defects if d.defect_type == "CORNER_WEAR")
    edge_penalty = sum(5.0 for d in defects if d.defect_type == "EDGE_WEAR")
    surface_penalty = sum(7.0 for d in defects if d.defect_type in {"SURFACE_DEFECT", "SCRATCH", "STAIN", "CREASE"})
    centering_penalty = 4.0 if quality and quality.alignment_score < 75.0 else 0.0

    specs = [
        ("CENTERING", _score_from_signals(base, centering_penalty), 0.7 if quality else 0.55),
        ("CORNERS", _score_from_signals(base, corner_penalty), 0.72),
        ("EDGES", _score_from_signals(base, edge_penalty), 0.7),
        ("SURFACE", _score_from_signals(base, surface_penalty), 0.74),
    ]

    created: list[ConditionSubgradeRead] = []
    for subgrade_type, score, confidence in specs:
        if subgrade_type not in SUBGRADE_TYPES:
            continue
        row = ConditionSubgrade(
            analysis_id=int(analysis.id),
            subgrade_type=subgrade_type,
            score=score,
            confidence_score=round(confidence, 3),
        )
        session.add(row)
        created.append(row)
    analysis.analysis_status = "SUBGRADED"
    session.add(analysis)
    session.commit()
    for row in created:
        session.refresh(row)
    return [ConditionSubgradeRead.model_validate(row) for row in created]


def run_subgrade_agent(session: Session, *, analysis: ScanAnalysis) -> list[ConditionSubgradeRead]:
    def _run() -> list[ConditionSubgradeRead]:
        return generate_subgrades(session, analysis=analysis)

    result, _ = run_with_execution(session, analysis_id=int(analysis.id), agent_code=AGENT_SUBGRADE, runner=_run)
    return result
