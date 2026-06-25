"""P98 Master Universe tree API (reference skeleton, not catalog)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.acquisition import TreePlaceholderCreateResponse
from app.schemas.master_universe import (
    MasterUniverseIssueListResponse,
    MasterUniversePublisherListResponse,
    MasterUniverseSearchResponse,
    MasterUniverseVariantListResponse,
    MasterUniverseVolumeListResponse,
)
from app.schemas.master_universe_catalog_dashboard import MasterUniverseCatalogDashboardResponse
from app.services.universe.master_universe_catalog_dashboard_service import get_master_universe_catalog_dashboard
from app.services.universe.universe_acquisition_service import create_placeholder_from_universe_variant
from app.services.universe.universe_issue_service import list_issues_for_volume, list_variants_for_issue
from app.services.universe.universe_publisher_service import list_publishers
from app.services.universe.universe_tree_service import search_master_universe
from app.services.universe.universe_volume_service import list_volumes_for_publisher

master_universe_v1_router = APIRouter(prefix="/api/v1/universe", tags=["Master Universe (P98)"])


def attach_master_universe_layer(app) -> None:
    app.include_router(master_universe_v1_router)


@master_universe_v1_router.get("/catalog-dashboard", response_model=MasterUniverseCatalogDashboardResponse)
def master_universe_catalog_dashboard_endpoint(
    search: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MasterUniverseCatalogDashboardResponse:
    assert current_user.id is not None
    return get_master_universe_catalog_dashboard(
        session,
        owner_user_id=int(current_user.id),
        search=search,
        limit=limit,
        offset=offset,
    )


@master_universe_v1_router.get("/publishers", response_model=MasterUniversePublisherListResponse)
def list_universe_publishers_endpoint(
    search: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MasterUniversePublisherListResponse:
    del current_user
    return list_publishers(session, search=search, limit=limit, offset=offset)


@master_universe_v1_router.get(
    "/publishers/{publisher_id}/volumes",
    response_model=MasterUniverseVolumeListResponse,
)
def list_universe_volumes_endpoint(
    publisher_id: int,
    search: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MasterUniverseVolumeListResponse:
    del current_user
    return list_volumes_for_publisher(
        session,
        publisher_id=publisher_id,
        search=search,
        limit=limit,
        offset=offset,
    )


@master_universe_v1_router.get(
    "/volumes/{volume_id}/issues",
    response_model=MasterUniverseIssueListResponse,
)
def list_universe_issues_endpoint(
    volume_id: int,
    issue_number: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MasterUniverseIssueListResponse:
    del current_user
    return list_issues_for_volume(
        session,
        volume_id=volume_id,
        issue_number=issue_number,
        limit=limit,
        offset=offset,
    )


@master_universe_v1_router.get(
    "/issues/{issue_id}/variants",
    response_model=MasterUniverseVariantListResponse,
)
def list_universe_variants_endpoint(
    issue_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MasterUniverseVariantListResponse:
    del current_user
    return list_variants_for_issue(session, issue_id=issue_id, limit=limit, offset=offset)


@master_universe_v1_router.get("/search", response_model=MasterUniverseSearchResponse)
def search_universe_endpoint(
    q: str = Query(min_length=1),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MasterUniverseSearchResponse:
    del current_user
    return search_master_universe(session, query=q, limit=limit, offset=offset)


class UniverseAcquisitionPayload(BaseModel):
    universe_variant_id: int
    quantity: int = Field(default=1, ge=1, le=100)


@master_universe_v1_router.post(
    "/acquisitions/{acquisition_id}/placeholders",
    response_model=TreePlaceholderCreateResponse,
)
def create_universe_placeholder_endpoint(
    acquisition_id: int,
    payload: UniverseAcquisitionPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> TreePlaceholderCreateResponse:
    assert current_user.id is not None
    return create_placeholder_from_universe_variant(
        session,
        owner_user_id=int(current_user.id),
        acquisition_id=acquisition_id,
        universe_variant_id=payload.universe_variant_id,
        quantity=payload.quantity,
    )
