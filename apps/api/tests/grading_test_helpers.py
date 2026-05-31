from __future__ import annotations

from sqlmodel import Session

from app.models.condition_intelligence import ScanAnalysis
from app.services.condition_intelligence import create_scan_analysis
from app.services.condition_profile_agent import build_condition_profile
from app.services.defect_detection_agent import detect_condition_defects
from app.services.scan_quality_agent import analyze_scan_quality
from app.services.subgrade_agent import generate_subgrades
from app.services.grade_prediction_agent import predict_grade
from app.services.grade_validation_agent import validate_predictions
from app.services.grading_calibration_agent import calculate_calibration_metrics
from app.services.grading_intelligence_roi import run_grading_roi_agent
from app.services.grading_recommendation_agent import run_grading_recommendation_agent
from app.services.grading_reliability_agent import run_reliability_monitoring
from test_scan_quality_agent import _seed_scan_image


def seed_analysis_with_condition_pipeline(session: Session, *, owner_user_id: int) -> ScanAnalysis:
    image = _seed_scan_image(session, owner_user_id=owner_user_id)
    analysis_read = create_scan_analysis(session, owner_user_id=owner_user_id, front_image_id=int(image.id))
    analysis = session.get(ScanAnalysis, analysis_read.id)
    assert analysis is not None
    analyze_scan_quality(session, analysis=analysis)
    session.refresh(analysis)
    detect_condition_defects(session, analysis=analysis)
    session.refresh(analysis)
    build_condition_profile(session, analysis=analysis)
    session.refresh(analysis)
    generate_subgrades(session, analysis=analysis)
    session.refresh(analysis)
    return analysis


def seed_full_grading_platform_stack(session: Session, *, owner_user_id: int) -> int:
    analysis = seed_analysis_with_condition_pipeline(session, owner_user_id=owner_user_id)
    analysis_id = int(analysis.id)
    detail = predict_grade(session, owner_user_id=owner_user_id, analysis_id=analysis_id)
    run_grading_recommendation_agent(session, owner_user_id=owner_user_id, analysis_id=analysis_id)
    run_grading_roi_agent(session, owner_user_id=owner_user_id, analysis_id=analysis_id)
    validate_predictions(
        session,
        owner_user_id=owner_user_id,
        actual_grades=[(detail.prediction.id, detail.prediction.predicted_grade)],
    )
    calculate_calibration_metrics(session, owner_user_id=owner_user_id)
    run_reliability_monitoring(session, owner_user_id=owner_user_id)
    return analysis_id
