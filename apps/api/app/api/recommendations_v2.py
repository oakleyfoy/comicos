from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.recommendation_v2 import (
    RecommendationComponentRead,
    RecommendationDecisionRead,
    RecommendationV2DashboardRead,
    RecommendationV2DetailRead,
    RecommendationV2ListResponse,
    RecommendationV2Read,
    RecommendationV2RunResponse,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.recommendation_v2_dashboard import build_recommendations_v2_dashboard, list_latest_recommendations_v2
from app.services.recommendation_v2_engine import (
    generate_recommendations_v2,
    generate_weekly_buy_list_v2,
    get_recommendation_detail,
)

recommendations_v2_router = APIRouter(prefix="/api/v1", tags=["Recommendations V2 API (P51-04)"])


def attach_recommendations_v2_layer(app: FastAPI) -> None:
    app.include_router(recommendations_v2_router)


def _to_read(row, issue, series) -> RecommendationV2Read:
    return RecommendationV2Read(
        id=int(row.id or 0),
        release_issue_id=row.release_issue_id,
        release_variant_id=row.release_variant_id,
        series_name=series.series_name,
        issue_number=issue.issue_number,
        title=issue.title,
        publisher=series.publisher,
        total_score=float(row.total_score),
        recommendation_tier=row.recommendation_tier,
        recommendation_type=row.recommendation_type,
        confidence_score=float(row.confidence_score),
    )


@recommendations_v2_router.post("/recommendations-v2/run", response_model=ScanApiV1Envelope)
def v1_recommendations_v2_run(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    run = generate_recommendations_v2(session, owner_user_id=int(current_user.id))
    body = RecommendationV2RunResponse(
        run_uuid=run.run_uuid,
        status=run.status,
        issues_scored=run.issues_scored,
        variants_scored=run.variants_scored,
        recommendations_created=run.recommendations_created,
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@recommendations_v2_router.get("/recommendations-v2", response_model=ScanApiV1Envelope)
def v1_recommendations_v2_list(
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    lim = max(1, min(limit, 500))
    off = max(0, offset)
    items, total = list_latest_recommendations_v2(
        session, owner_user_id=int(current_user.id), limit=lim, offset=off
    )
    body = RecommendationV2ListResponse(items=items, total_items=total, limit=lim, offset=off)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@recommendations_v2_router.get("/recommendations-v2/dashboard", response_model=ScanApiV1Envelope)
def v1_recommendations_v2_dashboard(
    limit: int = 25,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    lim = max(1, min(limit, 100))
    body = build_recommendations_v2_dashboard(session, owner_user_id=int(current_user.id), limit=lim)
    return wrap_object(body, owner_user_id=int(current_user.id))


@recommendations_v2_router.get("/recommendations-v2/top", response_model=ScanApiV1Envelope)
def v1_recommendations_v2_top(
    limit: int = 25,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    lim = max(1, min(limit, 100))
    dashboard = build_recommendations_v2_dashboard(session, owner_user_id=int(current_user.id), limit=lim)
    combined = (
        dashboard.must_buy
        + dashboard.strong_buy
        + dashboard.buy
        + dashboard.watch
        + dashboard.pass_tier
    )
    combined.sort(key=lambda row: row.total_score, reverse=True)
    body = RecommendationV2ListResponse(items=combined[:lim], total_items=len(combined), limit=lim, offset=0)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@recommendations_v2_router.get("/recommendations-v2/weekly-buy-list", response_model=ScanApiV1Envelope)
def v1_recommendations_v2_weekly(
    limit: int = 50,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    lim = max(1, min(limit, 200))
    rows = generate_weekly_buy_list_v2(session, owner_user_id=int(current_user.id), limit=lim)
    items: list[RecommendationV2Read] = []
    for row in rows:
        score, _, _, issue, series = get_recommendation_detail(
            session, owner_user_id=int(current_user.id), score_id=int(row.id or 0)
        )
        items.append(_to_read(score, issue, series))
    body = RecommendationV2ListResponse(items=items, total_items=len(items), limit=lim, offset=0)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@recommendations_v2_router.get("/recommendations-v2/{score_id}", response_model=ScanApiV1Envelope)
def v1_recommendations_v2_detail(
    score_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    try:
        score, components, decision, issue, series = get_recommendation_detail(
            session, owner_user_id=int(current_user.id), score_id=score_id
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Recommendation not found") from exc
    body = RecommendationV2DetailRead(
        **_to_read(score, issue, series).model_dump(),
        components=[
            RecommendationComponentRead(
                component_name=c.component_name,
                component_score=c.component_score,
                component_weight=c.component_weight,
                explanation=c.explanation,
            )
            for c in components
        ],
        decision=(
            RecommendationDecisionRead(
                decision_summary=decision.decision_summary,
                primary_reason=decision.primary_reason,
                risk_note=decision.risk_note,
                suggested_action=decision.suggested_action,
                suggested_quantity=decision.suggested_quantity,
            )
            if decision
            else None
        ),
    )
    return wrap_object(body, owner_user_id=int(current_user.id))
