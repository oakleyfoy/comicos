from __future__ import annotations

from datetime import date

from sqlmodel import Session, select

from app.models.grading_intelligence import GradePrediction
from app.models.grading_validation import GradeCalibrationMetric, GradeValidation
from app.schemas.grading_validation import GradeCalibrationMetricRead, GradingValidationExecutionRead
from app.models.grading_validation import GradingValidationExecution
from app.services.grade_validation_agent import calculate_prediction_accuracy
from app.services.grading_validation import AGENT_GRADING_CALIBRATION, run_with_validation_execution


def evaluate_grade_bias(*, predicted: list[float], actual: list[float]) -> float:
    if not predicted or not actual or len(predicted) != len(actual):
        return 0.0
    deltas = [p - a for p, a in zip(predicted, actual, strict=True)]
    return round(sum(deltas) / len(deltas), 3)


def evaluate_prediction_spread(*, variances: list[float]) -> float:
    if len(variances) < 2:
        return 0.0
    mean = sum(variances) / len(variances)
    spread = sum((v - mean) ** 2 for v in variances) / len(variances)
    return round(spread ** 0.5, 3)


def calculate_calibration_metrics(
    session: Session, *, owner_user_id: int
) -> tuple[list[GradeCalibrationMetricRead], GradingValidationExecutionRead]:
    def runner():
        validations = session.exec(
            select(GradeValidation).where(GradeValidation.owner_user_id == owner_user_id)
        ).all()
        by_scale: dict[str, list[GradeValidation]] = {}
        for row in validations:
            pred = session.get(GradePrediction, row.prediction_id)
            scale = pred.grading_scale if pred else "UNKNOWN"
            by_scale.setdefault(scale, []).append(row)

        metrics: list[GradeCalibrationMetric] = []
        for scale, rows in by_scale.items():
            variances = [r.variance for r in rows]
            predicted = [float(r.predicted_grade) for r in rows if _numeric(r.predicted_grade) is not None]
            actual = [float(r.actual_grade) for r in rows if _numeric(r.actual_grade) is not None]
            bias = abs(evaluate_grade_bias(predicted=predicted, actual=actual))
            spread = evaluate_prediction_spread(variances=variances)
            accuracy = calculate_prediction_accuracy(variances=variances)
            adjusted = round(max(0.0, min(1.0, accuracy - bias * 0.05 - spread * 0.02)), 3)
            metric = GradeCalibrationMetric(
                owner_user_id=owner_user_id,
                metric_date=date.today(),
                grading_scale=scale,
                total_predictions=len(rows),
                average_variance=round(sum(variances) / len(variances), 3) if variances else 0.0,
                accuracy_score=adjusted,
            )
            session.add(metric)
            metrics.append(metric)
        session.commit()
        for metric in metrics:
            session.refresh(metric)
        return [GradeCalibrationMetricRead.model_validate(m) for m in metrics]

    result, execution = run_with_validation_execution(
        session, owner_user_id=owner_user_id, agent_code=AGENT_GRADING_CALIBRATION, runner=runner
    )
    assert isinstance(execution, GradingValidationExecution)
    return result, GradingValidationExecutionRead.model_validate(execution)


def _numeric(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def list_calibration_metrics_for_owner(session: Session, *, owner_user_id: int, limit: int = 50, offset: int = 0):
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = session.exec(
        select(GradeCalibrationMetric)
        .where(GradeCalibrationMetric.owner_user_id == owner_user_id)
        .order_by(GradeCalibrationMetric.created_at.desc(), GradeCalibrationMetric.id.desc())
    ).all()
    page = rows[offset : offset + limit]
    return [GradeCalibrationMetricRead.model_validate(row) for row in page], len(rows)
