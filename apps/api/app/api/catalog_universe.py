"""Read-only catalog universe tree API (local DB only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.acquisition import VariantPickerResult
from app.schemas.catalog_universe import (
    CatalogUniverseIssueListResponse,
    CatalogUniversePublisherListResponse,
    CatalogUniverseSearchResponse,
    CatalogUniverseVolumeListResponse,
)
from app.schemas.catalog_universe_placeholders import (
    LinkPlaceholderPayload,
    LinkPlaceholderResponse,
    PlaceholderMatchCandidatesResponse,
    PlaceholderQueueResponse,
)
from app.services.catalog_universe.catalog_universe_placeholder_service import (
    link_placeholder_to_catalog,
    list_unresolved_placeholders,
    match_candidates_for_placeholder,
)
from app.services.catalog_universe.catalog_universe_service import (
    list_issues_for_volume,
    list_universe_publishers,
    list_variants_for_volume_issue,
    list_volumes_for_publisher,
    search_universe,
)

catalog_universe_v1_router = APIRouter(prefix="/api/v1/catalog-universe", tags=["Catalog Universe (local DB)"])


def attach_catalog_universe_layer(app) -> None:
    app.include_router(catalog_universe_v1_router)


@catalog_universe_v1_router.get("/publishers", response_model=CatalogUniversePublisherListResponse)
def list_publishers_endpoint(
    search: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CatalogUniversePublisherListResponse:
    del current_user
    return list_universe_publishers(session, search=search, limit=limit, offset=offset)


@catalog_universe_v1_router.get(
    "/publishers/{publisher}/volumes",
    response_model=CatalogUniverseVolumeListResponse,
)
def list_publisher_volumes_endpoint(
    publisher: str,
    search: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CatalogUniverseVolumeListResponse:
    del current_user
    return list_volumes_for_publisher(
        session,
        publisher_path=publisher,
        search=search,
        limit=limit,
        offset=offset,
    )


@catalog_universe_v1_router.get(
    "/volumes/{volume_id}/issues",
    response_model=CatalogUniverseIssueListResponse,
)
def list_volume_issues_endpoint(
    volume_id: int,
    issue_number: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CatalogUniverseIssueListResponse:
    del current_user
    return list_issues_for_volume(
        session,
        volume_id=volume_id,
        issue_number=issue_number,
        limit=limit,
        offset=offset,
    )


@catalog_universe_v1_router.get(
    "/volumes/{volume_id}/issues/{issue_number}/variants",
    response_model=VariantPickerResult,
)
def list_volume_issue_variants_endpoint(
    volume_id: int,
    issue_number: str,
    acquisition_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> VariantPickerResult:
    assert current_user.id is not None
    return list_variants_for_volume_issue(
        session,
        volume_id=volume_id,
        issue_number=issue_number,
        owner_user_id=int(current_user.id),
        acquisition_id=acquisition_id,
    )


@catalog_universe_v1_router.get("/search", response_model=CatalogUniverseSearchResponse)
def search_catalog_universe_endpoint(
    q: str = Query(min_length=1),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CatalogUniverseSearchResponse:
    del current_user
    return search_universe(session, query=q, limit=limit, offset=offset)


@catalog_universe_v1_router.get("/placeholders", response_model=PlaceholderQueueResponse)
def list_placeholders_endpoint(
    search: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PlaceholderQueueResponse:
    assert current_user.id is not None
    return list_unresolved_placeholders(
        session,
        owner_user_id=int(current_user.id),
        search=search,
        limit=limit,
        offset=offset,
    )


@catalog_universe_v1_router.get(
    "/placeholders/{placeholder_id}/match-candidates",
    response_model=PlaceholderMatchCandidatesResponse,
)
def placeholder_match_candidates_endpoint(
    placeholder_id: int,
    q: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PlaceholderMatchCandidatesResponse:
    assert current_user.id is not None
    return match_candidates_for_placeholder(
        session,
        owner_user_id=int(current_user.id),
        placeholder_id=placeholder_id,
        manual_search=q,
        limit=limit,
    )


@catalog_universe_v1_router.post(
    "/placeholders/{placeholder_id}/link",
    response_model=LinkPlaceholderResponse,
)
def link_placeholder_endpoint(
    placeholder_id: int,
    payload: LinkPlaceholderPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> LinkPlaceholderResponse:
    assert current_user.id is not None
    return link_placeholder_to_catalog(
        session,
        owner_user_id=int(current_user.id),
        placeholder_id=placeholder_id,
        catalog_issue_id=payload.catalog_issue_id,
    )
