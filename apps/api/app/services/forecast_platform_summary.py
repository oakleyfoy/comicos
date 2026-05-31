from __future__ import annotations

from sqlmodel import Session, select

from app.models.dealer_copilot import DealerRecommendation
from app.models.market_forecast import MarketForecast, MarketRiskAssessment
from app.models.market_intelligence import MarketSnapshot
from app.schemas.forecast_platform import ForecastPlatformCertificationRead, ForecastPlatformDashboardRead, ForecastPlatformSummaryRead
from app.services.dealer_copilot_engine import list_recommendations
from app.services.forecast_platform_health import get_forecast_platform_health
from app.services.forecast_platform_validation import validate_forecast_platform
from app.services.forecast_validation_dashboard import (
    build_validation_summary,
    list_accuracy_metrics,
    list_outcomes,
    list_signal_quality_metrics,
)
from app.services.forecast_dashboard import (
    list_highest_risk_assets,
    list_top_bearish_forecasts,
    list_top_bullish_forecasts,
)


def get_forecast_platform_summary(session: Session, *, owner_user_id: int) -> ForecastPlatformSummaryRead:
    latest_snapshot = session.exec(
        select(MarketSnapshot)
        .where(MarketSnapshot.owner_user_id == owner_user_id)
        .order_by(MarketSnapshot.created_at.desc(), MarketSnapshot.id.desc())
    ).first()
    market_score = float(latest_snapshot.market_score) if latest_snapshot is not None else 0.0
    forecast_count = len(session.exec(select(MarketForecast).where(MarketForecast.owner_user_id == owner_user_id)).all())
    risk_count = len(session.exec(select(MarketRiskAssessment).where(MarketRiskAssessment.owner_user_id == owner_user_id)).all())
    recommendation_count = len(session.exec(select(DealerRecommendation).where(DealerRecommendation.owner_user_id == owner_user_id)).all())
    accuracy_summary = list_accuracy_metrics(session, owner_user_id=owner_user_id, limit=5, offset=0).items
    signal_quality_summary = list_signal_quality_metrics(session, owner_user_id=owner_user_id, limit=5, offset=0).items
    recent_outcomes = list_outcomes(session, owner_user_id=owner_user_id, limit=5, offset=0).items
    average_accuracy = build_validation_summary(session, owner_user_id=owner_user_id).average_accuracy

    return ForecastPlatformSummaryRead(
        market_score=market_score,
        forecast_count=forecast_count,
        risk_count=risk_count,
        recommendation_count=recommendation_count,
        forecast_accuracy=average_accuracy,
        top_bullish_forecasts=list_top_bullish_forecasts(session, owner_user_id=owner_user_id, limit=5),
        top_bearish_forecasts=list_top_bearish_forecasts(session, owner_user_id=owner_user_id, limit=5),
        top_risks=list_highest_risk_assets(session, owner_user_id=owner_user_id, limit=5),
        top_buy_recommendations=list_recommendations(session, owner_user_id=owner_user_id, recommendation_type="BUY", limit=5, offset=0).items,
        top_sell_recommendations=list_recommendations(session, owner_user_id=owner_user_id, recommendation_type="SELL", limit=5, offset=0).items,
        top_grade_candidates=list_recommendations(session, owner_user_id=owner_user_id, recommendation_type="GRADE", limit=5, offset=0).items,
        accuracy_summary=accuracy_summary,
        signal_quality_summary=signal_quality_summary,
        recent_outcomes=recent_outcomes,
    )


def get_forecast_platform_certification(session: Session, *, owner_user_id: int) -> ForecastPlatformCertificationRead:
    validation = validate_forecast_platform(session, owner_user_id=owner_user_id)
    health = get_forecast_platform_health(session, owner_user_id=owner_user_id)
    certified = validation.platform_certified and health.overall_status in {"HEALTHY", "WARNING"}
    notes: list[str] = []
    if validation.overall_status != "PASS":
        notes.append("Validation checks must all pass for full certification.")
    if health.overall_status == "FAILED":
        notes.append("One or more health components are currently failed.")
    if health.overall_status == "DISABLED":
        notes.append("No active decision-intelligence activity is visible yet.")
    if certified and not notes:
        notes.append("Forecast platform passed closeout validation and is certified for the P47 decision-intelligence layer.")
    return ForecastPlatformCertificationRead(
        platform_certified=certified,
        validation_status=validation.overall_status,
        health_status=health.overall_status,
        summary="Certified" if certified else "Not certified",
        certification_notes=notes,
    )


def get_forecast_platform_dashboard(session: Session, *, owner_user_id: int) -> ForecastPlatformDashboardRead:
    return ForecastPlatformDashboardRead(
        summary=get_forecast_platform_summary(session, owner_user_id=owner_user_id),
        health=get_forecast_platform_health(session, owner_user_id=owner_user_id),
        validation=validate_forecast_platform(session, owner_user_id=owner_user_id),
        certification=get_forecast_platform_certification(session, owner_user_id=owner_user_id),
    )
