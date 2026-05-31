from __future__ import annotations

from sqlmodel import Session, select

from app.models.dealer_copilot import DealerOpportunityScore, DealerRecommendation, DealerRecommendationEvidence
from app.models.forecast_validation import (
    ForecastAccuracyMetric,
    ForecastDriftEvent,
    ForecastOutcome,
    ForecastValidation,
    SignalQualityMetric,
)
from app.models.market_forecast import MarketForecast, MarketRiskAssessment
from app.models.market_intelligence import MarketObservation, MarketSignal, MarketSnapshot, MarketTrend
from app.schemas.forecast_platform import ForecastPlatformValidationCheckRead, ForecastPlatformValidationRead

PLATFORM_STATUS_PASS = "PASS"
PLATFORM_STATUS_WARNING = "WARNING"
PLATFORM_STATUS_FAIL = "FAIL"


def _aggregate_status(statuses: list[str]) -> str:
    if any(status == PLATFORM_STATUS_FAIL for status in statuses):
        return PLATFORM_STATUS_FAIL
    if any(status == PLATFORM_STATUS_WARNING for status in statuses):
        return PLATFORM_STATUS_WARNING
    return PLATFORM_STATUS_PASS


def _check(
    *,
    check_code: str,
    title: str,
    status: str,
    summary: str,
    details_json: dict[str, object],
) -> ForecastPlatformValidationCheckRead:
    return ForecastPlatformValidationCheckRead(
        check_code=check_code,
        title=title,
        status=status,
        summary=summary,
        details_json=details_json,
    )


def validate_market_intelligence(session: Session, *, owner_user_id: int) -> ForecastPlatformValidationCheckRead:
    signals = session.exec(select(MarketSignal).where(MarketSignal.owner_user_id == owner_user_id)).all()
    snapshots = session.exec(select(MarketSnapshot).where(MarketSnapshot.owner_user_id == owner_user_id)).all()
    trends = session.exec(select(MarketTrend).where(MarketTrend.owner_user_id == owner_user_id)).all()
    observations = session.exec(select(MarketObservation).where(MarketObservation.owner_user_id == owner_user_id)).all()

    status = PLATFORM_STATUS_PASS
    if not signals or not snapshots or not trends:
        status = PLATFORM_STATUS_WARNING
    if signals and any(float(row.confidence_score) < 0.0 or float(row.confidence_score) > 1.0 for row in signals):
        status = PLATFORM_STATUS_FAIL

    return _check(
        check_code="market_intelligence",
        title="Market Intelligence",
        status=status,
        summary=f"{len(signals)} signals, {len(snapshots)} snapshots, {len(trends)} trends, and {len(observations)} observations reviewed.",
        details_json={
            "owner_user_id": owner_user_id,
            "signal_count": len(signals),
            "snapshot_count": len(snapshots),
            "trend_count": len(trends),
            "observation_count": len(observations),
        },
    )


def validate_forecasts(session: Session, *, owner_user_id: int) -> ForecastPlatformValidationCheckRead:
    forecasts = session.exec(select(MarketForecast).where(MarketForecast.owner_user_id == owner_user_id)).all()
    invalid_confidence = [
        int(row.id or 0) for row in forecasts if float(row.confidence_score) < 0.0 or float(row.confidence_score) > 1.0
    ]
    status = PLATFORM_STATUS_PASS
    if invalid_confidence:
        status = PLATFORM_STATUS_FAIL
    elif not forecasts:
        status = PLATFORM_STATUS_WARNING
    return _check(
        check_code="forecasts",
        title="Forecasts",
        status=status,
        summary=f"{len(forecasts)} forecasts validated for confidence and coverage.",
        details_json={
            "owner_user_id": owner_user_id,
            "forecast_count": len(forecasts),
            "invalid_confidence_forecast_ids": invalid_confidence,
        },
    )


def validate_risk_assessments(session: Session, *, owner_user_id: int) -> ForecastPlatformValidationCheckRead:
    risks = session.exec(select(MarketRiskAssessment).where(MarketRiskAssessment.owner_user_id == owner_user_id)).all()
    invalid_scores = [int(row.id or 0) for row in risks if float(row.risk_score) < 0.0]
    status = PLATFORM_STATUS_PASS
    if invalid_scores:
        status = PLATFORM_STATUS_FAIL
    elif not risks:
        status = PLATFORM_STATUS_WARNING
    return _check(
        check_code="risk_assessments",
        title="Risk Assessments",
        status=status,
        summary=f"{len(risks)} risk assessments checked for valid scores.",
        details_json={
            "owner_user_id": owner_user_id,
            "risk_count": len(risks),
            "invalid_risk_ids": invalid_scores,
        },
    )


