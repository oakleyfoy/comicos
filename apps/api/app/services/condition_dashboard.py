from __future__ import annotations

from sqlmodel import Session, select

from app.models.condition_intelligence import ScanAnalysis
from app.schemas.condition_intelligence import (
    ConditionAgentExecutionRead,
    ConditionDashboardRead,
    ConditionDefectRead,
    ConditionProfileRead,
    ConditionSubgradeRead,
    ScanQualityAssessmentRead,
)
from app.services.condition_intelligence import (
    list_analyses_for_owner,
    list_defects_for_owner,
    list_executions_for_owner,
    list_profiles_for_owner,
    list_quality_for_owner,
    list_subgrades_for_owner,
)


def build_condition_dashboard(session: Session, *, owner_user_id: int) -> ConditionDashboardRead:
    analyses, analysis_count = list_analyses_for_owner(session, owner_user_id=owner_user_id, limit=200, offset=0)
    profiles_raw, profile_count = list_profiles_for_owner(session, owner_user_id=owner_user_id, limit=20, offset=0)
    defects_raw, defect_count = list_defects_for_owner(session, owner_user_id=owner_user_id, limit=20, offset=0)
    subgrades_raw, subgrade_count = list_subgrades_for_owner(session, owner_user_id=owner_user_id, limit=20, offset=0)
    quality_raw, quality_count = list_quality_for_owner(session, owner_user_id=owner_user_id, limit=20, offset=0)
    executions_raw, execution_count = list_executions_for_owner(session, owner_user_id=owner_user_id, limit=20, offset=0)

    profiles = [ConditionProfileRead.model_validate(row) for row in profiles_raw]
    defects = [ConditionDefectRead.model_validate(row) for row in defects_raw]
    subgrades = [ConditionSubgradeRead.model_validate(row) for row in subgrades_raw]
    quality = [ScanQualityAssessmentRead.model_validate(row) for row in quality_raw]
    executions = [ConditionAgentExecutionRead.model_validate(row) for row in executions_raw]

    avg_condition = round(sum(p.overall_condition_score for p in profiles) / len(profiles), 2) if profiles else 0.0
    avg_quality = round(sum(q.image_quality_score for q in quality) / len(quality), 2) if quality else 0.0

    return ConditionDashboardRead(
        analysis_count=analysis_count,
        profile_count=profile_count,
        defect_count=defect_count,
        subgrade_count=subgrade_count,
        quality_assessment_count=quality_count,
        execution_count=execution_count,
        average_condition_score=avg_condition,
        average_quality_score=avg_quality,
        condition_summary=profiles,
        defect_summary=defects,
        subgrade_summary=subgrades,
        scan_quality_summary=quality,
        agent_activity=executions,
    )


def get_analysis_detail(session: Session, *, analysis_id: int, owner_user_id: int):
    from app.schemas.condition_intelligence import ScanAnalysisDetailRead, ScanAnalysisRead

    row = session.exec(
        select(ScanAnalysis).where(ScanAnalysis.id == analysis_id, ScanAnalysis.owner_user_id == owner_user_id)
    ).first()
    if row is None:
        return None
    profiles_raw, _ = list_profiles_for_owner(session, owner_user_id=owner_user_id, limit=200, offset=0)
    defects_raw, _ = list_defects_for_owner(session, owner_user_id=owner_user_id, limit=200, offset=0)
    subgrades_raw, _ = list_subgrades_for_owner(session, owner_user_id=owner_user_id, limit=200, offset=0)
    quality_raw, _ = list_quality_for_owner(session, owner_user_id=owner_user_id, limit=200, offset=0)
    executions_raw, _ = list_executions_for_owner(session, owner_user_id=owner_user_id, limit=200, offset=0)

    return ScanAnalysisDetailRead(
        analysis=ScanAnalysisRead.model_validate(row),
        quality_assessments=[ScanQualityAssessmentRead.model_validate(q) for q in quality_raw if q.analysis_id == analysis_id],
        profiles=[ConditionProfileRead.model_validate(p) for p in profiles_raw if p.analysis_id == analysis_id],
        defects=[ConditionDefectRead.model_validate(d) for d in defects_raw if d.analysis_id == analysis_id],
        subgrades=[ConditionSubgradeRead.model_validate(s) for s in subgrades_raw if s.analysis_id == analysis_id],
        executions=[ConditionAgentExecutionRead.model_validate(e) for e in executions_raw if e.analysis_id == analysis_id],
    )
