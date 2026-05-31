from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI
from sqlmodel import Session

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models import User
from app.schemas.operations_reliability import (
    JobHealthMetricListResponse,
    OperationsReliabilityRunResponse,
    PlatformHealthCheckListResponse,
    QueueHealthMetricListResponse,
    RecoveryRecommendationListResponse,
    ReliabilityIssueListResponse,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.ops_admin import ensure_ops_admin_access
from app.services.platform_health import check_platform_health
from app.services.recovery_recommendations import (
    build_operations_dashboard,
    generate_recovery_recommendations,
    list_recommendations_for_owner,
)
from app.services.reliability_monitor import (
    list_job_metrics,
    list_queue_metrics,
    list_reliability_issues_for_owner,
    run_reliability_monitor,
)

operations_reliability_v1_router = APIRouter(prefix="/api/v1", tags=["Operations Reliability API v1 (P48-03)"])


def attach_operations_reliability_layer(app: FastAPI) -> None:
    app.include_router(operations_reliability_v1_router)


@operations_reliability_v1_router.get("/operations-reliability/health", response_model=ScanApiV1Envelope)
def v1_operations_reliability_health(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_operations_dashboard(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@operations_reliability_v1_router.get("/operations-reliability/issues", response_model=ScanApiV1Envelope)
def v1_operations_reliability_issues(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_reliability_issues_for_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    body = ReliabilityIssueListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@operations_reliability_v1_router.get("/operations-reliability/jobs", response_model=ScanApiV1Envelope)
def v1_operations_reliability_jobs(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_job_metrics(session, limit=limit, offset=offset)
    body = JobHealthMetricListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@operations_reliability_v1_router.get("/operations-reliability/queues", response_model=ScanApiV1Envelope)
def v1_operations_reliability_queues(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_queue_metrics(session, limit=limit, offset=offset)
    body = QueueHealthMetricListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@operations_reliability_v1_router.get("/operations-reliability/recommendations", response_model=ScanApiV1Envelope)
def v1_operations_reliability_recommendations(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_recommendations_for_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    body = RecoveryRecommendationListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@operations_reliability_v1_router.post("/operations-reliability/run/health", response_model=ScanApiV1Envelope)
def v1_run_operations_health(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    assert current_user.id is not None
    checks = check_platform_health(session, owner_user_id=int(current_user.id))
    body = PlatformHealthCheckListResponse(items=checks, total_items=len(checks), limit=len(checks), offset=0)
    return wrap_object(body, owner_user_id=int(current_user.id))


@operations_reliability_v1_router.post("/operations-reliability/run/reliability", response_model=ScanApiV1Envelope)
def v1_run_operations_reliability(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    assert current_user.id is not None
    body = OperationsReliabilityRunResponse.model_validate(run_reliability_monitor(session, owner_user_id=int(current_user.id)))
    return wrap_object(body, owner_user_id=int(current_user.id))


@operations_reliability_v1_router.post("/operations-reliability/run/recommendations", response_model=ScanApiV1Envelope)
def v1_run_operations_recommendations(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    assert current_user.id is not None
    items = generate_recovery_recommendations(session, owner_user_id=int(current_user.id))
    body = RecoveryRecommendationListResponse(items=items, total_items=len(items), limit=len(items), offset=0)
    return wrap_object(body, owner_user_id=int(current_user.id))
