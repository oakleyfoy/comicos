"""P98 Acquisition + catalog-browse API router."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.acquisition import (
    AcquisitionCreatePayload,
    AcquisitionDeleteResponse,
    AcquisitionItemsResponse,
    AcquisitionListResponse,
    AcquisitionRead,
    AcquisitionSourceAnalyticsResponse,
    AcquisitionUpdatePayload,
    AddBooksPayload,
    AddBooksResponse,
    AddGenericIssuePayload,
    AddPlaceholderIssuePayload,
    AllocatePayload,
    AllocateResponse,
    BulkRangePayload,
    BulkRangeResponse,
    IssueGridResponse,
    PublisherListResponse,
    SeriesListResponse,
    VariantPickerResult,
)
from app.services.acquisition.acquisition_inventory_service import (
    add_bulk_range,
    add_catalog_issues,
    add_generic_issue,
    add_placeholder_issue,
    delete_acquisition_item,
    list_acquisition_items,
    list_needs_review,
)
from app.services.acquisition.acquisition_service import (
    acquisition_source_analytics,
    allocate_acquisition,
    complete_acquisition,
    create_acquisition,
    delete_acquisition,
    get_acquisition,
    list_acquisitions,
    update_acquisition,
)
from app.services.acquisition.catalog_browse_service import (
    list_issue_variants,
    list_publishers,
    list_series_for_publisher,
    list_series_issue_grid,
)

acquisitions_v1_router = APIRouter(prefix="/api/v1", tags=["Acquisitions API v1 (P98)"])


def attach_acquisition_layer(app: FastAPI) -> None:
    app.include_router(acquisitions_v1_router)


# ----- Acquisition CRUD -----


@acquisitions_v1_router.post("/acquisitions", response_model=AcquisitionRead)
def create_acquisition_endpoint(
    payload: AcquisitionCreatePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> AcquisitionRead:
    assert current_user.id is not None
    return create_acquisition(session, owner_user_id=int(current_user.id), payload=payload)


@acquisitions_v1_router.get("/acquisitions", response_model=AcquisitionListResponse)
def list_acquisitions_endpoint(
    acquisition_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    seller: str | None = Query(default=None),
    search: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> AcquisitionListResponse:
    assert current_user.id is not None
    return list_acquisitions(
        session,
        owner_user_id=int(current_user.id),
        acquisition_type=acquisition_type,
        status_filter=status,
        seller=seller,
        search=search,
        date_from=date_from,
        date_to=date_to,
    )


@acquisitions_v1_router.get("/acquisitions/analytics/by-source", response_model=AcquisitionSourceAnalyticsResponse)
def acquisition_analytics_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> AcquisitionSourceAnalyticsResponse:
    assert current_user.id is not None
    return acquisition_source_analytics(session, owner_user_id=int(current_user.id))


@acquisitions_v1_router.get("/acquisitions/needs-review", response_model=AcquisitionItemsResponse)
def needs_review_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> AcquisitionItemsResponse:
    assert current_user.id is not None
    return list_needs_review(session, owner_user_id=int(current_user.id))


@acquisitions_v1_router.get("/acquisitions/{acquisition_id}", response_model=AcquisitionRead)
def get_acquisition_endpoint(
    acquisition_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> AcquisitionRead:
    assert current_user.id is not None
    return get_acquisition(session, owner_user_id=int(current_user.id), acquisition_id=acquisition_id)


@acquisitions_v1_router.patch("/acquisitions/{acquisition_id}", response_model=AcquisitionRead)
def update_acquisition_endpoint(
    acquisition_id: int,
    payload: AcquisitionUpdatePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> AcquisitionRead:
    assert current_user.id is not None
    return update_acquisition(
        session,
        owner_user_id=int(current_user.id),
        acquisition_id=acquisition_id,
        payload=payload,
    )


@acquisitions_v1_router.delete("/acquisitions/{acquisition_id}", response_model=AcquisitionDeleteResponse)
def delete_acquisition_endpoint(
    acquisition_id: int,
    delete_inventory: bool = Query(default=False),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> AcquisitionDeleteResponse:
    assert current_user.id is not None
    return delete_acquisition(
        session,
        owner_user_id=int(current_user.id),
        acquisition_id=acquisition_id,
        delete_inventory=delete_inventory,
    )


@acquisitions_v1_router.post("/acquisitions/{acquisition_id}/complete", response_model=AcquisitionRead)
def complete_acquisition_endpoint(
    acquisition_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> AcquisitionRead:
    assert current_user.id is not None
    return complete_acquisition(session, owner_user_id=int(current_user.id), acquisition_id=acquisition_id)


# ----- Items / add books -----


@acquisitions_v1_router.get("/acquisitions/{acquisition_id}/items", response_model=AcquisitionItemsResponse)
def list_items_endpoint(
    acquisition_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> AcquisitionItemsResponse:
    assert current_user.id is not None
    return list_acquisition_items(session, owner_user_id=int(current_user.id), acquisition_id=acquisition_id)


@acquisitions_v1_router.post("/acquisitions/{acquisition_id}/items", response_model=AddBooksResponse)
def add_items_endpoint(
    acquisition_id: int,
    payload: AddBooksPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> AddBooksResponse:
    assert current_user.id is not None
    return add_catalog_issues(
        session,
        owner_user_id=int(current_user.id),
        acquisition_id=acquisition_id,
        payload=payload,
    )


@acquisitions_v1_router.post("/acquisitions/{acquisition_id}/items/generic", response_model=AddBooksResponse)
def add_generic_endpoint(
    acquisition_id: int,
    payload: AddGenericIssuePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> AddBooksResponse:
    assert current_user.id is not None
    return add_generic_issue(
        session,
        owner_user_id=int(current_user.id),
        acquisition_id=acquisition_id,
        payload=payload,
    )


@acquisitions_v1_router.post(
    "/acquisitions/{acquisition_id}/placeholder-items", response_model=AddBooksResponse
)
def add_placeholder_endpoint(
    acquisition_id: int,
    payload: AddPlaceholderIssuePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> AddBooksResponse:
    assert current_user.id is not None
    return add_placeholder_issue(
        session,
        owner_user_id=int(current_user.id),
        acquisition_id=acquisition_id,
        payload=payload,
    )


@acquisitions_v1_router.post("/acquisitions/{acquisition_id}/items/bulk-range", response_model=BulkRangeResponse)
def bulk_range_endpoint(
    acquisition_id: int,
    payload: BulkRangePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> BulkRangeResponse:
    assert current_user.id is not None
    return add_bulk_range(
        session,
        owner_user_id=int(current_user.id),
        acquisition_id=acquisition_id,
        payload=payload,
    )


@acquisitions_v1_router.delete(
    "/acquisitions/{acquisition_id}/items/{inventory_copy_id}", response_model=AddBooksResponse
)
def delete_item_endpoint(
    acquisition_id: int,
    inventory_copy_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> AddBooksResponse:
    assert current_user.id is not None
    return delete_acquisition_item(
        session,
        owner_user_id=int(current_user.id),
        acquisition_id=acquisition_id,
        inventory_copy_id=inventory_copy_id,
    )


# ----- Cost allocation -----


@acquisitions_v1_router.post("/acquisitions/{acquisition_id}/allocate", response_model=AllocateResponse)
def allocate_endpoint(
    acquisition_id: int,
    payload: AllocatePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> AllocateResponse:
    assert current_user.id is not None
    return allocate_acquisition(
        session,
        owner_user_id=int(current_user.id),
        acquisition_id=acquisition_id,
        mode=payload.mode,
        manual=payload.manual,
    )


# ----- Catalog browse -----


@acquisitions_v1_router.get("/acquisitions/catalog/publishers", response_model=PublisherListResponse)
def catalog_publishers_endpoint(
    search: str | None = Query(default=None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PublisherListResponse:
    assert current_user.id is not None
    return list_publishers(session, owner_user_id=int(current_user.id), search=search)


@acquisitions_v1_router.get(
    "/acquisitions/catalog/publishers/{publisher_id}/series", response_model=SeriesListResponse
)
def catalog_series_endpoint(
    publisher_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> SeriesListResponse:
    assert current_user.id is not None
    return list_series_for_publisher(session, owner_user_id=int(current_user.id), publisher_id=publisher_id)


@acquisitions_v1_router.get(
    "/acquisitions/catalog/series/{series_id}/issues", response_model=IssueGridResponse
)
def catalog_issue_grid_endpoint(
    series_id: int,
    acquisition_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> IssueGridResponse:
    assert current_user.id is not None
    return list_series_issue_grid(
        session,
        owner_user_id=int(current_user.id),
        series_id=series_id,
        acquisition_id=acquisition_id,
    )


@acquisitions_v1_router.get(
    "/acquisitions/catalog/series/{series_id}/issue-number/{normalized_issue_number}/variants",
    response_model=VariantPickerResult,
)
def catalog_variants_endpoint(
    series_id: int,
    normalized_issue_number: str,
    acquisition_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> VariantPickerResult:
    assert current_user.id is not None
    return list_issue_variants(
        session,
        owner_user_id=int(current_user.id),
        series_id=series_id,
        normalized_issue_number=normalized_issue_number,
        acquisition_id=acquisition_id,
    )
