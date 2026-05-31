from __future__ import annotations

from sqlmodel import Session

from app.models import ScanImage
from app.models.condition_intelligence import ScanAnalysis, ScanQualityAssessment
from app.schemas.condition_intelligence import ScanQualityAssessmentRead
from app.services.condition_intelligence import AGENT_SCAN_QUALITY, run_with_execution


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, round(value, 2)))


def evaluate_resolution(image: ScanImage | None) -> float:
    if image is None or not image.width or not image.height:
        return 40.0
    megapixels = (image.width * image.height) / 1_000_000
    if megapixels >= 12:
        return 100.0
    if megapixels >= 8:
        return 85.0
    if megapixels >= 4:
        return 70.0
    if megapixels >= 2:
        return 55.0
    return 35.0


def evaluate_alignment(image: ScanImage | None) -> float:
    if image is None:
        return 50.0
    if image.normalized_dpi_x and image.normalized_dpi_y:
        return 92.0
    if image.processing_status == "NORMALIZED":
        return 88.0
    return 72.0


def evaluate_glare(image: ScanImage | None) -> float:
    if image is None:
        return 60.0
    if image.color_mode and image.color_mode.upper() == "REFLECTIVE":
        return 55.0
    return 85.0


def evaluate_crop(image: ScanImage | None) -> float:
    if image is None or not image.width or not image.height:
        return 45.0
    ratio = image.width / max(image.height, 1)
    if 0.62 <= ratio <= 0.72:
        return 95.0
    if 0.55 <= ratio <= 0.8:
        return 78.0
    return 62.0


def _quality_status(score: float) -> str:
    if score >= 85.0:
        return "PASS"
    if score >= 65.0:
        return "WARNING"
    return "FAIL"


def analyze_scan_quality(session: Session, *, analysis: ScanAnalysis) -> ScanQualityAssessmentRead:
    front = session.get(ScanImage, analysis.front_image_id) if analysis.front_image_id else None
    back = session.get(ScanImage, analysis.back_image_id) if analysis.back_image_id else None
    primary = front or back

    resolution = evaluate_resolution(primary)
    alignment = evaluate_alignment(primary)
    glare = evaluate_glare(primary)
    crop = evaluate_crop(primary)
    image_quality = _clamp((resolution + alignment + glare + crop) / 4.0)

    row = ScanQualityAssessment(
        analysis_id=int(analysis.id),
        image_quality_score=image_quality,
        resolution_score=_clamp(resolution),
        alignment_score=_clamp(alignment),
        glare_score=_clamp(glare),
        crop_score=_clamp(crop),
        quality_status=_quality_status(image_quality),
    )
    session.add(row)
    analysis.analysis_status = "QUALITY_ANALYZED"
    session.add(analysis)
    session.commit()
    session.refresh(row)
    return ScanQualityAssessmentRead.model_validate(row)


def run_scan_quality_agent(session: Session, *, analysis: ScanAnalysis) -> ScanQualityAssessmentRead:
    def _run() -> ScanQualityAssessmentRead:
        return analyze_scan_quality(session, analysis=analysis)

    result, _ = run_with_execution(session, analysis_id=int(analysis.id), agent_code=AGENT_SCAN_QUALITY, runner=_run)
    return result
