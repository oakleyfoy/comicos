"""P77-01 collector profile (`/api/v1/collector-profile/*`)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.p77_collector_profile import (
    P77CollectorBudgetRead,
    P77CollectorBudgetUpdate,
    P77CollectorGoalCreate,
    P77CollectorGoalListResponse,
    P77CollectorGoalRead,
    P77CollectorGoalUpdate,
    P77CollectorProfileDashboardRead,
    P77CollectorProfileRead,
    P77CollectorProfileUpdate,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.schemas.p77_personalization import (
    P77PersonalizedDashboardRead,
    P77PersonalizedQuantityListResponse,
    P77PersonalizedRecommendationListResponse,
)
from app.services.p77_collector_profile_service import (
    build_collector_profile_dashboard,
    create_collector_goal,
    get_collector_budget,
    get_collector_profile,
    list_collector_goals,
    update_collector_budget,
    update_collector_goal,
    update_collector_profile,
)
from app.services.p77_personalization_service import (
    build_budget_status,
    build_personalized_dashboard,
    list_personalized_quantities,
    list_personalized_recommendations,
)
from app.services.p77_analytics_service import (
    build_analytics_dashboard,
    build_budget_analytics,
    build_goal_analytics,
    build_profile_analytics,
    build_recommendation_analytics_bundle,
)
from app.services.collector_profile_certification import run_collector_profile_certification
from app.schemas.p77_analytics import (
    P77AnalyticsDashboardRead,
    P77BudgetAnalyticsRead,
    P77CollectorAnalyticsRead,
    P77GoalAnalyticsRead,
    P77RecommendationAnalyticsRead,
)
from app.schemas.p77_certification import P77CollectorCertificationRead
from app.schemas.p91_collector_onboarding import (
    P91OnboardingCompleteRequest,
    P91OnboardingDraft,
    P91OnboardingDraftUpdate,
    P91OnboardingStatusRead,
)
from app.services.p91_collector_onboarding_service import (
    build_recommendation_preview,
    complete_onboarding,
    get_onboarding_status,
    normalize_onboarding_draft,
    save_onboarding_draft,
    search_interest_options,
    seed_draft_from_profile,
)

p77_collector_profile_v1_router = APIRouter(
    prefix="/api/v1/collector-profile",
    tags=["Collector Profile API v1 (P77-01)"],
)


def attach_p77_collector_profile_layer(app: FastAPI) -> None:
    app.include_router(p77_collector_profile_v1_router)


@p77_collector_profile_v1_router.get("", response_model=ScanApiV1Envelope)
def v1_get_collector_profile(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_collector_profile(session, owner_user_id=int(current_user.id))
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p77_collector_profile_v1_router.put("", response_model=ScanApiV1Envelope)
def v1_put_collector_profile(
    payload: P77CollectorProfileUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = update_collector_profile(session, owner_user_id=int(current_user.id), payload=payload)
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p77_collector_profile_v1_router.get("/onboarding", response_model=ScanApiV1Envelope)
def v1_get_collector_onboarding(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_onboarding_status(session, owner_user_id=int(current_user.id))
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p77_collector_profile_v1_router.get("/onboarding/status", response_model=ScanApiV1Envelope)
def v1_get_collector_onboarding_status_alias(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    return v1_get_collector_onboarding(session=session, current_user=current_user)


@p77_collector_profile_v1_router.put("/onboarding/draft", response_model=ScanApiV1Envelope)
def v1_put_collector_onboarding_draft(
    payload: P91OnboardingDraftUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = save_onboarding_draft(session, owner_user_id=int(current_user.id), draft=payload.draft)
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p77_collector_profile_v1_router.post("/onboarding/complete", response_model=ScanApiV1Envelope)
def v1_post_collector_onboarding_complete(
    payload: P91OnboardingCompleteRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = complete_onboarding(session, owner_user_id=int(current_user.id), draft=payload.draft)
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p77_collector_profile_v1_router.get("/onboarding/interest-options", response_model=ScanApiV1Envelope)
def v1_collector_onboarding_interest_options(
    kind: str = Query(..., pattern="^(PUBLISHER|CHARACTER|CREATOR)$"),
    q: str = Query("", max_length=120),
    limit: int = Query(40, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = search_interest_options(session, kind=kind, query=q, limit=limit, offset=offset)
    session.commit()
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@p77_collector_profile_v1_router.post("/onboarding/preview", response_model=ScanApiV1Envelope)
def v1_collector_onboarding_preview(
    payload: P91OnboardingDraft,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_recommendation_preview(normalize_onboarding_draft(payload))
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p77_collector_profile_v1_router.post("/onboarding/seed-from-profile", response_model=ScanApiV1Envelope)
def v1_collector_onboarding_seed_from_profile(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = seed_draft_from_profile(session, owner_user_id=int(current_user.id))
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p77_collector_profile_v1_router.get("/goals", response_model=ScanApiV1Envelope)
def v1_list_collector_goals(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_collector_goals(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    body = P77CollectorGoalListResponse(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@p77_collector_profile_v1_router.post("/goals", response_model=ScanApiV1Envelope, status_code=status.HTTP_201_CREATED)
def v1_create_collector_goal(
    payload: P77CollectorGoalCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = create_collector_goal(session, owner_user_id=int(current_user.id), payload=payload)
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p77_collector_profile_v1_router.put("/goals/{goal_id}", response_model=ScanApiV1Envelope)
def v1_update_collector_goal(
    goal_id: int,
    payload: P77CollectorGoalUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = update_collector_goal(session, owner_user_id=int(current_user.id), goal_id=goal_id, payload=payload)
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p77_collector_profile_v1_router.get("/budget", response_model=ScanApiV1Envelope)
def v1_get_collector_budget(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = get_collector_budget(session, owner_user_id=int(current_user.id))
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p77_collector_profile_v1_router.put("/budget", response_model=ScanApiV1Envelope)
def v1_put_collector_budget(
    payload: P77CollectorBudgetUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = update_collector_budget(session, owner_user_id=int(current_user.id), payload=payload)
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p77_collector_profile_v1_router.get("/recommendations", response_model=ScanApiV1Envelope)
def v1_personalized_recommendations(
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_personalized_recommendations(
        session,
        owner_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@p77_collector_profile_v1_router.get("/quantities", response_model=ScanApiV1Envelope)
def v1_personalized_quantities(
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = list_personalized_quantities(session, owner_user_id=int(current_user.id), limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@p77_collector_profile_v1_router.get("/budget-status", response_model=ScanApiV1Envelope)
def v1_collector_budget_status(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_budget_status(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@p77_collector_profile_v1_router.get("/personalized-dashboard", response_model=ScanApiV1Envelope)
def v1_personalized_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P77PersonalizedDashboardRead = build_personalized_dashboard(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@p77_collector_profile_v1_router.get("/analytics", response_model=ScanApiV1Envelope)
def v1_collector_analytics(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P77CollectorAnalyticsRead = build_profile_analytics(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@p77_collector_profile_v1_router.get("/budget-analytics", response_model=ScanApiV1Envelope)
def v1_collector_budget_analytics(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P77BudgetAnalyticsRead = build_budget_analytics(session, owner_user_id=int(current_user.id), persist=False)
    return wrap_object(body, owner_user_id=int(current_user.id))


@p77_collector_profile_v1_router.get("/goal-analytics", response_model=ScanApiV1Envelope)
def v1_collector_goal_analytics(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P77GoalAnalyticsRead = build_goal_analytics(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@p77_collector_profile_v1_router.get("/recommendation-analytics", response_model=ScanApiV1Envelope)
def v1_collector_recommendation_analytics(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P77RecommendationAnalyticsRead = build_recommendation_analytics_bundle(
        session,
        owner_user_id=int(current_user.id),
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@p77_collector_profile_v1_router.get("/analytics-dashboard", response_model=ScanApiV1Envelope)
def v1_collector_analytics_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P77AnalyticsDashboardRead = build_analytics_dashboard(
        session,
        owner_user_id=int(current_user.id),
        persist=True,
    )
    session.commit()
    return wrap_object(body, owner_user_id=int(current_user.id))


@p77_collector_profile_v1_router.get("/certification", response_model=ScanApiV1Envelope)
def v1_collector_profile_certification(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P77CollectorCertificationRead = run_collector_profile_certification(
        session,
        owner_user_id=int(current_user.id),
    )
    return wrap_object(body, owner_user_id=int(current_user.id))


@p77_collector_profile_v1_router.get("/dashboard", response_model=ScanApiV1Envelope)
def v1_collector_profile_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body: P77CollectorProfileDashboardRead = build_collector_profile_dashboard(
        session,
        owner_user_id=int(current_user.id),
    )
    return wrap_object(body, owner_user_id=int(current_user.id))
