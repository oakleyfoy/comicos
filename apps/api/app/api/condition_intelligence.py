from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.condition_intelligence import (
    ConditionAgentExecutionListResponse,
    ConditionAgentExecutionRead,
    ConditionDefectListResponse,
    ConditionDefectRead,
    ConditionIntelligenceRunRequest,
    ConditionProfileListResponse,
    ConditionProfileRead,
    ConditionProfileRunResponse,
    ConditionQualityRunResponse,
    ConditionSubgradeListResponse,
    ConditionSubgradeRead,
    ConditionSubgradesRunResponse,
    ConditionDefectsRunResponse,
    ScanAnalysisListResponse,
    ScanAnalysisRead,
    ScanQualityAssessmentListResponse,
    ScanQualityAssessmentRead,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.condition_dashboard import build_condition_dashboard, get_analysis_detail
from app.services.condition_intelligence import (
    list_analyses_for_owner,
    list_defects_for_owner,
    list_executions_for_owner,
    list_profiles_for_owner,
    list_quality_for_owner,
    list_subgrades_for_owner,
    resolve_or_create_analysis,
)
from app.services.condition_profile_agent import run_condition_profile_agent
from app.services.defect_detection_agent import run_defect_detection_agent
from app.services.scan_quality_agent import run_scan_quality_agent
from app.services.subgrade_agent import run_subgrade_agent

condition_intelligence_v1_router = APIRouter(prefix="/api/v1", tags=["Condition Intelligence API v1 (P49-01)"])


def attach_condition_intelligence_layer(app: FastAPI) -> None:
    app.include_router(condition_intelligence_v1_router)


@condition_intelligence_v1_router.get("/condition-intelligence/analyses", response_model=ScanApiV1Envelope)
def v1_condition_analyses(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_analyses_for_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    body = ScanAnalysisListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@condition_intelligence_v1_router.get("/condition-intelligence/analyses/{analysis_id}", response_model=ScanApiV1Envelope)
def v1_condition_analysis_detail(
    analysis_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    detail = get_analysis_detail(session, analysis_id=analysis_id, owner_user_id=int(current_user.id))
    if detail is None:
        raise HTTPException(status_code=404, detail="Scan analysis not found.")
    return wrap_object(detail, owner_user_id=int(current_user.id))


@condition_intelligence_v1_router.get("/condition-intelligence/profiles", response_model=ScanApiV1Envelope)
def v1_condition_profiles(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    rows, total = list_profiles_for_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    items = [ConditionProfileRead.model_validate(row) for row in rows]
    body = ConditionProfileListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@condition_intelligence_v1_router.get("/condition-intelligence/defects", response_model=ScanApiV1Envelope)
def v1_condition_defects(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    rows, total = list_defects_for_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    items = [ConditionDefectRead.model_validate(row) for row in rows]
    body = ConditionDefectListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@condition_intelligence_v1_router.get("/condition-intelligence/subgrades", response_model=ScanApiV1Envelope)
def v1_condition_subgrades(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    rows, total = list_subgrades_for_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    items = [ConditionSubgradeRead.model_validate(row) for row in rows]
    body = ConditionSubgradeListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@condition_intelligence_v1_router.get("/condition-intelligence/quality", response_model=ScanApiV1Envelope)
def v1_condition_quality(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    rows, total = list_quality_for_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    items = [ScanQualityAssessmentRead.model_validate(row) for row in rows]
    body = ScanQualityAssessmentListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@condition_intelligence_v1_router.get("/condition-intelligence/executions", response_model=ScanApiV1Envelope)
def v1_condition_executions(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    rows, total = list_executions_for_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    items = [ConditionAgentExecutionRead.model_validate(row) for row in rows]
    body = ConditionAgentExecutionListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@condition_intelligence_v1_router.get("/condition-intelligence/dashboard", response_model=ScanApiV1Envelope)
def v1_condition_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_condition_dashboard(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@condition_intelligence_v1_router.post("/condition-intelligence/run/quality", response_model=ScanApiV1Envelope)
def v1_run_condition_quality(
    payload: ConditionIntelligenceRunRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    analysis = resolve_or_create_analysis(
        session,
        owner_user_id=int(current_user.id),
        analysis_id=payload.analysis_id,
        inventory_copy_id=payload.inventory_copy_id,
        front_image_id=payload.front_image_id,
        back_image_id=payload.back_image_id,
    )
    result = run_scan_quality_agent(session, analysis=analysis)
    body = ConditionQualityRunResponse(analysis=ScanAnalysisRead.model_validate(analysis), quality=result)
    return wrap_object(body, owner_user_id=int(current_user.id))


@condition_intelligence_v1_router.post("/condition-intelligence/run/defects", response_model=ScanApiV1Envelope)
def v1_run_condition_defects(
    payload: ConditionIntelligenceRunRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    analysis = resolve_or_create_analysis(
        session,
        owner_user_id=int(current_user.id),
        analysis_id=payload.analysis_id,
        inventory_copy_id=payload.inventory_copy_id,
        front_image_id=payload.front_image_id,
        back_image_id=payload.back_image_id,
    )
    defects = run_defect_detection_agent(session, analysis=analysis)
    body = ConditionDefectsRunResponse(analysis=ScanAnalysisRead.model_validate(analysis), defects=defects)
    return wrap_object(body, owner_user_id=int(current_user.id))


@condition_intelligence_v1_router.post("/condition-intelligence/run/profile", response_model=ScanApiV1Envelope)
def v1_run_condition_profile(
    payload: ConditionIntelligenceRunRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    analysis = resolve_or_create_analysis(
        session,
        owner_user_id=int(current_user.id),
        analysis_id=payload.analysis_id,
        inventory_copy_id=payload.inventory_copy_id,
        front_image_id=payload.front_image_id,
        back_image_id=payload.back_image_id,
    )
    profile = run_condition_profile_agent(session, analysis=analysis)
    body = ConditionProfileRunResponse(analysis=ScanAnalysisRead.model_validate(analysis), profile=profile)
    return wrap_object(body, owner_user_id=int(current_user.id))


@condition_intelligence_v1_router.post("/condition-intelligence/run/subgrades", response_model=ScanApiV1Envelope)
def v1_run_condition_subgrades(
    payload: ConditionIntelligenceRunRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    analysis = resolve_or_create_analysis(
        session,
        owner_user_id=int(current_user.id),
        analysis_id=payload.analysis_id,
        inventory_copy_id=payload.inventory_copy_id,
        front_image_id=payload.front_image_id,
        back_image_id=payload.back_image_id,
    )
    subgrades = run_subgrade_agent(session, analysis=analysis)
    body = ConditionSubgradesRunResponse(analysis=ScanAnalysisRead.model_validate(analysis), subgrades=subgrades)
    return wrap_object(body, owner_user_id=int(current_user.id))
