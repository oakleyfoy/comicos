from __future__ import annotations

from sqlmodel import Session, select

from app.models.condition_intelligence import ScanQualityAssessment
from app.models.grading_intelligence import GradePrediction, GradingRecommendation
from app.schemas.grading_intelligence import GradingRecommendationRead
from app.services.condition_intelligence import get_analysis_for_owner
from app.services.grading_intelligence import AGENT_GRADING_RECOMMENDATION, run_with_grading_execution


def _create_recommendation(
    session: Session,
    *,
    owner_user_id: int,
    prediction: GradePrediction,
    recommendation_type: str,
    title: str,
    description: str,
    confidence_score: float,
    priority_score: float,
) -> GradingRecommendationRead:
    row = GradingRecommendation(
        owner_user_id=owner_user_id,
        prediction_id=int(prediction.id),
        inventory_copy_id=prediction.inventory_copy_id,
        recommendation_type=recommendation_type,
        title=title,
        description=description,
        confidence_score=round(confidence_score, 3),
        priority_score=round(priority_score, 3),
        recommendation_status="OPEN",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return GradingRecommendationRead.model_validate(row)


def generate_grading_recommendations(
    session: Session,
    *,
    owner_user_id: int,
    analysis_id: int,
) -> list[GradingRecommendationRead]:
    analysis = get_analysis_for_owner(session, analysis_id=analysis_id, owner_user_id=owner_user_id)
    prediction = session.exec(
        select(GradePrediction)
        .where(GradePrediction.analysis_id == analysis.id)
        .order_by(GradePrediction.created_at.desc(), GradePrediction.id.desc())
    ).first()
    if prediction is None:
        raise ValueError("Grade prediction required before recommendations.")

    quality = session.exec(
        select(ScanQualityAssessment)
        .where(ScanQualityAssessment.analysis_id == analysis.id)
        .order_by(ScanQualityAssessment.created_at.desc(), ScanQualityAssessment.id.desc())
    ).first()

    recommendations: list[GradingRecommendationRead] = []
    conf = float(prediction.confidence_score)
    grade_val = float(prediction.predicted_grade)

    if quality and quality.quality_status == "FAIL":
        recommendations.append(
            _create_recommendation(
                session,
                owner_user_id=owner_user_id,
                prediction=prediction,
                recommendation_type="RESCAN_NEEDED",
                title="Rescan before grading",
                description="Scan quality failed validation; capture a higher-quality scan before grading submission.",
                confidence_score=0.9,
                priority_score=0.95,
            )
        )
        return recommendations

    if conf < 0.55:
        recommendations.append(
            _create_recommendation(
                session,
                owner_user_id=owner_user_id,
                prediction=prediction,
                recommendation_type="REVIEW_MANUALLY",
                title="Manual grading review advised",
                description="Prediction confidence is below the advisory threshold; human review recommended.",
                confidence_score=conf,
                priority_score=0.7,
            )
        )

    if grade_val >= 9.0 and conf >= 0.65:
        recommendations.append(
            _create_recommendation(
                session,
                owner_user_id=owner_user_id,
                prediction=prediction,
                recommendation_type="GRADE",
                title="Advisory grade candidate",
                description=(
                    f"Condition intelligence suggests PSA {prediction.predicted_grade} "
                    f"(range {prediction.grade_floor}-{prediction.grade_ceiling}). Submission remains manual."
                ),
                confidence_score=conf,
                priority_score=min(0.99, conf + grade_val / 100.0),
            )
        )
    elif grade_val < 8.0:
        recommendations.append(
            _create_recommendation(
                session,
                owner_user_id=owner_user_id,
                prediction=prediction,
                recommendation_type="DO_NOT_GRADE",
                title="Grading likely poor ROI",
                description="Predicted grade is below typical submission thresholds; hold or sell raw.",
                confidence_score=conf,
                priority_score=0.4,
            )
        )
    else:
        recommendations.append(
            _create_recommendation(
                session,
                owner_user_id=owner_user_id,
                prediction=prediction,
                recommendation_type="PRESS_CLEAN_FIRST",
                title="Press or clean before grading",
                description="Mid-tier prediction; surface prep may improve subgrades before manual submission review.",
                confidence_score=conf,
                priority_score=0.55,
            )
        )

    return recommendations


def run_grading_recommendation_agent(
    session: Session,
    *,
    owner_user_id: int,
    analysis_id: int,
) -> list[GradingRecommendationRead]:
    def _run() -> list[GradingRecommendationRead]:
        return generate_grading_recommendations(session, owner_user_id=owner_user_id, analysis_id=analysis_id)

    result, _ = run_with_grading_execution(
        session,
        owner_user_id=owner_user_id,
        agent_code=AGENT_GRADING_RECOMMENDATION,
        analysis_id=analysis_id,
        runner=_run,
    )
    return result
