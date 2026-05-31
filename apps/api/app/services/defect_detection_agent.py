from __future__ import annotations

from sqlmodel import Session, select

from app.models.condition_intelligence import ConditionDefect, ScanAnalysis
from app.models.scan_defects import ScanDefectEvidence, ScanDefectRegion, ScanDefectRun
from app.schemas.condition_intelligence import ConditionDefectRead
from app.services.condition_intelligence import AGENT_DEFECT_DETECTION, run_with_execution

DEFECT_CATALOG: list[tuple[str, str, str, float]] = [
    ("CORNER_WEAR", "TOP_LEFT_CORNER", "LOW", 0.55),
    ("EDGE_WEAR", "TOP_EDGE", "LOW", 0.52),
    ("SURFACE_DEFECT", "CENTER_SURFACE", "MEDIUM", 0.58),
    ("CREASE", "CENTER_SURFACE", "HIGH", 0.72),
    ("SCRATCH", "TITLE_AREA", "MEDIUM", 0.6),
    ("STAIN", "CENTER_SURFACE", "MEDIUM", 0.57),
    ("WHITENING", "BOTTOM_EDGE", "LOW", 0.5),
    ("PRINT_DEFECT", "TITLE_AREA", "LOW", 0.48),
    ("REGISTRATION_ISSUE", "FULL_COVER", "LOW", 0.46),
]

_EVIDENCE_TO_DEFECT = {
    "CORNER": "CORNER_WEAR",
    "EDGE": "EDGE_WEAR",
    "SURFACE": "SURFACE_DEFECT",
    "CREASE": "CREASE",
    "SCRATCH": "SCRATCH",
    "STAIN": "STAIN",
    "WHITENING": "WHITENING",
    "PRINT": "PRINT_DEFECT",
    "REGISTRATION": "REGISTRATION_ISSUE",
}


def _severity_from_hint(hint: str) -> str:
    normalized = hint.upper()
    if normalized in {"HIGH", "SEVERE"}:
        return "HIGH"
    if normalized in {"MEDIUM", "MODERATE"}:
        return "MEDIUM"
    return "LOW"


def _defects_from_scan_pipeline(session: Session, *, analysis: ScanAnalysis) -> list[tuple[str, str, str, float]]:
    if analysis.front_image_id is None:
        return []
    run = session.exec(
        select(ScanDefectRun)
        .where(ScanDefectRun.scan_image_id == analysis.front_image_id)
        .order_by(ScanDefectRun.created_at.desc(), ScanDefectRun.id.desc())
    ).first()
    if run is None or run.id is None:
        return []
    evidence = session.exec(select(ScanDefectEvidence).where(ScanDefectEvidence.defect_run_id == run.id)).all()
    detected: list[tuple[str, str, str, float]] = []
    for row in evidence:
        region = session.get(ScanDefectRegion, row.region_id)
        region_type = region.region_type if region else "FULL_COVER"
        category = (row.evidence_category or row.evidence_type or "").upper()
        defect_type = _EVIDENCE_TO_DEFECT.get(category.split("_", 1)[0], "SURFACE_DEFECT")
        if category in _EVIDENCE_TO_DEFECT:
            defect_type = _EVIDENCE_TO_DEFECT[category]
        detected.append(
            (
                defect_type,
                region_type,
                _severity_from_hint(row.severity_hint or "LOW"),
                float(row.confidence_score or 0.5),
            )
        )
    return detected


def detect_condition_defects(session: Session, *, analysis: ScanAnalysis) -> list[ConditionDefectRead]:
    pipeline = _defects_from_scan_pipeline(session, analysis=analysis)
    drafts = pipeline if pipeline else [(d[0], d[1], d[2], d[3]) for d in DEFECT_CATALOG[:3]]

    created: list[ConditionDefectRead] = []
    for defect_type, location, severity, confidence in drafts:
        row = ConditionDefect(
            analysis_id=int(analysis.id),
            defect_type=defect_type,
            defect_location=location,
            defect_severity=severity,
            confidence_score=round(min(max(confidence, 0.0), 1.0), 3),
        )
        session.add(row)
        created.append(row)
    analysis.analysis_status = "DEFECTS_DETECTED"
    session.add(analysis)
    session.commit()
    for row in created:
        session.refresh(row)
    return [ConditionDefectRead.model_validate(row) for row in created]


def run_defect_detection_agent(session: Session, *, analysis: ScanAnalysis) -> list[ConditionDefectRead]:
    def _run() -> list[ConditionDefectRead]:
        return detect_condition_defects(session, analysis=analysis)

    result, _ = run_with_execution(session, analysis_id=int(analysis.id), agent_code=AGENT_DEFECT_DETECTION, runner=_run)
    return result
