from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.release_intelligence import (
    ReleaseAgentExecutionListResponse,
    ReleaseAgentExecutionRead,
    ReleaseIntelligenceDashboardRead,
    ReleaseIssueListResponse,
    ReleaseKeySignalListResponse,
    ReleaseSeriesListResponse,
    ReleaseSignalsRunResponse,
    ReleaseVariantListResponse,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.key_issue_agent import detect_key_issues
from app.services.new_number_one_agent import detect_new_number_ones
from app.services.release_dashboard import build_release_dashboard
from app.services.release_import import list_issues_for_owner, list_series_for_owner, list_signals_for_owner, list_variants_for_owner
from app.services.release_intelligence import list_executions_for_owner
from app.services.variant_intelligence_agent import detect_variant_signals

release_intelligence_v1_router = APIRouter(prefix="/api/v1", tags=["Release Intelligence API v1 (P50-01)"])


def attach_release_intelligence_layer(app: FastAPI) -> None:
    app.include_router(release_intelligence_v1_router)


@release_intelligence_v1_router.get("/release-intelligence/series", response_model=ScanApiV1Envelope)
def v1_release_series(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_series_for_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    body = ReleaseSeriesListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@release_intelligence_v1_router.get("/release-intelligence/issues", response_model=ScanApiV1Envelope)
def v1_release_issues(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_issues_for_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    body = ReleaseIssueListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@release_intelligence_v1_router.get("/release-intelligence/variants", response_model=ScanApiV1Envelope)
def v1_release_variants(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_variants_for_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    body = ReleaseVariantListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@release_intelligence_v1_router.get("/release-intelligence/variants/top", response_model=ScanApiV1Envelope)
def v1_release_variants_top(
    limit: int = 20,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    from app.services.release_variant_metrics import list_top_ratio_variants

    items = list_top_ratio_variants(session, owner_user_id=int(current_user.id), limit=limit)
    body = ReleaseVariantListResponse(items=items, total_items=len(items), limit=limit, offset=0)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@release_intelligence_v1_router.get("/release-intelligence/signals", response_model=ScanApiV1Envelope)
def v1_release_signals(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_signals_for_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    body = ReleaseKeySignalListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@release_intelligence_v1_router.get("/release-intelligence/executions", response_model=ScanApiV1Envelope)
def v1_release_executions(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    rows, total = list_executions_for_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    items = [ReleaseAgentExecutionRead.model_validate(row) for row in rows]
    body = ReleaseAgentExecutionListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@release_intelligence_v1_router.get("/release-intelligence/dashboard", response_model=ScanApiV1Envelope)
def v1_release_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_release_dashboard(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@release_intelligence_v1_router.post("/release-intelligence/run/new-number-ones", response_model=ScanApiV1Envelope)
def v1_run_new_number_ones(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    signals, execution = detect_new_number_ones(session, owner_user_id=int(current_user.id))
    body = ReleaseSignalsRunResponse(signals=signals, execution=execution)
    return wrap_object(body, owner_user_id=int(current_user.id))


@release_intelligence_v1_router.post("/release-intelligence/run/key-issues", response_model=ScanApiV1Envelope)
def v1_run_key_issues(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    signals, execution = detect_key_issues(session, owner_user_id=int(current_user.id))
    body = ReleaseSignalsRunResponse(signals=signals, execution=execution)
    return wrap_object(body, owner_user_id=int(current_user.id))


@release_intelligence_v1_router.post("/release-intelligence/run/variants", response_model=ScanApiV1Envelope)
def v1_run_variant_intelligence(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    signals, execution = detect_variant_signals(session, owner_user_id=int(current_user.id))
    body = ReleaseSignalsRunResponse(signals=signals, execution=execution)
    return wrap_object(body, owner_user_id=int(current_user.id))
