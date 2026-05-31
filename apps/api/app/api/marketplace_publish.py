from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.marketplace_publish import MarketplacePublishRequest
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.marketplace_publish_engine import (
    complete_publish_job,
    create_publish_job,
    fail_publish_job,
    get_publish_job,
    list_publish_jobs,
    plan_publish_job,
    ready_publish_job,
    rebuild_publish_request,
    start_publish_job,
    validate_job_request,
)

marketplace_publish_v1_router = APIRouter(prefix="/api/v1", tags=["Marketplace Publish Engine API v1"])


def attach_marketplace_publish_layer(app: FastAPI) -> None:
    app.include_router(marketplace_publish_v1_router)


@marketplace_publish_v1_router.post("/marketplace-publish/jobs", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_create_marketplace_publish_job(
    payload: MarketplacePublishRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = create_publish_job(
        session,
        owner_id=int(current_user.id),
        requested_by=int(current_user.id),
        payload=payload,
    )
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.job.id)


@marketplace_publish_v1_router.get("/marketplace-publish/jobs", response_model=ScanApiV1Envelope)
def v1_list_marketplace_publish_jobs(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_publish_jobs(session, owner_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@marketplace_publish_v1_router.get("/marketplace-publish/jobs/{job_id}", response_model=ScanApiV1Envelope)
def v1_get_marketplace_publish_job(
    job_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_publish_job(session, owner_id=int(current_user.id), job_id=job_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.job.id)


@marketplace_publish_v1_router.post("/marketplace-publish/jobs/{job_id}/validate", response_model=ScanApiV1Envelope)
def v1_validate_marketplace_publish_job(
    job_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    request = rebuild_publish_request(session, owner_id=int(current_user.id), job_id=job_id)
    body = validate_job_request(session, owner_id=int(current_user.id), job_id=job_id, payload=request)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.job.id)


@marketplace_publish_v1_router.post("/marketplace-publish/jobs/{job_id}/plan", response_model=ScanApiV1Envelope)
def v1_plan_marketplace_publish_job(
    job_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    request = rebuild_publish_request(session, owner_id=int(current_user.id), job_id=job_id)
    body = plan_publish_job(session, owner_id=int(current_user.id), job_id=job_id, payload=request)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.job.id)


@marketplace_publish_v1_router.post("/marketplace-publish/jobs/{job_id}/ready", response_model=ScanApiV1Envelope)
def v1_ready_marketplace_publish_job(
    job_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = ready_publish_job(session, owner_id=int(current_user.id), job_id=job_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.job.id)


@marketplace_publish_v1_router.post("/marketplace-publish/jobs/{job_id}/complete", response_model=ScanApiV1Envelope)
def v1_complete_marketplace_publish_job(
    job_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = complete_publish_job(session, owner_id=int(current_user.id), job_id=job_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.job.id)


@marketplace_publish_v1_router.post("/marketplace-publish/jobs/{job_id}/fail", response_model=ScanApiV1Envelope)
def v1_fail_marketplace_publish_job(
    job_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = fail_publish_job(session, owner_id=int(current_user.id), job_id=job_id)
    return wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.job.id)
