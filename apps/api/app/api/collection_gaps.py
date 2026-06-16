from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.collection_gap import CollectionGapListRead, CollectionGapSummaryRead
from app.schemas.collection_gap_builder import (
    CollectionGapIssuesResponse,
    CollectionGapPublishersResponse,
    CollectionGapVolumesResponse,
    CollectionGapYearsResponse,
    WantListTargetCreatePayload,
    WantListTargetCreateResponse,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object, wrap_standard_list
from app.services.collection_gap_service import (
    create_wantlist_targets,
    list_gap_issues_for_volume_year,
    list_gap_publishers_for_year,
    list_gap_volumes_for_publisher_year,
    list_gap_years,
)
from app.services.collection_gaps import (
    build_collection_gap_summary,
    list_collection_gaps,
    refresh_and_list_latest_collection_gaps,
)

collection_gap_v1_router = APIRouter(prefix="/api/v1", tags=["Collection Gaps API v1 (P55-02)"])


def attach_collection_gap_layer(app: FastAPI) -> None:
    app.include_router(collection_gap_v1_router)


@collection_gap_v1_router.get("/collection-gaps", response_model=ScanApiV1Envelope)
def v1_list_collection_gaps(
    priority: str | None = None,
    gap_type: str | None = None,
    publisher: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = list_collection_gaps(
        session,
        owner_user_id=int(current_user.id),
        priority=priority,
        gap_type=gap_type,
        publisher=publisher,
        limit=limit,
        offset=offset,
    )
    body = CollectionGapListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@collection_gap_v1_router.get("/collection-gaps/latest", response_model=ScanApiV1Envelope)
def v1_list_latest_collection_gaps(
    priority: str | None = None,
    gap_type: str | None = None,
    publisher: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    items, total = refresh_and_list_latest_collection_gaps(
        session,
        owner_user_id=int(current_user.id),
        priority=priority,
        gap_type=gap_type,
        publisher=publisher,
        limit=limit,
        offset=offset,
    )
    body = CollectionGapListRead(items=items, total_items=total, limit=limit, offset=offset)
    return wrap_standard_list(body, owner_user_id=int(current_user.id))


@collection_gap_v1_router.get("/collection-gaps/summary", response_model=ScanApiV1Envelope)
def v1_collection_gap_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanApiV1Envelope:
    assert current_user.id is not None
    body = build_collection_gap_summary(session, owner_user_id=int(current_user.id))
    return wrap_object(body, owner_user_id=int(current_user.id))


@collection_gap_v1_router.get("/collection-gaps/years", response_model=CollectionGapYearsResponse)
def collection_gap_years_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CollectionGapYearsResponse:
    assert current_user.id is not None
    return list_gap_years(session, owner_user_id=int(current_user.id))


@collection_gap_v1_router.get(
    "/collection-gaps/years/{year}/publishers",
    response_model=CollectionGapPublishersResponse,
)
def collection_gap_publishers_endpoint(
    year: int,
    priority_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CollectionGapPublishersResponse:
    assert current_user.id is not None
    return list_gap_publishers_for_year(
        session,
        owner_user_id=int(current_user.id),
        year=year,
        limit=limit,
        offset=offset,
        priority_only=priority_only,
    )


@collection_gap_v1_router.get(
    "/collection-gaps/publishers/{publisher}/volumes",
    response_model=CollectionGapVolumesResponse,
)
def collection_gap_volumes_endpoint(
    publisher: str,
    year: int = Query(default=2025, ge=1900, le=2100),
    incomplete_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CollectionGapVolumesResponse:
    assert current_user.id is not None
    return list_gap_volumes_for_publisher_year(
        session,
        owner_user_id=int(current_user.id),
        publisher_path=publisher,
        year=year,
        limit=limit,
        offset=offset,
        incomplete_only=incomplete_only,
    )


@collection_gap_v1_router.get(
    "/collection-gaps/volumes/{volume_id}/issues",
    response_model=CollectionGapIssuesResponse,
)
def collection_gap_issues_endpoint(
    volume_id: int,
    year: int = Query(default=2025, ge=1900, le=2100),
    gap_status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CollectionGapIssuesResponse:
    assert current_user.id is not None
    return list_gap_issues_for_volume_year(
        session,
        owner_user_id=int(current_user.id),
        volume_id=volume_id,
        year=year,
        limit=limit,
        offset=offset,
        gap_status_filter=gap_status,
    )


@collection_gap_v1_router.post(
    "/collection-gaps/wantlist-targets",
    response_model=WantListTargetCreateResponse,
)
def collection_gap_wantlist_targets_endpoint(
    payload: WantListTargetCreatePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> WantListTargetCreateResponse:
    assert current_user.id is not None
    return create_wantlist_targets(
        session,
        owner_user_id=int(current_user.id),
        payload=payload,
    )
