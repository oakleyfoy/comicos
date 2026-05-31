from __future__ import annotations

from sqlmodel import Session, select

from app.models.grading_intelligence import GradePrediction
from app.models.grading_validation import GradeValidation, GradingDriftEvent, GradingReliabilityMetric
from app.models.grading_validation import GradingValidationExecution
from app.schemas.grading_validation import GradingDriftEventRead, GradingReliabilityMetricRead, GradingValidationExecutionRead
from app.services.grading_validation import AGENT_GRADING_RELIABILITY, run_with_validation_execution


def detect_prediction_drift(session: Session, *, owner_user_id: int) -> GradingDriftEvent | None:
    validations = session.exec(
        select(GradeValidation)
        .where(GradeValidation.owner_user_id == owner_user_id)
        .order_by(GradeValidation.validated_at.desc(), GradeValidation.id.desc())
    ).all()
    if len(validations) < 4:
        return None
    mid = len(validations) // 2
    recent = validations[:mid]
    older = validations[mid:]
    recent_avg = sum(r.variance for r in recent) / len(recent)
    older_avg = sum(r.variance for r in older) / len(older)
    drift_score = round(abs(recent_avg - older_avg), 3)
    if drift_score < 0.05:
        return None
    event = GradingDriftEvent(
        owner_user_id=owner_user_id,
        drift_type="PREDICTION_VARIANCE_DRIFT",
        drift_score=drift_score,
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def detect_confidence_failures(session: Session, *, owner_user_id: int) -> GradingReliabilityMetric | None:
    predictions = session.exec(
        select(GradePrediction).where(GradePrediction.owner_user_id == owner_user_id)
    ).all()
    if not predictions:
        return None
    failures = 0
    for prediction in predictions:
        validation = session.exec(
            select(GradeValidation)
            .where(GradeValidation.prediction_id == prediction.id)
            .order_by(GradeValidation.validated_at.desc(), GradeValidation.id.desc())
        ).first()
        if validation is None:
            continue
        if validation.variance > 1.0 and prediction.confidence_score >= 0.7:
            failures += 1
    if failures == 0:
        return None
    score = round(min(1.0, failures / max(1, len(predictions))), 3)
    metric = GradingReliabilityMetric(
        owner_user_id=owner_user_id,
        reliability_type="CONFIDENCE_CALIBRATION_FAILURE",
        metric_score=score,
    )
    session.add(metric)
    session.commit()
    session.refresh(metric)
    return metric


def detect_prediction_instability(session: Session, *, owner_user_id: int) -> GradingReliabilityMetric | None:
    validations = session.exec(
        select(GradeValidation).where(GradeValidation.owner_user_id == owner_user_id)
    ).all()
    if len(validations) < 3:
        return None
    variances = [v.variance for v in validations]
    mean = sum(variances) / len(variances)
    instability = sum((v - mean) ** 2 for v in variances) / len(variances)
    if instability < 0.01:
        return None
    metric = GradingReliabilityMetric(
        owner_user_id=owner_user_id,
        reliability_type="PREDICTION_INSTABILITY",
        metric_score=round(min(1.0, instability), 3),
    )
    session.add(metric)
    session.commit()
    session.refresh(metric)
    return metric


def measure_system_reliability(session: Session, *, owner_user_id: int) -> GradingReliabilityMetric:
    validations = session.exec(
        select(GradeValidation).where(GradeValidation.owner_user_id == owner_user_id)
    ).all()
    predictions = session.exec(
        select(GradePrediction).where(GradePrediction.owner_user_id == owner_user_id)
    ).all()
    validated_ids = {v.prediction_id for v in validations}
    coverage = len(validated_ids) / len(predictions) if predictions else 0.0
    avg_variance = sum(v.variance for v in validations) / len(validations) if validations else 0.0
    reliability = round(max(0.0, min(1.0, coverage * 0.5 + (1.0 - min(1.0, avg_variance / 2.0)) * 0.5)), 3)
    metric = GradingReliabilityMetric(
        owner_user_id=owner_user_id,
        reliability_type="SYSTEM_RELIABILITY",
        metric_score=reliability,
    )
    session.add(metric)
    session.commit()
    session.refresh(metric)
    return metric


def run_reliability_monitoring(
    session: Session,
    *,
    owner_user_id: int,
) -> tuple[list[GradingDriftEventRead], list[GradingReliabilityMetricRead]]:
    def runner():
        drift_events: list[GradingDriftEventRead] = []
        reliability_metrics: list[GradingReliabilityMetricRead] = []

        drift = detect_prediction_drift(session, owner_user_id=owner_user_id)
        if drift is not None:
            drift_events.append(GradingDriftEventRead.model_validate(drift))

        confidence = detect_confidence_failures(session, owner_user_id=owner_user_id)
        if confidence is not None:
            reliability_metrics.append(GradingReliabilityMetricRead.model_validate(confidence))

        instability = detect_prediction_instability(session, owner_user_id=owner_user_id)
        if instability is not None:
            reliability_metrics.append(GradingReliabilityMetricRead.model_validate(instability))

        system = measure_system_reliability(session, owner_user_id=owner_user_id)
        reliability_metrics.append(GradingReliabilityMetricRead.model_validate(system))

        return drift_events, reliability_metrics

    result, execution = run_with_validation_execution(
        session, owner_user_id=owner_user_id, agent_code=AGENT_GRADING_RELIABILITY, runner=runner
    )
    assert isinstance(execution, GradingValidationExecution)
    drift_events, reliability_metrics = result
    return drift_events, reliability_metrics, GradingValidationExecutionRead.model_validate(execution)


def list_drift_events_for_owner(session: Session, *, owner_user_id: int, limit: int = 50, offset: int = 0):
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = session.exec(
        select(GradingDriftEvent)
        .where(GradingDriftEvent.owner_user_id == owner_user_id)
        .order_by(GradingDriftEvent.detected_at.desc(), GradingDriftEvent.id.desc())
    ).all()
    page = rows[offset : offset + limit]
    return [GradingDriftEventRead.model_validate(row) for row in page], len(rows)


def list_reliability_metrics_for_owner(session: Session, *, owner_user_id: int, limit: int = 50, offset: int = 0):
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = session.exec(
        select(GradingReliabilityMetric)
        .where(GradingReliabilityMetric.owner_user_id == owner_user_id)
        .order_by(GradingReliabilityMetric.measured_at.desc(), GradingReliabilityMetric.id.desc())
    ).all()
    page = rows[offset : offset + limit]
    return [GradingReliabilityMetricRead.model_validate(row) for row in page], len(rows)
