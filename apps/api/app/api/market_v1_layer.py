"""P39-07 `/api/v1/market/*` layered routes; identical services as legacy URLs, enveloped responses."""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from sqlmodel import Session
from starlette.responses import JSONResponse

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models import User
from app.schemas.market_api_v1 import MarketApiV1Envelope, wrap_object, wrap_standard_list
from app.schemas.market_determinism import MarketDeterminismValidationRunPayload
from app.schemas.market_ingestion import MarketAcquisitionIngestionBatchCreatePayload
from app.schemas.market_normalization import MarketNormalizationRunCreatePayload
from app.schemas.market_opportunity import MarketAcquisitionOpportunityGeneratePayload
from app.schemas.market_feed import MarketIntelligenceFeedReplayPayload
from app.schemas.market_scoring import MarketAcquisitionScoreRunPayload
from app.schemas.market_signal import MarketAcquisitionSignalGeneratePayload
from app.schemas.portfolio_market_coupling import PortfolioMarketCouplingGeneratePayload
from app.services.market_ingestion import (
    get_ingestion_batch_ops,
    get_ingestion_batch_owner,
    ingest_market_acquisition_batch_for_owner,
    list_ingestion_batches_ops,
    list_ingestion_batches_owner,
    list_ingestion_raw_ops,
    list_ingestion_raw_owner,
)
from app.services.market_normalization import (
    execute_market_normalization_run_for_owner,
    get_normalization_run_ops,
    get_normalization_run_owner,
    list_normalized_candidates_ops,
    list_normalized_candidates_owner,
    list_normalization_issues_ops,
    list_normalization_issues_owner,
    list_normalization_runs_ops,
    list_normalization_runs_owner,
)
from app.services.market_opportunity import (
    generate_market_opportunities_for_owner,
    get_opportunity_detail_ops,
    get_opportunity_detail_owner,
    list_evidence_ops as list_market_opportunity_evidence_ops,
    list_evidence_owner as list_market_opportunity_evidence_owner,
    list_history_ops as list_market_opportunity_history_ops,
    list_history_owner as list_market_opportunity_history_owner,
    list_opportunity_items_ops,
    list_opportunity_items_owner,
    list_snapshots_ops as list_market_opportunity_snapshots_ops,
    list_snapshots_owner as list_market_opportunity_snapshots_owner,
)
from app.services.market_feed import (
    build_market_feed_timeline,
    get_market_feed_event,
    list_market_feed_events,
    list_market_feed_snapshots,
    replay_market_feed,
)
from app.services.market_determinism import (
    get_validation_run_ops,
    get_validation_run_owner,
    list_invariants_ops,
    list_invariants_owner,
    list_replay_audits_ops,
    list_validation_runs_ops,
    list_validation_runs_owner,
    run_market_validation,
)
from app.services.market_scoring import (
    get_score_ops,
    get_score_owner,
    list_history_ops as list_market_scoring_history_ops,
    list_history_owner as list_market_scoring_history_owner,
    list_scores_ops,
    list_scores_owner,
    list_snapshots_ops,
    list_snapshots_owner,
    run_market_acquisition_scoring_for_owner,
)
from app.services.market_signal import (
    generate_market_signals_for_owner,
    get_signal_ops,
    get_signal_owner,
    list_evidence_ops as list_market_signal_evidence_ops,
    list_evidence_owner as list_market_signal_evidence_owner,
    list_history_ops as list_market_signal_history_ops,
    list_history_owner as list_market_signal_history_owner,
    list_signals_ops,
    list_signals_owner,
    list_snapshots_ops as list_market_signal_snapshots_ops,
    list_snapshots_owner as list_market_signal_snapshots_owner,
)
from app.services.ops_admin import ensure_ops_admin_access
from app.services.portfolio_market_coupling import (
    generate_coupling_for_owner,
    get_coupling_detail_ops,
    get_coupling_detail_owner,
    list_coupling_edges_ops,
    list_coupling_edges_owner,
    list_coupling_history_ops,
    list_coupling_history_owner,
    list_coupling_snapshots_ops,
    list_coupling_snapshots_owner,
)

_log = logging.getLogger(__name__)
market_v1_router = APIRouter(prefix="/api/v1/market", tags=["Market API v1 (P39)"])


def _emit_market_event(phase: str, owner_user_id: int | None, **fields: object) -> None:
    safe_fields = {k: v for k, v in fields.items() if v is not None}
    _log.info(
        "p39.market.%s",
        phase,
        extra={"p39_market_phase": phase, "owner_user_id": owner_user_id, **safe_fields},
    )


def _http_error_content(detail: Any) -> tuple[str, Any | None]:
    if isinstance(detail, str):
        return detail, None
    if isinstance(detail, dict):
        return str(detail.get("message") or detail.get("msg") or "Request failed"), detail
    if isinstance(detail, list):
        return "Request failed", detail
    return str(detail), None


