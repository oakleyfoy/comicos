from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI
from sqlmodel import Session

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models import User
from app.schemas.production_readiness import (
    GoLiveAssessmentListResponse,
    ProductionCertificationListResponse,
    ProductionCertificationRunResponse,
    ProductionReadinessCheckListResponse,
    ProductionReadinessGoLiveRunResponse,
    ProductionReadinessRunResponse,
    ReadinessChecklistListResponse,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.ops_admin import ensure_ops_admin_access
from app.services.production_certification import (
    build_production_readiness_dashboard,
    generate_certification,
    generate_go_live_assessment,
    list_assessments_for_owner,
    list_certifications_for_owner,
)
from app.services.production_readiness import (
    get_latest_production_readiness_validation,
    list_readiness_checks_for_owner,
    run_production_readiness_check,
    validate_production_readiness,
)
from app.services.readiness_checklist import generate_readiness_checklist, list_checklist_items_for_owner

production_readiness_v1_router = APIRouter(prefix="/api/v1", tags=["Production Readiness API v1 (P48-04)"])


def attach_production_readiness_layer(app: FastAPI) -> None:
    app.include_router(production_readiness_v1_router)


@production_readiness_v1_router.get("/production-readiness/checks", response_model=ScanApiV1Envelope)
def v1_production_readiness_checks(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_readiness_checks_for_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    body = ProductionReadinessCheckListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@production_readiness_v1_router.get("/production-readiness/checklist", response_model=ScanApiV1Envelope)
def v1_production_readiness_checklist(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_checklist_items_for_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    body = ReadinessChecklistListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@production_readiness_v1_router.get("/production-readiness/certification", response_model=ScanApiV1Envelope)
def v1_production_readiness_certification(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_certifications_for_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    body = ProductionCertificationListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@production_readiness_v1_router.get("/production-readiness/assessment", response_model=ScanApiV1Envelope)
def v1_production_readiness_assessment(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_assessments_for_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    body = GoLiveAssessmentListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@production_readiness_v1_router.get("/production-readiness/dashboard", response_model=ScanApiV1Envelope)
def v1_production_readiness_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_production_readiness_dashboard(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@production_readiness_v1_router.get("/production-readiness/latest", response_model=ScanApiV1Envelope)
def v1_production_readiness_latest(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_latest_production_readiness_validation(session, owner_user_id=int(current_user.id))
    if body is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="No production readiness runs recorded yet.")
    return wrap_object(body, owner_user_id=int(current_user.id))


@production_readiness_v1_router.post("/production-readiness/run", response_model=ScanApiV1Envelope)
def v1_run_production_readiness_go_live(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    assert current_user.id is not None
    validation = run_production_readiness_check(session, owner_user_id=int(current_user.id))
    body = ProductionReadinessGoLiveRunResponse(validation=validation)
    return wrap_object(body, owner_user_id=int(current_user.id))


@production_readiness_v1_router.post("/production-readiness/run/readiness", response_model=ScanApiV1Envelope)
def v1_run_production_readiness(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    assert current_user.id is not None
    owner_user_id = int(current_user.id)
    checks = validate_production_readiness(session, owner_user_id=owner_user_id)
    checklist_items = generate_readiness_checklist(session, owner_user_id=owner_user_id)
    body = ProductionReadinessRunResponse(checks=checks, checklist_items=checklist_items)
    return wrap_object(body, owner_user_id=owner_user_id)


@production_readiness_v1_router.post("/production-readiness/run/certification", response_model=ScanApiV1Envelope)
def v1_run_production_certification(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    assert current_user.id is not None
    owner_user_id = int(current_user.id)
    certification = generate_certification(session, owner_user_id=owner_user_id)
    assessment = generate_go_live_assessment(session, owner_user_id=owner_user_id, certification=certification)
    body = ProductionCertificationRunResponse(certification=certification, assessment=assessment)
    return wrap_object(body, owner_user_id=owner_user_id)
