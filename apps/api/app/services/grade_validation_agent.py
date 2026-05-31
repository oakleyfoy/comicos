from __future__ import annotations

from datetime import date

from sqlmodel import Session, select

from app.models.grading_intelligence import GradePrediction
from app.models.grading_validation import GradeCalibrationMetric, GradeValidation
from app.models.grading_validation import GradingValidationExecution
from app.schemas.grading_validation import (
    GradeCalibrationMetricRead,
    GradingValidationExecutionRead,
    GradeValidationRead,
)
from app.services.grading_validation import AGENT_GRADE_VALIDATION, run_with_validation_execution


def _grade_numeric(grade: str) -> float:
    try:
        return float(grade)
    except ValueError:
        return 0.0


def calculate_variance(*, predicted_grade: str, actual_grade: str) -> float:
    return round(abs(_grade_numeric(predicted_grade) - _grade_numeric(actual_grade)), 3)


def calculate_prediction_accuracy(*, variances: list[float]) -> float:
    if not variances:
        return 0.0
    average_variance = sum(variances) / len(variances)
    return round(max(0.0, min(1.0, 1.0 - average_variance / 2.0)), 3)


def _build_calibration_metric(
    session: Session,
    *,
    owner_user_id: int,
    grading_scale: str,
    variances: list[float],
) -> GradeCalibrationMetric:
    metric = GradeCalibrationMetric(
        owner_user_id=owner_user_id,
        metric_date=date.today(),
        grading_scale=grading_scale,
        total_predictions=len(variances),
        average_variance=round(sum(variances) / len(variances), 3) if variances else 0.0,
        accuracy_score=calculate_prediction_accuracy(variances=variances),
    )
    session.add(metric)
    session.commit()
    session.refresh(metric)
    return metric


def validate_predictions(
    session: Session,
    *,
    owner_user_id: int,
    actual_grades: list[tuple[int, str]],
) -> tuple[list[GradeValidationRead], GradeCalibrationMetricRead | None]:
    def runner():
        validations: list[GradeValidation] = []
        by_scale: dict[str, list[float]] = {}
        for prediction_id, actual_grade in actual_grades:
            prediction = session.get(GradePrediction, prediction_id)
            if prediction is None or prediction.owner_user_id != owner_user_id:
                continue
            variance = calculate_variance(
                predicted_grade=prediction.predicted_grade,
                actual_grade=actual_grade,
            )
            row = GradeValidation(
                owner_user_id=owner_user_id,
                prediction_id=prediction_id,
                actual_grade=actual_grade,
                predicted_grade=prediction.predicted_grade,
                variance=variance,
            )
            session.add(row)
            validations.append(row)
            by_scale.setdefault(prediction.grading_scale, []).append(variance)
        session.commit()
        for row in validations:
            session.refresh(row)
        calibration: GradeCalibrationMetric | None = None
        if by_scale:
            scale, variances = next(iter(by_scale.items()))
            if len(by_scale) > 1:
                all_variances = [v for group in by_scale.values() for v in group]
                calibration = _build_calibration_metric(
                    session,
                    owner_user_id=owner_user_id,
                    grading_scale="MIXED",
                    variances=all_variances,
                )
            else:
                calibration = _build_calibration_metric(
                    session,
                    owner_user_id=owner_user_id,
                    grading_scale=scale,
                    variances=variances,
                )
        return (
            [GradeValidationRead.model_validate(v) for v in validations],
            GradeCalibrationMetricRead.model_validate(calibration) if calibration else None,
        )

    result, execution = run_with_validation_execution(
        session, owner_user_id=owner_user_id, agent_code=AGENT_GRADE_VALIDATION, runner=runner
    )
    assert isinstance(execution, GradingValidationExecution)
    return (*result, GradingValidationExecutionRead.model_validate(execution))


def list_validations_for_owner(session: Session, *, owner_user_id: int, limit: int = 50, offset: int = 0):
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = session.exec(
        select(GradeValidation)
        .where(GradeValidation.owner_user_id == owner_user_id)
        .order_by(GradeValidation.validated_at.desc(), GradeValidation.id.desc())
    ).all()
    page = rows[offset : offset + limit]
    return [GradeValidationRead.model_validate(row) for row in page], len(rows)