def attach_market_v1_layer(app: FastAPI) -> None:
    """Register /api/v1/market routes and path-scoped error envelopes."""

    from fastapi.exception_handlers import (
        http_exception_handler as default_http_exception_handler,
    )
    from fastapi.exception_handlers import (
        request_validation_exception_handler as default_request_validation_exception_handler,
    )

    @app.exception_handler(HTTPException)
    async def _market_v1_http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        if not request.url.path.startswith("/api/v1/market"):
            return await default_http_exception_handler(request, exc)
        message, details = _http_error_content(exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": f"HTTP_{exc.status_code}",
                    "message": message,
                    "details": details,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def _market_v1_validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        if not request.url.path.startswith("/api/v1/market"):
            return await default_request_validation_exception_handler(request, exc)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": exc.errors(),
                }
            },
        )

    app.include_router(market_v1_router)


# --- Owner ingestion ---


@market_v1_router.post(
    "/market-ingestion/batch",
    response_model=MarketApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_owner_create_market_ingestion_batch(
    payload: MarketAcquisitionIngestionBatchCreatePayload,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    body, created = ingest_market_acquisition_batch_for_owner(
        session,
        owner_user_id=int(current_user.id),
        payload=payload,
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    envelope = wrap_object(body, owner_user_id=int(current_user.id), checksum=body.batch_checksum)
    _emit_market_event(
        "ingestion",
        int(current_user.id),
        ingestion_batch_id=body.id,
        checksum=body.batch_checksum,
        snapshot_id=envelope.meta.snapshot_id,
        generated_at=envelope.meta.generated_at,
    )
    return envelope


@market_v1_router.get("/market-ingestion/batches", response_model=MarketApiV1Envelope)
def v1_owner_list_market_ingestion_batches(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    lst = list_ingestion_batches_owner(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(lst, owner_user_id=int(current_user.id))


@market_v1_router.get("/market-ingestion/batches/{batch_id}", response_model=MarketApiV1Envelope)
def v1_owner_get_market_ingestion_batch(
    batch_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    row = get_ingestion_batch_owner(session, owner_user_id=int(current_user.id), batch_id=batch_id)
    return wrap_object(row, owner_user_id=int(current_user.id), checksum=row.batch_checksum)


@market_v1_router.get("/market-ingestion/batches/{batch_id}/raw", response_model=MarketApiV1Envelope)
def v1_owner_list_market_ingestion_raw(
    batch_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    lst = list_ingestion_raw_owner(
        session,
        owner_user_id=int(current_user.id),
        batch_id=batch_id,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=int(current_user.id))


# --- Ops ingestion ---


@market_v1_router.get("/ops/market-ingestion/batches", response_model=MarketApiV1Envelope)
def v1_ops_list_market_ingestion_batches(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    lst = list_ingestion_batches_ops(session, owner_user_id=owner_user_id, limit=limit, offset=offset)
    return wrap_standard_list(lst, owner_user_id=owner_user_id)


@market_v1_router.get("/ops/market-ingestion/batches/{batch_id}", response_model=MarketApiV1Envelope)
def v1_ops_get_market_ingestion_batch(
    batch_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MarketApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    row = get_ingestion_batch_ops(session, batch_id=batch_id)
    return wrap_object(row, owner_user_id=row.owner_user_id, checksum=row.batch_checksum)


@market_v1_router.get("/ops/market-ingestion/raw", response_model=MarketApiV1Envelope)
def v1_ops_list_market_ingestion_raw(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    ingestion_batch_id: int | None = Query(default=None),
    processing_status: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    lst = list_ingestion_raw_ops(
        session,
        owner_user_id=owner_user_id,
        ingestion_batch_id=ingestion_batch_id,
        processing_status=processing_status,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=owner_user_id)


# --- Owner normalization ---


@market_v1_router.post(
    "/market-normalization/run",
    response_model=MarketApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_owner_create_market_normalization_run(
    payload: MarketNormalizationRunCreatePayload,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    body, fresh = execute_market_normalization_run_for_owner(
        session,
        owner_user_id=int(current_user.id),
        payload=payload,
    )
    if not fresh:
        response.status_code = status.HTTP_200_OK
    envelope = wrap_object(body, owner_user_id=int(current_user.id), snapshot_id=body.id, checksum=body.run_checksum)
    _emit_market_event(
        "normalization",
        int(current_user.id),
        normalization_run_id=body.id,
        checksum=body.run_checksum,
        snapshot_id=envelope.meta.snapshot_id,
        generated_at=envelope.meta.generated_at,
    )
    return envelope


@market_v1_router.get("/market-normalization/runs", response_model=MarketApiV1Envelope)
def v1_owner_list_market_normalization_runs(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    ingestion_batch_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    lst = list_normalization_runs_owner(
        session,
        owner_user_id=int(current_user.id),
        ingestion_batch_id=ingestion_batch_id,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=int(current_user.id))


@market_v1_router.get("/market-normalization/runs/{run_id}", response_model=MarketApiV1Envelope)
def v1_owner_get_market_normalization_run(
    run_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    row = get_normalization_run_owner(session, owner_user_id=int(current_user.id), run_id=run_id)
    return wrap_object(row, owner_user_id=int(current_user.id), snapshot_id=row.id, checksum=row.run_checksum)


@market_v1_router.get("/market-normalization/candidates", response_model=MarketApiV1Envelope)
def v1_owner_list_market_normalization_candidates(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    ingestion_batch_id: int | None = Query(default=None),
    normalization_status: str | None = Query(default=None),
    publisher: Annotated[str | None, Query(description="Canonical publisher exact match.")] = None,
    condition_band: str | None = Query(default=None),
    created_since: datetime | None = Query(default=None),
    created_until: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    lst = list_normalized_candidates_owner(
        session,
        owner_user_id=int(current_user.id),
        ingestion_batch_id=ingestion_batch_id,
        normalization_status=normalization_status,
        canonical_publisher=publisher,
        condition_band=condition_band,
        created_since=created_since,
        created_until=created_until,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=int(current_user.id))


@market_v1_router.get("/market-normalization/issues", response_model=MarketApiV1Envelope)
def v1_owner_list_market_normalization_issues(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    ingestion_batch_id: int | None = Query(default=None),
    issue_type: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    created_since: datetime | None = Query(default=None),
    created_until: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    lst = list_normalization_issues_owner(
        session,
        owner_user_id=int(current_user.id),
        ingestion_batch_id=ingestion_batch_id,
        issue_type=issue_type,
        severity=severity,
        created_since=created_since,
        created_until=created_until,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=int(current_user.id))


# --- Ops normalization ---


@market_v1_router.get("/ops/market-normalization/runs", response_model=MarketApiV1Envelope)
def v1_ops_list_market_normalization_runs(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    ingestion_batch_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    lst = list_normalization_runs_ops(
        session,
        owner_user_id_filter=owner_user_id,
        ingestion_batch_id=ingestion_batch_id,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=owner_user_id)


@market_v1_router.get("/ops/market-normalization/candidates", response_model=MarketApiV1Envelope)
def v1_ops_list_market_normalization_candidates(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    ingestion_batch_id: int | None = Query(default=None),
    normalization_status: str | None = Query(default=None),
    publisher: Annotated[str | None, Query(description="Canonical publisher exact match.")] = None,
    condition_band: str | None = Query(default=None),
    created_since: datetime | None = Query(default=None),
    created_until: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    lst = list_normalized_candidates_ops(
        session,
        owner_user_id_filter=owner_user_id,
        ingestion_batch_id=ingestion_batch_id,
        normalization_status=normalization_status,
        canonical_publisher=publisher,
        condition_band=condition_band,
        created_since=created_since,
        created_until=created_until,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=owner_user_id)


@market_v1_router.get("/ops/market-normalization/issues", response_model=MarketApiV1Envelope)
def v1_ops_list_market_normalization_issues(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    ingestion_batch_id: int | None = Query(default=None),
    issue_type: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    created_since: datetime | None = Query(default=None),
    created_until: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    lst = list_normalization_issues_ops(
        session,
        owner_user_id_filter=owner_user_id,
        ingestion_batch_id=ingestion_batch_id,
        issue_type=issue_type,
        severity=severity,
        created_since=created_since,
        created_until=created_until,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=owner_user_id)


@market_v1_router.get("/ops/market-normalization/runs/{run_id}", response_model=MarketApiV1Envelope)
def v1_ops_get_market_normalization_run(
    run_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MarketApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    row = get_normalization_run_ops(session, run_id=run_id)
    oid = row.owner_user_id
    return wrap_object(row, owner_user_id=oid, snapshot_id=row.id, checksum=row.run_checksum)


# --- Owner scoring ---


@market_v1_router.post("/market-scoring/run", response_model=MarketApiV1Envelope)
def v1_owner_run_market_scoring(
    payload: MarketAcquisitionScoreRunPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    resp = run_market_acquisition_scoring_for_owner(
        session,
        owner_user_id=int(current_user.id),
        payload=payload,
    )
    snap = resp.snapshot
    envelope = wrap_object(resp, owner_user_id=int(current_user.id), snapshot_id=snap.id, checksum=snap.checksum)
    _emit_market_event(
        "scoring",
        int(current_user.id),
        scoring_snapshot_id=snap.id,
        checksum=snap.checksum,
        generated_at=envelope.meta.generated_at,
    )
    return envelope


@market_v1_router.get("/market-scoring/scores", response_model=MarketApiV1Envelope)
def v1_owner_list_market_scoring_scores(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    recommendation_label: str | None = Query(default=None),
    confidence_level: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    score_min: Decimal | None = Query(default=None),
    score_max: Decimal | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    lst = list_scores_owner(
        session,
        owner_user_id=int(current_user.id),
        recommendation_label=recommendation_label,
        confidence_level=confidence_level,
        risk_level=risk_level,
        score_min=score_min,
        score_max=score_max,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=int(current_user.id))


@market_v1_router.get("/market-scoring/scores/{score_id}", response_model=MarketApiV1Envelope)
def v1_owner_get_market_scoring_score(
    score_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    row = get_score_owner(session, owner_user_id=int(current_user.id), score_id=score_id)
    chk = row.score.checksum
    sid = row.score.market_acquisition_score_snapshot_id
    return wrap_object(row, owner_user_id=int(current_user.id), snapshot_id=sid, checksum=chk)


@market_v1_router.get("/market-scoring/snapshots", response_model=MarketApiV1Envelope)
def v1_owner_list_market_scoring_snapshots(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    lst = list_snapshots_owner(
        session,
        owner_user_id=int(current_user.id),
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=int(current_user.id))


@market_v1_router.get("/market-scoring/history", response_model=MarketApiV1Envelope)
def v1_owner_list_market_scoring_history(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    recommendation_label: str | None = Query(default=None),
    confidence_level: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    lst = list_market_scoring_history_owner(
        session,
        owner_user_id=int(current_user.id),
        recommendation_label=recommendation_label,
        confidence_level=confidence_level,
        risk_level=risk_level,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=int(current_user.id))


# --- Ops scoring ---


@market_v1_router.get("/ops/market-scoring/scores", response_model=MarketApiV1Envelope)
def v1_ops_list_market_scoring_scores(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    recommendation_label: str | None = Query(default=None),
    confidence_level: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    score_min: Decimal | None = Query(default=None),
    score_max: Decimal | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    lst = list_scores_ops(
        session,
        owner_user_id=owner_user_id,
        recommendation_label=recommendation_label,
        confidence_level=confidence_level,
        risk_level=risk_level,
        score_min=score_min,
        score_max=score_max,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=owner_user_id)


@market_v1_router.get("/ops/market-scoring/scores/{score_id}", response_model=MarketApiV1Envelope)
def v1_ops_get_market_scoring_score(
    score_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MarketApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    row = get_score_ops(session, score_id=score_id)
    chk = row.score.checksum
    sid = row.score.market_acquisition_score_snapshot_id
    oid = row.score.owner_user_id
    return wrap_object(row, owner_user_id=oid, snapshot_id=sid, checksum=chk)


@market_v1_router.get("/ops/market-scoring/snapshots", response_model=MarketApiV1Envelope)
def v1_ops_list_market_scoring_snapshots(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    lst = list_snapshots_ops(
        session,
        owner_user_id=owner_user_id,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=owner_user_id)


@market_v1_router.get("/ops/market-scoring/history", response_model=MarketApiV1Envelope)
def v1_ops_list_market_scoring_history(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    recommendation_label: str | None = Query(default=None),
    confidence_level: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    lst = list_market_scoring_history_ops(
        session,
        owner_user_id=owner_user_id,
        recommendation_label=recommendation_label,
        confidence_level=confidence_level,
        risk_level=risk_level,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=owner_user_id)


# --- Owner signals ---


@market_v1_router.post("/market-signals/generate", response_model=MarketApiV1Envelope)
def v1_owner_generate_market_signals(
    payload: MarketAcquisitionSignalGeneratePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    resp = generate_market_signals_for_owner(session, owner_user_id=int(current_user.id), payload=payload)
    snap = resp.snapshot
    envelope = wrap_object(resp, owner_user_id=int(current_user.id), snapshot_id=snap.id, checksum=snap.checksum)
    _emit_market_event(
        "signals",
        int(current_user.id),
        signal_snapshot_id=snap.id,
        checksum=snap.checksum,
        generated_at=envelope.meta.generated_at,
    )
    return envelope


@market_v1_router.get("/market-signals", response_model=MarketApiV1Envelope)
def v1_owner_list_market_signals(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    signal_type: str | None = Query(default=None),
    signal_strength: str | None = Query(default=None),
    confidence_level: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    lst = list_signals_owner(
        session,
        owner_user_id=int(current_user.id),
        signal_type=signal_type,
        signal_strength=signal_strength,
        confidence_level=confidence_level,
        risk_level=risk_level,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=int(current_user.id))


@market_v1_router.get("/market-signals/{signal_id}", response_model=MarketApiV1Envelope)
def v1_owner_get_market_signal(
    signal_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    row = get_signal_owner(session, owner_user_id=int(current_user.id), signal_id=signal_id)
    sig = row.signal
    return wrap_object(row, owner_user_id=int(current_user.id), checksum=sig.checksum)


@market_v1_router.get("/market-signal-snapshots", response_model=MarketApiV1Envelope)
def v1_owner_list_market_signal_snapshots(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    lst = list_market_signal_snapshots_owner(
        session,
        owner_user_id=int(current_user.id),
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=int(current_user.id))


@market_v1_router.get("/market-signal-evidence", response_model=MarketApiV1Envelope)
def v1_owner_list_market_signal_evidence(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    signal_type: str | None = Query(default=None),
    signal_strength: str | None = Query(default=None),
    confidence_level: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    signal_id: int | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    lst = list_market_signal_evidence_owner(
        session,
        owner_user_id=int(current_user.id),
        signal_type=signal_type,
        signal_strength=signal_strength,
        confidence_level=confidence_level,
        risk_level=risk_level,
        signal_id=signal_id,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=int(current_user.id))


@market_v1_router.get("/market-signal-history", response_model=MarketApiV1Envelope)
def v1_owner_list_market_signal_history(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    signal_type: str | None = Query(default=None),
    signal_strength: str | None = Query(default=None),
    confidence_level: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    lst = list_market_signal_history_owner(
        session,
        owner_user_id=int(current_user.id),
        signal_type=signal_type,
        signal_strength=signal_strength,
        confidence_level=confidence_level,
        risk_level=risk_level,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=int(current_user.id))


# --- Ops signals ---


@market_v1_router.get("/ops/market-signals", response_model=MarketApiV1Envelope)
def v1_ops_list_market_signals(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    signal_type: str | None = Query(default=None),
    signal_strength: str | None = Query(default=None),
    confidence_level: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    lst = list_signals_ops(
        session,
        owner_user_id=owner_user_id,
        signal_type=signal_type,
        signal_strength=signal_strength,
        confidence_level=confidence_level,
        risk_level=risk_level,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=owner_user_id)


@market_v1_router.get("/ops/market-signals/{signal_id}", response_model=MarketApiV1Envelope)
def v1_ops_get_market_signal(
    signal_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MarketApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    row = get_signal_ops(session, signal_id=signal_id)
    sig = row.signal
    oid = sig.owner_user_id
    return wrap_object(row, owner_user_id=oid, checksum=sig.checksum)


@market_v1_router.get("/ops/market-signal-snapshots", response_model=MarketApiV1Envelope)
def v1_ops_list_market_signal_snapshots(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    lst = list_market_signal_snapshots_ops(
        session,
        owner_user_id=owner_user_id,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=owner_user_id)


@market_v1_router.get("/ops/market-signal-evidence", response_model=MarketApiV1Envelope)
def v1_ops_list_market_signal_evidence(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    signal_type: str | None = Query(default=None),
    signal_strength: str | None = Query(default=None),
    confidence_level: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    signal_id: int | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    lst = list_market_signal_evidence_ops(
        session,
        owner_user_id=owner_user_id,
        signal_type=signal_type,
        signal_strength=signal_strength,
        confidence_level=confidence_level,
        risk_level=risk_level,
        signal_id=signal_id,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=owner_user_id)


@market_v1_router.get("/ops/market-signal-history", response_model=MarketApiV1Envelope)
def v1_ops_list_market_signal_history(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    signal_type: str | None = Query(default=None),
    signal_strength: str | None = Query(default=None),
    confidence_level: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    lst = list_market_signal_history_ops(
        session,
        owner_user_id=owner_user_id,
        signal_type=signal_type,
        signal_strength=signal_strength,
        confidence_level=confidence_level,
        risk_level=risk_level,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=owner_user_id)


# --- Owner opportunities ---


@market_v1_router.post("/market-opportunities/generate", response_model=MarketApiV1Envelope)
def v1_owner_generate_market_opportunities(
    payload: MarketAcquisitionOpportunityGeneratePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    resp = generate_market_opportunities_for_owner(session, owner_user_id=int(current_user.id), payload=payload)
    snap = resp.snapshot
    envelope = wrap_object(resp, owner_user_id=int(current_user.id), snapshot_id=snap.id, checksum=snap.snapshot_checksum)
    _emit_market_event(
        "opportunity",
        int(current_user.id),
        opportunity_snapshot_id=snap.id,
        checksum=snap.snapshot_checksum,
        generated_at=envelope.meta.generated_at,
    )
    return envelope


@market_v1_router.get("/market-opportunities/snapshots", response_model=MarketApiV1Envelope)
def v1_owner_list_market_opportunity_snapshots(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    lst = list_market_opportunity_snapshots_owner(
        session,
        owner_user_id=int(current_user.id),
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=int(current_user.id))


@market_v1_router.get("/market-opportunities/evidence", response_model=MarketApiV1Envelope)
def v1_owner_list_market_opportunity_evidence(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    opportunity_snapshot_id: int | None = Query(default=None, ge=1),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    lst = list_market_opportunity_evidence_owner(
        session,
        owner_user_id=int(current_user.id),
        opportunity_snapshot_id=opportunity_snapshot_id,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=int(current_user.id))


@market_v1_router.get("/market-opportunities/history", response_model=MarketApiV1Envelope)
def v1_owner_list_market_opportunity_history(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    opportunity_snapshot_id: int | None = Query(default=None, ge=1),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    lst = list_market_opportunity_history_owner(
        session,
        owner_user_id=int(current_user.id),
        opportunity_snapshot_id=opportunity_snapshot_id,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=int(current_user.id))


@market_v1_router.get("/market-opportunities", response_model=MarketApiV1Envelope)
def v1_owner_list_market_opportunity_items(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    opportunity_snapshot_id: int | None = Query(default=None, ge=1),
    signal_type: str | None = Query(default=None),
    signal_strength: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    lst = list_opportunity_items_owner(
        session,
        owner_user_id=int(current_user.id),
        snapshot_id=opportunity_snapshot_id,
        signal_type=signal_type,
        signal_strength=signal_strength,
        risk_level=risk_level,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=int(current_user.id))


@market_v1_router.get("/market-opportunities/{snapshot_id}", response_model=MarketApiV1Envelope)
def v1_owner_get_market_opportunity_snapshot(
    snapshot_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    row = get_opportunity_detail_owner(
        session,
        owner_user_id=int(current_user.id),
        opportunity_snapshot_id=snapshot_id,
    )
    snap = row.snapshot
    return wrap_object(row, owner_user_id=int(current_user.id), snapshot_id=snap.id, checksum=snap.snapshot_checksum)


# --- Owner portfolio coupling ---


@market_v1_router.post("/market-portfolio-coupling/generate", response_model=MarketApiV1Envelope)
def v1_owner_generate_portfolio_market_coupling(
    payload: PortfolioMarketCouplingGeneratePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    resp = generate_coupling_for_owner(session, owner_user_id=int(current_user.id), payload=payload)
    snap = resp.snapshot
    envelope = wrap_object(resp, owner_user_id=int(current_user.id), snapshot_id=snap.id, checksum=snap.snapshot_checksum)
    _emit_market_event(
        "coupling",
        int(current_user.id),
        coupling_snapshot_id=snap.id,
        checksum=snap.snapshot_checksum,
        generated_at=envelope.meta.generated_at,
    )
    return envelope


@market_v1_router.get("/market-portfolio-coupling/snapshots", response_model=MarketApiV1Envelope)
def v1_owner_list_portfolio_coupling_snapshots_alias(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    min_alignment_score: Decimal | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    lst = list_coupling_snapshots_owner(
        session,
        owner_user_id=int(current_user.id),
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        min_alignment_score=min_alignment_score,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=int(current_user.id))


@market_v1_router.get("/market-portfolio-coupling", response_model=MarketApiV1Envelope)
def v1_owner_list_portfolio_coupling_root(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    min_alignment_score: Decimal | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    lst = list_coupling_snapshots_owner(
        session,
        owner_user_id=int(current_user.id),
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        min_alignment_score=min_alignment_score,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=int(current_user.id))


@market_v1_router.get("/market-portfolio-coupling/edges", response_model=MarketApiV1Envelope)
def v1_owner_list_portfolio_coupling_edges(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    coupling_snapshot_id: int | None = Query(default=None, ge=1),
    coupling_type: str | None = Query(default=None),
    coupling_strength: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    min_coupling_score: int | None = Query(default=None, ge=0, le=100),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    lst = list_coupling_edges_owner(
        session,
        owner_user_id=int(current_user.id),
        coupling_snapshot_id=coupling_snapshot_id,
        coupling_type=coupling_type,
        coupling_strength=coupling_strength,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        min_coupling_score=min_coupling_score,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=int(current_user.id))


@market_v1_router.get("/market-portfolio-coupling/history", response_model=MarketApiV1Envelope)
def v1_owner_list_portfolio_coupling_history(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    coupling_snapshot_id: int | None = Query(default=None, ge=1),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    min_alignment_score: Decimal | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    lst = list_coupling_history_owner(
        session,
        owner_user_id=int(current_user.id),
        coupling_snapshot_id=coupling_snapshot_id,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        min_alignment_score=min_alignment_score,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=int(current_user.id))


@market_v1_router.get("/market-portfolio-coupling/{snapshot_id}", response_model=MarketApiV1Envelope)
def v1_owner_get_portfolio_coupling_snapshot(
    snapshot_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    row = get_coupling_detail_owner(session, owner_user_id=int(current_user.id), snapshot_id=snapshot_id)
    snap = row.snapshot
    return wrap_object(row, owner_user_id=int(current_user.id), snapshot_id=snap.id, checksum=snap.snapshot_checksum)


# --- Ops opportunities ---


@market_v1_router.get("/ops/market-opportunities/snapshots", response_model=MarketApiV1Envelope)
def v1_ops_list_market_opportunity_snapshots(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    lst = list_market_opportunity_snapshots_ops(
        session,
        owner_user_id=owner_user_id,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=owner_user_id)


@market_v1_router.get("/ops/market-opportunities/evidence", response_model=MarketApiV1Envelope)
def v1_ops_list_market_opportunity_evidence(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    opportunity_snapshot_id: int | None = Query(default=None, ge=1),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    lst = list_market_opportunity_evidence_ops(
        session,
        owner_user_id=owner_user_id,
        opportunity_snapshot_id=opportunity_snapshot_id,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=owner_user_id)


@market_v1_router.get("/ops/market-opportunities/history", response_model=MarketApiV1Envelope)
def v1_ops_list_market_opportunity_history(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    opportunity_snapshot_id: int | None = Query(default=None, ge=1),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    lst = list_market_opportunity_history_ops(
        session,
        owner_user_id=owner_user_id,
        opportunity_snapshot_id=opportunity_snapshot_id,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=owner_user_id)


@market_v1_router.get("/ops/market-opportunities", response_model=MarketApiV1Envelope)
def v1_ops_list_market_opportunity_items(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    opportunity_snapshot_id: int | None = Query(default=None, ge=1),
    signal_type: str | None = Query(default=None),
    signal_strength: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    lst = list_opportunity_items_ops(
        session,
        owner_user_id=owner_user_id,
        snapshot_id=opportunity_snapshot_id,
        signal_type=signal_type,
        signal_strength=signal_strength,
        risk_level=risk_level,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=owner_user_id)


@market_v1_router.get("/ops/market-opportunities/{snapshot_id}", response_model=MarketApiV1Envelope)
def v1_ops_get_market_opportunity_snapshot(
    snapshot_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MarketApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    row = get_opportunity_detail_ops(session, opportunity_snapshot_id=snapshot_id)
    snap = row.snapshot
    oid = snap.owner_user_id
    return wrap_object(row, owner_user_id=oid, snapshot_id=snap.id, checksum=snap.snapshot_checksum)


# --- Ops portfolio coupling ---


@market_v1_router.get("/ops/market-portfolio-coupling/snapshots", response_model=MarketApiV1Envelope)
def v1_ops_list_portfolio_coupling_snapshots_alias(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    min_alignment_score: Decimal | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    lst = list_coupling_snapshots_ops(
        session,
        owner_user_id=owner_user_id,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        min_alignment_score=min_alignment_score,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=owner_user_id)


@market_v1_router.get("/ops/market-portfolio-coupling", response_model=MarketApiV1Envelope)
def v1_ops_list_portfolio_coupling_root(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    min_alignment_score: Decimal | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    lst = list_coupling_snapshots_ops(
        session,
        owner_user_id=owner_user_id,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        min_alignment_score=min_alignment_score,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=owner_user_id)


@market_v1_router.get("/ops/market-portfolio-coupling/edges", response_model=MarketApiV1Envelope)
def v1_ops_list_portfolio_coupling_edges(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    coupling_snapshot_id: int | None = Query(default=None, ge=1),
    coupling_type: str | None = Query(default=None),
    coupling_strength: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    min_coupling_score: int | None = Query(default=None, ge=0, le=100),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    lst = list_coupling_edges_ops(
        session,
        owner_user_id=owner_user_id,
        coupling_snapshot_id=coupling_snapshot_id,
        coupling_type=coupling_type,
        coupling_strength=coupling_strength,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        min_coupling_score=min_coupling_score,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=owner_user_id)


@market_v1_router.get("/ops/market-portfolio-coupling/history", response_model=MarketApiV1Envelope)
def v1_ops_list_portfolio_coupling_history(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    coupling_snapshot_id: int | None = Query(default=None, ge=1),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    min_alignment_score: Decimal | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    lst = list_coupling_history_ops(
        session,
        owner_user_id=owner_user_id,
        coupling_snapshot_id=coupling_snapshot_id,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        min_alignment_score=min_alignment_score,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=owner_user_id)


@market_v1_router.get("/ops/market-portfolio-coupling/{snapshot_id}", response_model=MarketApiV1Envelope)
def v1_ops_get_portfolio_coupling_snapshot(
    snapshot_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
) -> MarketApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    row = get_coupling_detail_ops(session, snapshot_id=snapshot_id, owner_filter=owner_user_id)
    snap = row.snapshot
    return wrap_object(
        row,
        owner_user_id=owner_user_id if owner_user_id is not None else snap.owner_user_id,
        snapshot_id=snap.id,
        checksum=snap.snapshot_checksum,
    )


# --- Owner feed ---


@market_v1_router.get("/market-feed/events", response_model=MarketApiV1Envelope)
def v1_owner_list_market_feed_events(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    event_type: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    related_snapshot_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    lst = list_market_feed_events(
        session,
        owner_user_id=int(current_user.id),
        event_type=event_type,
        severity=severity,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        related_snapshot_id=related_snapshot_id,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=int(current_user.id))


@market_v1_router.get("/market-feed/events/{event_id}", response_model=MarketApiV1Envelope)
def v1_owner_get_market_feed_event(
    event_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    row = get_market_feed_event(session, event_id=event_id, owner_user_id=int(current_user.id))
    return wrap_object(row, owner_user_id=int(current_user.id), snapshot_id=row.event_sequence_id, checksum=row.event_checksum)


@market_v1_router.get("/market-feed/timeline", response_model=MarketApiV1Envelope)
def v1_owner_get_market_feed_timeline(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    event_type: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    related_snapshot_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    timeline = build_market_feed_timeline(
        session,
        owner_user_id=int(current_user.id),
        event_type=event_type,
        severity=severity,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        related_snapshot_id=related_snapshot_id,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(timeline, owner_user_id=int(current_user.id))


@market_v1_router.get("/market-feed/snapshots", response_model=MarketApiV1Envelope)
def v1_owner_list_market_feed_snapshots(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    lst = list_market_feed_snapshots(
        session,
        owner_user_id=int(current_user.id),
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=int(current_user.id))


@market_v1_router.post("/market-feed/replay", response_model=MarketApiV1Envelope)
def v1_owner_replay_market_feed(
    payload: MarketIntelligenceFeedReplayPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    owner_user_id = int(current_user.id)
    if payload.owner_user_id is not None and payload.owner_user_id != owner_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot replay another owner's feed.")
    replay = replay_market_feed(
        session,
        payload=MarketIntelligenceFeedReplayPayload.model_validate(
            {**payload.model_dump(mode="json"), "owner_user_id": owner_user_id}
        ),
    )
    session.commit()
    snap = replay.snapshot
    return wrap_object(replay, owner_user_id=owner_user_id, snapshot_id=snap.id, checksum=snap.snapshot_checksum)


# --- Ops feed ---


@market_v1_router.get("/ops/market-feed/events", response_model=MarketApiV1Envelope)
def v1_ops_list_market_feed_events(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    event_type: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    related_snapshot_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    lst = list_market_feed_events(
        session,
        owner_user_id=owner_user_id,
        event_type=event_type,
        severity=severity,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        related_snapshot_id=related_snapshot_id,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=owner_user_id)


@market_v1_router.get("/ops/market-feed/timeline", response_model=MarketApiV1Envelope)
def v1_ops_get_market_feed_timeline(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    event_type: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    related_snapshot_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    timeline = build_market_feed_timeline(
        session,
        owner_user_id=owner_user_id,
        event_type=event_type,
        severity=severity,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        related_snapshot_id=related_snapshot_id,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(timeline, owner_user_id=owner_user_id)


@market_v1_router.get("/ops/market-feed/snapshots", response_model=MarketApiV1Envelope)
def v1_ops_list_market_feed_snapshots(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    lst = list_market_feed_snapshots(
        session,
        owner_user_id=owner_user_id,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(lst, owner_user_id=owner_user_id)


# --- Owner determinism ---


@market_v1_router.get("/market-determinism/validation-runs", response_model=MarketApiV1Envelope)
def v1_owner_list_market_determinism_runs(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    validation_status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    rows = list_validation_runs_owner(
        session,
        owner_user_id=int(current_user.id),
        validation_status=validation_status,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(rows, owner_user_id=int(current_user.id))


@market_v1_router.get("/market-determinism/validation-runs/{validation_run_id}", response_model=MarketApiV1Envelope)
def v1_owner_get_market_determinism_run(
    validation_run_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    row = get_validation_run_owner(
        session,
        owner_user_id=int(current_user.id),
        validation_run_id=validation_run_id,
    )
    return wrap_object(
        row,
        owner_user_id=int(current_user.id),
        snapshot_id=row.run.id,
        checksum=row.run.validation_checksum,
    )


@market_v1_router.get("/market-determinism/invariants", response_model=MarketApiV1Envelope)
def v1_owner_list_market_determinism_invariants(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    validation_run_id: int | None = Query(default=None),
    invariant_status: str | None = Query(default=None),
    layer_name: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    rows = list_invariants_owner(
        session,
        owner_user_id=int(current_user.id),
        validation_run_id=validation_run_id,
        invariant_status=invariant_status,
        layer_name=layer_name,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(rows, owner_user_id=int(current_user.id))


@market_v1_router.post(
    "/market-determinism/run",
    response_model=MarketApiV1Envelope,
    status_code=status.HTTP_201_CREATED,
)
def v1_owner_run_market_determinism(
    payload: MarketDeterminismValidationRunPayload,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MarketApiV1Envelope:
    assert current_user.id is not None
    row, created = run_market_validation(
        session,
        owner_user_id=int(current_user.id),
        payload=payload,
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return wrap_object(
        row,
        owner_user_id=int(current_user.id),
        snapshot_id=row.run.id,
        checksum=row.run.validation_checksum,
    )


# --- Ops determinism ---


@market_v1_router.get("/ops/market-determinism/validation-runs", response_model=MarketApiV1Envelope)
def v1_ops_list_market_determinism_runs(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    validation_status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    rows = list_validation_runs_ops(
        session,
        owner_user_id=owner_user_id,
        validation_status=validation_status,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(rows, owner_user_id=owner_user_id)


@market_v1_router.get("/ops/market-determinism/validation-runs/{validation_run_id}", response_model=MarketApiV1Envelope)
def v1_ops_get_market_determinism_run(
    validation_run_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
) -> MarketApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    row = get_validation_run_ops(
        session,
        validation_run_id=validation_run_id,
        owner_user_id=owner_user_id,
    )
    return wrap_object(
        row,
        owner_user_id=owner_user_id if owner_user_id is not None else row.run.owner_user_id,
        snapshot_id=row.run.id,
        checksum=row.run.validation_checksum,
    )


@market_v1_router.get("/ops/market-determinism/invariants", response_model=MarketApiV1Envelope)
def v1_ops_list_market_determinism_invariants(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    validation_run_id: int | None = Query(default=None),
    invariant_status: str | None = Query(default=None),
    layer_name: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    rows = list_invariants_ops(
        session,
        owner_user_id=owner_user_id,
        validation_run_id=validation_run_id,
        invariant_status=invariant_status,
        layer_name=layer_name,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(rows, owner_user_id=owner_user_id)


@market_v1_router.get("/ops/market-determinism/replay-audits", response_model=MarketApiV1Envelope)
def v1_ops_list_market_determinism_replay_audits(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    validation_run_id: int | None = Query(default=None),
    replay_status: str | None = Query(default=None),
    artifact_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketApiV1Envelope:
    ensure_ops_admin_access(current_user, settings)
    rows = list_replay_audits_ops(
        session,
        owner_user_id=owner_user_id,
        validation_run_id=validation_run_id,
        replay_status=replay_status,
        artifact_type=artifact_type,
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(rows, owner_user_id=owner_user_id)