def validate_dealer_copilot(session: Session, *, owner_user_id: int) -> ForecastPlatformValidationCheckRead:
    recommendations = session.exec(select(DealerRecommendation).where(DealerRecommendation.owner_user_id == owner_user_id)).all()
    opportunities = session.exec(select(DealerOpportunityScore).where(DealerOpportunityScore.owner_user_id == owner_user_id)).all()
    recommendation_ids = [int(row.id or 0) for row in recommendations]
    evidence_rows = (
        session.exec(select(DealerRecommendationEvidence).where(DealerRecommendationEvidence.recommendation_id.in_(recommendation_ids))).all()
        if recommendation_ids
        else []
    )
    evidence_ids = {row.recommendation_id for row in evidence_rows}
    recommendations_without_evidence = sorted(
        rec_id for rec_id in recommendation_ids if rec_id not in evidence_ids
    )
    status = PLATFORM_STATUS_PASS
    if recommendations_without_evidence:
        status = PLATFORM_STATUS_FAIL
    elif not recommendations or not opportunities:
        status = PLATFORM_STATUS_WARNING
    return _check(
        check_code="dealer_copilot",
        title="Dealer Copilot",
        status=status,
        summary=f"{len(recommendations)} recommendations and {len(opportunities)} opportunity scores reviewed.",
        details_json={
            "owner_user_id": owner_user_id,
            "recommendation_count": len(recommendations),
            "opportunity_count": len(opportunities),
            "recommendations_without_evidence": recommendations_without_evidence,
        },
    )


def validate_validation_learning(session: Session, *, owner_user_id: int) -> ForecastPlatformValidationCheckRead:
    validations = session.exec(select(ForecastValidation).where(ForecastValidation.owner_user_id == owner_user_id)).all()
    accuracy = session.exec(select(ForecastAccuracyMetric).where(ForecastAccuracyMetric.owner_user_id == owner_user_id)).all()
    drift = session.exec(select(ForecastDriftEvent).where(ForecastDriftEvent.owner_user_id == owner_user_id)).all()
    signal_quality = session.exec(select(SignalQualityMetric).where(SignalQualityMetric.owner_user_id == owner_user_id)).all()
    outcomes = session.exec(select(ForecastOutcome).where(ForecastOutcome.owner_user_id == owner_user_id)).all()
    status = PLATFORM_STATUS_PASS
    if not validations or not accuracy or not signal_quality:
        status = PLATFORM_STATUS_WARNING
    if signal_quality and any(float(row.quality_score) < 0.0 or float(row.quality_score) > 1.0 for row in signal_quality):
        status = PLATFORM_STATUS_FAIL
    return _check(
        check_code="validation_learning",
        title="Validation and Learning",
        status=status,
        summary=f"{len(validations)} validations, {len(accuracy)} accuracy metrics, {len(drift)} drift events, {len(signal_quality)} signal quality metrics, and {len(outcomes)} outcomes reviewed.",
        details_json={
            "owner_user_id": owner_user_id,
            "validation_count": len(validations),
            "accuracy_metric_count": len(accuracy),
            "drift_event_count": len(drift),
            "signal_quality_count": len(signal_quality),
            "outcome_count": len(outcomes),
        },
    )


def validate_forecast_platform(session: Session, *, owner_user_id: int) -> ForecastPlatformValidationRead:
    checks = [
        validate_market_intelligence(session, owner_user_id=owner_user_id),
        validate_forecasts(session, owner_user_id=owner_user_id),
        validate_risk_assessments(session, owner_user_id=owner_user_id),
        validate_dealer_copilot(session, owner_user_id=owner_user_id),
        validate_validation_learning(session, owner_user_id=owner_user_id),
    ]
    overall = _aggregate_status([check.status for check in checks])
    return ForecastPlatformValidationRead(
        overall_status=overall,
        platform_certified=overall == PLATFORM_STATUS_PASS,
        checks=checks,
    )
