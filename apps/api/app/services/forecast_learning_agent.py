from __future__ import annotations

from sqlmodel import Session, select

from app.models.dealer_copilot import DealerOpportunityScore, DealerRecommendation
from app.models.forecast_validation import ForecastOutcome, ForecastValidation, ForecastValidationExecution, utc_now
from app.models.market_forecast import MarketForecast
from app.schemas.forecast_validation import (
    ForecastLearningRunResponse,
    ForecastOutcomeRead,
    ForecastValidationExecutionRead,
)

AGENT_CODE = "forecast_learning_agent"


def _execution_read(row: ForecastValidationExecution) -> ForecastValidationExecutionRead:
    return ForecastValidationExecutionRead.model_validate(row)


def _outcome_read(row: ForecastOutcome) -> ForecastOutcomeRead:
    return ForecastOutcomeRead.model_validate(row)


def _start_execution(session: Session, *, owner_user_id: int) -> ForecastValidationExecution:
    row = ForecastValidationExecution(
        owner_user_id=owner_user_id,
        agent_code=AGENT_CODE,
        status="RUNNING",
        started_at=utc_now(),
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return row


def _finish_execution(session: Session, *, execution: ForecastValidationExecution, status: str) -> None:
    completed_at = utc_now()
    execution.status = status
    execution.completed_at = completed_at
    execution.duration_ms = max(int((completed_at - execution.started_at).total_seconds() * 1000), 0)
    session.add(execution)
    session.flush()


def track_accuracy_improvement(*, accuracy_score: float, confidence_score: float) -> float:
    return round(max(0.0, min(1.0, (accuracy_score * 0.7) + (confidence_score * 0.3))), 4)


def track_confidence_accuracy(*, accuracy_score: float, confidence_score: float) -> float:
    return round(max(0.0, 1.0 - abs(float(confidence_score) - float(accuracy_score))), 4)


def evaluate_forecast_outcomes(session: Session, *, owner_user_id: int) -> list[ForecastOutcome]:
    validations = session.exec(
        select(ForecastValidation)
        .where(ForecastValidation.owner_user_id == owner_user_id)
        .order_by(ForecastValidation.validated_at.desc(), ForecastValidation.id.desc())
    ).all()
    forecasts = {int(row.id or 0): row for row in session.exec(select(MarketForecast).where(MarketForecast.owner_user_id == owner_user_id)).all()}
    created: list[ForecastOutcome] = []
    for validation in validations:
        forecast = forecasts.get(validation.forecast_id)
        if forecast is None:
            continue
        accuracy_score = round(max(0.0, 1.0 - min(abs(float(validation.variance_percent)) / 100.0, 1.0)), 4)
        confidence_alignment = track_confidence_accuracy(
            accuracy_score=accuracy_score,
            confidence_score=float(forecast.confidence_score),
        )
        outcome = ForecastOutcome(
            owner_user_id=owner_user_id,
            forecast_id=validation.forecast_id,
            outcome_type="FORECAST_ACCURACY",
            outcome_score=track_accuracy_improvement(
                accuracy_score=accuracy_score,
                confidence_score=confidence_alignment,
            ),
            created_at=utc_now(),
        )
        session.add(outcome)
        created.append(outcome)
    session.flush()
    return created


def evaluate_recommendation_outcomes(session: Session, *, owner_user_id: int) -> list[ForecastOutcome]:
    recommendations = session.exec(
        select(DealerRecommendation)
        .where(DealerRecommendation.owner_user_id == owner_user_id)
        .where(DealerRecommendation.asset_id.is_not(None))
        .order_by(DealerRecommendation.created_at.desc(), DealerRecommendation.id.desc())
    ).all()
    scores = session.exec(
        select(DealerOpportunityScore)
        .where(DealerOpportunityScore.owner_user_id == owner_user_id)
        .order_by(DealerOpportunityScore.calculated_at.desc(), DealerOpportunityScore.id.desc())
    ).all()
    latest_score_by_asset: dict[tuple[str, int], DealerOpportunityScore] = {}
    for score in scores:
        key = (score.asset_type, score.asset_id)
        if key not in latest_score_by_asset:
            latest_score_by_asset[key] = score

    created: list[ForecastOutcome] = []
    for recommendation in recommendations:
        if recommendation.asset_id is None:
            continue
        score = latest_score_by_asset.get((recommendation.asset_type, int(recommendation.asset_id)))
        if score is None:
            continue
        if recommendation.recommendation_type == "BUY":
            outcome_score = (score.opportunity_score * 0.7) + ((1.0 - score.risk_score) * 0.3)
        elif recommendation.recommendation_type == "SELL":
            outcome_score = (score.risk_score * 0.7) + ((1.0 - score.forecast_score) * 0.3)
        elif recommendation.recommendation_type == "HOLD":
            outcome_score = max(0.0, 1.0 - abs(score.opportunity_score - 0.5))
        elif recommendation.recommendation_type == "GRADE":
            outcome_score = float(score.grading_score or 0.0)
        else:
            outcome_score = (score.demand_score * 0.6) + ((1.0 - score.risk_score) * 0.4)
        row = ForecastOutcome(
            owner_user_id=owner_user_id,
            recommendation_id=int(recommendation.id or 0),
            outcome_type="RECOMMENDATION_OUTCOME",
            outcome_score=round(max(0.0, min(1.0, outcome_score)), 4),
            created_at=utc_now(),
        )
        session.add(row)
        created.append(row)
    session.flush()
    return created


def run_forecast_learning_agent(session: Session, *, owner_user_id: int) -> ForecastLearningRunResponse:
    execution = _start_execution(session, owner_user_id=owner_user_id)
    try:
        outcomes = [
            *evaluate_forecast_outcomes(session, owner_user_id=owner_user_id),
            *evaluate_recommendation_outcomes(session, owner_user_id=owner_user_id),
        ]
        _finish_execution(session, execution=execution, status="COMPLETED")
        session.commit()
        return ForecastLearningRunResponse(
            execution=_execution_read(execution),
            outcomes=[_outcome_read(row) for row in outcomes],
        )
    except Exception:
        _finish_execution(session, execution=execution, status="FAILED")
        session.commit()
        raise
