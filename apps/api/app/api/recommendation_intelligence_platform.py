"""P62 Recommendation Intelligence Platform API (Phase 1 preview)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.recommendation_intelligence_v3 import (
    V3CertificationRead,
    V3PreviewItemRead,
    V3PreviewRead,
    V3ReadinessRead,
    V3ScoreComponentRead,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.services.p62_feature_flags import p62_v3_preview_enabled
from app.services.recommendation_v3_certification import certify_recommendation_v3_preview
from app.services.recommendation_v3_preview_service import build_recommendation_v3_preview

recommendation_intelligence_v1_router = APIRouter(
    prefix="/api/v1/recommendation-intelligence",
    tags=["P62 Recommendation Intelligence"],
)


def attach_recommendation_intelligence_platform_layer(app: FastAPI) -> None:
    app.include_router(recommendation_intelligence_v1_router)


def _preview_read(raw: dict) -> V3PreviewRead:
    readiness_raw = raw.get("readiness")
    readiness = None
    if isinstance(readiness_raw, dict):
        readiness = V3ReadinessRead(**readiness_raw)
    items = [
        V3PreviewItemRead(
            title=str(row["title"]),
            recommendation_type=str(row["recommendation_type"]),
            v2_priority_score=float(row["v2_priority_score"]),
            v2_confidence_score=float(row["v2_confidence_score"]),
            v3_preview_score=float(row["v3_preview_score"]),
            release_issue_id=row.get("release_issue_id"),
            demand_intel_status=str(row["demand_intel_status"]),
            components=[V3ScoreComponentRead(**c) for c in row.get("components") or []],
        )
        for row in raw.get("items") or []
    ]
    return V3PreviewRead(
        enabled=bool(raw.get("enabled")),
        not_ready=bool(raw.get("not_ready")),
        reason_codes=list(raw.get("reason_codes") or []),
        items=items,
        readiness=readiness,
        persisted_row_count=int(raw.get("persisted_row_count") or 0),
        v2_mutated=bool(raw.get("v2_mutated")),
        preview_count=int(raw.get("preview_count") or len(items)),
    )


@recommendation_intelligence_v1_router.get("/v3/preview", response_model=ScanApiV1Envelope)
def v1_recommendation_v3_preview(
    limit: int = Query(20, ge=1, le=50),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    if not p62_v3_preview_enabled():
        raise HTTPException(status_code=403, detail="P62_V3_PREVIEW_DISABLED")
    raw = build_recommendation_v3_preview(
        session,
        owner_user_id=int(current_user.id),
        limit=limit,
    )
    return wrap_object(_preview_read(raw), owner_user_id=int(current_user.id))


@recommendation_intelligence_v1_router.get("/v3/certification", response_model=ScanApiV1Envelope)
def v1_recommendation_v3_certification(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    cert = certify_recommendation_v3_preview(session, owner_user_id=int(current_user.id))
    body = V3CertificationRead(**cert)
    return wrap_object(body, owner_user_id=int(current_user.id))
