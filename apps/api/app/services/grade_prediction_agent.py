from __future__ import annotations

from sqlmodel import Session, select

from app.models.condition_intelligence import (
    ConditionDefect,
    ConditionProfile,
    ConditionSubgrade,
    ScanAnalysis,
    ScanQualityAssessment,
)
from app.models.grading_intelligence import GradePrediction, GradePredictionEvidence
from app.schemas.grading_intelligence import GradePredictionDetail, GradePredictionEvidenceRead, GradePredictionRead
from app.services.condition_intelligence import get_analysis_for_owner
from app.services.grading_intelligence import AGENT_GRADE_PREDICTION, run_with_grading_execution

PSA_SCALE = "PSA"


def _score_to_psa_grade(score: float) -> str:
    if score >= 97:
        return "10"
    if score >= 95:
        return "9.8"
    if score >= 92:
        return "9.6"
    if score >= 88:
        return "9.4"
    if score >= 84:
        return "9.2"
    if score >= 80:
        return "9.0"
    if score >= 75:
        return "8.5"
    if score >= 70:
        return "8.0"
    if score >= 60:
        return "7.0"
    return "6.0"


def _grade_numeric(grade: str) -> float:
    try:
        return float(grade)
    except ValueError:
        return 6.0


def predict_grade_range(*, predicted_grade: str, condition_score: float, defect_count: int) -> tuple[str, str]:
    center = _grade_numeric(predicted_grade)
    spread = 0.4 + min(defect_count, 5) * 0.1
    if condition_score < 70:
        spread += 0.3
    floor_val = max(1.0, round(center - spread, 1))
    ceiling_val = min(10.0, round(center + spread * 0.5, 1))
    return str(floor_val), str(ceiling_val)


def calculate_grade_confidence(
    *,
    profile_confidence: float,
    quality_score: float | None,
    subgrade_count: int,
    defect_count: int,
) -> float:
    base = profile_confidence * 0.5
    if quality_score is not None:
        base += (quality_score / 100.0) * 0.25
    base += min(subgrade_count, 4) * 0.05
    base -= min(defect_count, 8) * 0.02
    return round(max(0.1, min(0.98, base)), 3)


def attach_prediction_evidence(
    session: Session,
    *,
    prediction_id: int,
    evidence_type: str,
    payload: dict,
    evidence_score: float,
) -> GradePredictionEvidenceRead:
    row = GradePredictionEvidence(
        prediction_id=prediction_id,
        evidence_type=evidence_type,
        evidence_payload_json=payload,
        evidence_score=round(evidence_score, 3),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return GradePredictionEvidenceRead.model_validate(row)


def predict_grade(session: Session, *, owner_user_id: int, analysis_id: int) -> GradePredictionDetail:
    analysis = get_analysis_for_owner(session, analysis_id=analysis_id, owner_user_id=owner_user_id)
    profile = session.exec(
        select(ConditionProfile)
        .where(ConditionProfile.analysis_id == analysis.id)
        .order_by(ConditionProfile.created_at.desc(), ConditionProfile.id.desc())
    ).first()
    if profile is None:
        raise ValueError("Condition profile required before grade prediction.")

    quality = session.exec(
        select(ScanQualityAssessment)
        .where(ScanQualityAssessment.analysis_id == analysis.id)
        .order_by(ScanQualityAssessment.created_at.desc(), ScanQualityAssessment.id.desc())
    ).first()
    subgrades = session.exec(select(ConditionSubgrade).where(ConditionSubgrade.analysis_id == analysis.id)).all()
    defects = session.exec(select(ConditionDefect).where(ConditionDefect.analysis_id == analysis.id)).all()

    condition_score = float(profile.overall_condition_score)
    predicted = _score_to_psa_grade(condition_score)
    grade_floor, grade_ceiling = predict_grade_range(
        predicted_grade=predicted,
        condition_score=condition_score,
        defect_count=len(defects),
    )
    confidence = calculate_grade_confidence(
        profile_confidence=float(profile.confidence_score),
        quality_score=float(quality.image_quality_score) if quality else None,
        subgrade_count=len(subgrades),
        defect_count=len(defects),
    )

    row = GradePrediction(
        owner_user_id=owner_user_id,
        analysis_id=int(analysis.id),
        inventory_copy_id=analysis.inventory_copy_id,
        grading_scale=PSA_SCALE,
        predicted_grade=predicted,
        grade_floor=grade_floor,
        grade_ceiling=grade_ceiling,
        confidence_score=confidence,
    )
    session.add(row)
    session.commit()
    session.refresh(row)

    evidence: list[GradePredictionEvidenceRead] = []
    evidence.append(
        attach_prediction_evidence(
            session,
            prediction_id=int(row.id),
            evidence_type="condition_profile",
            payload={"overall_condition_score": condition_score, "confidence_score": float(profile.confidence_score)},
            evidence_score=float(profile.confidence_score),
        )
    )
    if quality:
        evidence.append(
            attach_prediction_evidence(
                session,
                prediction_id=int(row.id),
                evidence_type="scan_quality",
                payload={"quality_status": quality.quality_status, "image_quality_score": quality.image_quality_score},
                evidence_score=quality.image_quality_score / 100.0,
            )
        )
    for sub in subgrades[:4]:
        evidence.append(
            attach_prediction_evidence(
                session,
                prediction_id=int(row.id),
                evidence_type="subgrade",
                payload={"subgrade_type": sub.subgrade_type, "score": sub.score},
                evidence_score=float(sub.confidence_score),
            )
        )
    for defect in defects[:6]:
        evidence.append(
            attach_prediction_evidence(
                session,
                prediction_id=int(row.id),
                evidence_type="defect",
                payload={
                    "defect_type": defect.defect_type,
                    "defect_severity": defect.defect_severity,
                    "defect_location": defect.defect_location,
                },
                evidence_score=float(defect.confidence_score),
            )
        )

    return GradePredictionDetail(prediction=GradePredictionRead.model_validate(row), evidence=evidence)


def run_grade_prediction_agent(session: Session, *, owner_user_id: int, analysis_id: int) -> GradePredictionDetail:
    def _run() -> GradePredictionDetail:
        return predict_grade(session, owner_user_id=owner_user_id, analysis_id=analysis_id)

    result, _ = run_with_grading_execution(
        session,
        owner_user_id=owner_user_id,
        agent_code=AGENT_GRADE_PREDICTION,
        analysis_id=analysis_id,
        runner=_run,
    )
    return result
