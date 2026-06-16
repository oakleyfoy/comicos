"""P98-11/10/13/17 manual inventory creation from catalog issues.

CONTRACT (P98-17): inventory copies created through this service MUST belong to
an Acquisition. Scanner/photo/barcode flows must route through an acquisition's
pending items rather than creating orphan inventory directly. This service is
the single supported path for manual catalog-issue inventory creation.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlmodel import Session, select

from app.models import Acquisition, CatalogIssue, CatalogSeries, InventoryCopy
from app.models.acquisition import ACQUISITION_TYPE_UNKNOWN
from app.schemas.acquisition import (
    AcquisitionItemRead,
    AcquisitionItemsResponse,
    AddBooksItem,
    AddBooksPayload,
    AddBooksResponse,
    AddBooksResultItem,
    AddGenericIssuePayload,
    BulkRangeNeedsVariant,
    BulkRangePayload,
    BulkRangeResponse,
)
from app.services.acquisition.acquisition_cost_allocation_service import (
    quantize_money,
    recalc_if_even,
)
from app.services.acquisition.acquisition_service import (
    build_acquisition_read,
    get_acquisition_or_404,
    recompute_actual_book_count,
    require_open,
)
from app.services.catalog_ingestion_service import normalize_issue_number
from app.services.recognition.catalog_matcher import load_catalog_issue_identity

VARIANT_STATUS_RESOLVED = "RESOLVED"
VARIANT_STATUS_UNKNOWN = "UNKNOWN"
RECEIVED_VIA_ACQUISITION = "ACQUISITION_MANUAL"


def _identity_key(session: Session, catalog_issue_id: int) -> str | None:
    identity = load_catalog_issue_identity(session, catalog_issue_id)
    if identity is None:
        return None
    return "|".join(
        [
            (identity.publisher or ""),
            (identity.series or ""),
            (identity.issue_number or ""),
            "",
        ]
    )


def _next_copy_number(session: Session, acquisition_id: int, catalog_issue_id: int | None) -> int:
    existing = session.exec(
        select(func.count(InventoryCopy.id)).where(
            InventoryCopy.acquisition_id == acquisition_id,
            InventoryCopy.catalog_issue_id == catalog_issue_id,
        )
    ).one()
    return int(existing or 0) + 1


def _create_copy(
    session: Session,
    *,
    acquisition: Acquisition,
    catalog_issue_id: int | None,
    series_id: int | None,
    issue_number: str | None,
    variant_status: str,
) -> InventoryCopy:
    identity_key = _identity_key(session, catalog_issue_id) if catalog_issue_id else None
    copy = InventoryCopy(
        user_id=acquisition.user_id,
        acquisition_id=acquisition.id,
        catalog_issue_id=catalog_issue_id,
        canonical_series_id=None,
        copy_number=_next_copy_number(session, int(acquisition.id or 0), catalog_issue_id),
        acquisition_cost=Decimal("0.00"),
        variant_status=variant_status,
        metadata_identity_key=identity_key,
        order_status="received",
        received_at=None,
        received_via=RECEIVED_VIA_ACQUISITION,
        acquisition_source_type=acquisition.acquisition_type or ACQUISITION_TYPE_UNKNOWN,
        acquisition_source_name=acquisition.seller_name,
    )
    session.add(copy)
    return copy


def add_catalog_issues(
    session: Session,
    *,
    owner_user_id: int,
    acquisition_id: int,
    payload: AddBooksPayload,
) -> AddBooksResponse:
    acquisition = get_acquisition_or_404(session, owner_user_id=owner_user_id, acquisition_id=acquisition_id)
    require_open(acquisition)

    results: list[AddBooksResultItem] = []
    duplicates: list[int] = []
    created_total = 0

    for item in payload.items:
        issue = session.get(CatalogIssue, item.catalog_issue_id)
        if issue is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Catalog issue {item.catalog_issue_id} not found")

        already = session.exec(
            select(func.count(InventoryCopy.id)).where(
                InventoryCopy.acquisition_id == acquisition_id,
                InventoryCopy.catalog_issue_id == item.catalog_issue_id,
            )
        ).one()
        already_added = int(already or 0) > 0

        if already_added and not payload.force_duplicate:
            duplicates.append(item.catalog_issue_id)
            results.append(
                AddBooksResultItem(
                    catalog_issue_id=item.catalog_issue_id,
                    created_count=0,
                    already_added=True,
                    inventory_copy_ids=[],
                )
            )
            continue

        qty = max(1, int(item.quantity or 1))
        created_ids: list[int] = []
        for _ in range(qty):
            copy = _create_copy(
                session,
                acquisition=acquisition,
                catalog_issue_id=item.catalog_issue_id,
                series_id=issue.series_id,
                issue_number=issue.issue_number,
                variant_status=VARIANT_STATUS_RESOLVED,
            )
            session.flush()
            created_ids.append(int(copy.id or 0))
        created_total += qty
        results.append(
            AddBooksResultItem(
                catalog_issue_id=item.catalog_issue_id,
                created_count=qty,
                already_added=already_added,
                inventory_copy_ids=created_ids,
            )
        )

    recompute_actual_book_count(session, acquisition)
    recalc_if_even(session, acquisition)
    session.add(acquisition)
    session.commit()
    session.refresh(acquisition)

    return AddBooksResponse(
        created_count=created_total,
        results=results,
        duplicate_catalog_issue_ids=duplicates,
        acquisition=build_acquisition_read(session, acquisition),
    )


def add_generic_issue(
    session: Session,
    *,
    owner_user_id: int,
    acquisition_id: int,
    payload: AddGenericIssuePayload,
) -> AddBooksResponse:
    """P98-13 'Not Sure / Add Generic Issue' -> Needs Review queue."""
    acquisition = get_acquisition_or_404(session, owner_user_id=owner_user_id, acquisition_id=acquisition_id)
    require_open(acquisition)
    series = session.get(CatalogSeries, payload.series_id)
    if series is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Series not found")

    qty = max(1, int(payload.quantity or 1))
    created_ids: list[int] = []
    for _ in range(qty):
        copy = _create_copy(
            session,
            acquisition=acquisition,
            catalog_issue_id=None,
            series_id=payload.series_id,
            issue_number=payload.issue_number,
            variant_status=VARIANT_STATUS_UNKNOWN,
        )
        # capture the series/issue context for later resolution
        copy.metadata_identity_key = "|".join(["", series.name or "", payload.issue_number or "", ""])
        copy.acquisition_notes = f"Generic add: {series.name} #{payload.issue_number}"
        session.flush()
        created_ids.append(int(copy.id or 0))

    recompute_actual_book_count(session, acquisition)
    recalc_if_even(session, acquisition)
    session.add(acquisition)
    session.commit()
    session.refresh(acquisition)

    return AddBooksResponse(
        created_count=qty,
        results=[
            AddBooksResultItem(
                catalog_issue_id=0,
                created_count=qty,
                already_added=False,
                inventory_copy_ids=created_ids,
            )
        ],
        duplicate_catalog_issue_ids=[],
        acquisition=build_acquisition_read(session, acquisition),
    )


def add_bulk_range(
    session: Session,
    *,
    owner_user_id: int,
    acquisition_id: int,
    payload: BulkRangePayload,
) -> BulkRangeResponse:
    """P98-10 bulk range: add single-cover issues immediately, defer multi-cover."""
    acquisition = get_acquisition_or_404(session, owner_user_id=owner_user_id, acquisition_id=acquisition_id)
    require_open(acquisition)
    series = session.get(CatalogSeries, payload.series_id)
    if series is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Series not found")
    if payload.end_issue < payload.start_issue:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="end_issue must be >= start_issue")

    added_count = 0
    needs_variant: list[BulkRangeNeedsVariant] = []

    for number in range(payload.start_issue, payload.end_issue + 1):
        normalized = normalize_issue_number(str(number))
        issues = list(
            session.exec(
                select(CatalogIssue).where(
                    CatalogIssue.series_id == payload.series_id,
                    CatalogIssue.normalized_issue_number == normalized,
                )
            ).all()
        )
        if not issues:
            continue
        # skip already-added in this acquisition
        issue_ids = [int(i.id or 0) for i in issues]
        existing = session.exec(
            select(func.count(InventoryCopy.id)).where(
                InventoryCopy.acquisition_id == acquisition_id,
                InventoryCopy.catalog_issue_id.in_(issue_ids),
            )
        ).one()
        if int(existing or 0) > 0:
            continue

        if len(issues) == 1:
            self_issue = issues[0]
            _create_copy(
                session,
                acquisition=acquisition,
                catalog_issue_id=int(self_issue.id or 0),
                series_id=self_issue.series_id,
                issue_number=self_issue.issue_number,
                variant_status=VARIANT_STATUS_RESOLVED,
            )
            added_count += 1
            continue

        # multi-cover number
        if payload.variant_resolution == "cover_a":
            chosen = sorted(issues, key=lambda i: int(i.id or 0))[0]
            _create_copy(
                session,
                acquisition=acquisition,
                catalog_issue_id=int(chosen.id or 0),
                series_id=chosen.series_id,
                issue_number=chosen.issue_number,
                variant_status=VARIANT_STATUS_RESOLVED,
            )
            added_count += 1
        elif payload.variant_resolution == "generic":
            rep = issues[0]
            copy = _create_copy(
                session,
                acquisition=acquisition,
                catalog_issue_id=None,
                series_id=payload.series_id,
                issue_number=rep.issue_number,
                variant_status=VARIANT_STATUS_UNKNOWN,
            )
            copy.metadata_identity_key = "|".join(["", series.name or "", rep.issue_number or "", ""])
            added_count += 1
        else:  # review
            needs_variant.append(
                BulkRangeNeedsVariant(issue_number=issues[0].issue_number, cover_count=len(issues))
            )

    recompute_actual_book_count(session, acquisition)
    recalc_if_even(session, acquisition)
    session.add(acquisition)
    session.commit()
    session.refresh(acquisition)

    return BulkRangeResponse(
        added_count=added_count,
        needs_variant=needs_variant,
        acquisition=build_acquisition_read(session, acquisition),
    )


def _item_read(session: Session, copy: InventoryCopy) -> AcquisitionItemRead:
    series_name: str | None = None
    issue_number: str | None = None
    publisher: str | None = None
    cover_url: str | None = None
    variant_label: str | None = None
    if copy.catalog_issue_id is not None:
        identity = load_catalog_issue_identity(session, int(copy.catalog_issue_id))
        if identity is not None:
            series_name = identity.series
            issue_number = identity.issue_number
            publisher = identity.publisher
            cover_url = identity.cover_image_url
    if series_name is None and copy.metadata_identity_key:
        parts = copy.metadata_identity_key.split("|")
        parts += [""] * (4 - len(parts))
        publisher = publisher or (parts[0] or None)
        series_name = series_name or (parts[1] or None)
        issue_number = issue_number or (parts[2] or None)
        variant_label = parts[3] or None
    return AcquisitionItemRead(
        inventory_copy_id=int(copy.id or 0),
        acquisition_id=int(copy.acquisition_id or 0),
        catalog_issue_id=copy.catalog_issue_id,
        series=series_name,
        issue_number=issue_number,
        publisher=publisher,
        cover_image_url=cover_url,
        variant_label=variant_label,
        variant_status=copy.variant_status,
        cost_basis=quantize_money(copy.acquisition_cost),
        copy_number=copy.copy_number,
    )


def list_acquisition_items(
    session: Session,
    *,
    owner_user_id: int,
    acquisition_id: int,
) -> AcquisitionItemsResponse:
    get_acquisition_or_404(session, owner_user_id=owner_user_id, acquisition_id=acquisition_id)
    copies = list(
        session.exec(
            select(InventoryCopy)
            .where(InventoryCopy.acquisition_id == acquisition_id)
            .order_by(InventoryCopy.id.asc())
        ).all()
    )
    items = [_item_read(session, copy) for copy in copies]
    return AcquisitionItemsResponse(items=items, total=len(items))


def delete_acquisition_item(
    session: Session,
    *,
    owner_user_id: int,
    acquisition_id: int,
    inventory_copy_id: int,
) -> AddBooksResponse:
    acquisition = get_acquisition_or_404(session, owner_user_id=owner_user_id, acquisition_id=acquisition_id)
    require_open(acquisition)
    copy = session.get(InventoryCopy, inventory_copy_id)
    if copy is None or copy.acquisition_id != acquisition_id or copy.user_id != owner_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory copy not found")
    session.delete(copy)
    session.flush()
    recompute_actual_book_count(session, acquisition)
    recalc_if_even(session, acquisition)
    session.add(acquisition)
    session.commit()
    session.refresh(acquisition)
    return AddBooksResponse(
        created_count=0,
        results=[],
        duplicate_catalog_issue_ids=[],
        acquisition=build_acquisition_read(session, acquisition),
    )


def list_needs_review(
    session: Session,
    *,
    owner_user_id: int,
) -> AcquisitionItemsResponse:
    """P98-13 Needs Review queue: copies missing exact catalog/variant resolution."""
    copies = list(
        session.exec(
            select(InventoryCopy)
            .where(
                InventoryCopy.user_id == owner_user_id,
                InventoryCopy.variant_status == VARIANT_STATUS_UNKNOWN,
            )
            .order_by(InventoryCopy.id.asc())
        ).all()
    )
    items = [_item_read(session, copy) for copy in copies]
    return AcquisitionItemsResponse(items=items, total=len(items))
