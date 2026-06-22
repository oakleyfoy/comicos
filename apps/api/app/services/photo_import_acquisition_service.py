"""Photo import sessions → acquisitions (catalog-native intake, E2)."""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException, status
from sqlmodel import Session

from app.models import Acquisition, CatalogIssue
from app.models.acquisition import ACQUISITION_TYPE_OTHER
from app.models.photo_import import PhotoImportSession
from app.models.photo_import_vision_read import PhotoImportVisionRead, utc_now
from app.schemas.acquisition import AcquisitionCreatePayload
from app.services.acquisition.acquisition_inventory_service import create_received_catalog_copy
from app.services.acquisition.acquisition_service import create_acquisition, get_acquisition_or_404, require_open, recompute_actual_book_count
from app.services.photo_import_catalog_match_service import match_and_apply


def ensure_photo_import_session_acquisition(session: Session, import_row: PhotoImportSession) -> Acquisition:
    """One open acquisition per photo-import session (shared with detection confirm flow)."""
    if import_row.acquisition_id:
        return get_acquisition_or_404(
            session,
            owner_user_id=int(import_row.user_id),
            acquisition_id=int(import_row.acquisition_id),
        )
    acq_read = create_acquisition(
        session,
        owner_user_id=int(import_row.user_id),
        payload=AcquisitionCreatePayload(
            acquisition_type=ACQUISITION_TYPE_OTHER,
            purchase_date=date.today(),
            seller_name="Photo Import",
            notes="Photo Import session",
        ),
    )
    import_row.acquisition_id = int(acq_read.id)
    session.add(import_row)
    session.flush()
    return get_acquisition_or_404(
        session,
        owner_user_id=int(import_row.user_id),
        acquisition_id=int(acq_read.id),
    )


def create_catalog_copy_from_vision_read(
    session: Session,
    *,
    read: PhotoImportVisionRead,
    import_row: PhotoImportSession,
    owner_user_id: int,
    source_image_url: str | None = None,
) -> tuple[int, int]:
    """Create a catalog-spine inventory copy under the session acquisition (no legacy order rows)."""
    if int(import_row.user_id) != int(owner_user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    catalog_issue_id = read.catalog_issue_id
    if catalog_issue_id is None:
        match_and_apply(session, read)
        catalog_issue_id = read.catalog_issue_id
    if catalog_issue_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Choose or confirm a catalog match before adding to inventory",
        )

    issue = session.get(CatalogIssue, int(catalog_issue_id))
    if issue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalog issue not found")

    acquisition = ensure_photo_import_session_acquisition(session, import_row)
    require_open(acquisition)

    copy = create_received_catalog_copy(
        session,
        acquisition=acquisition,
        catalog_issue_id=int(catalog_issue_id),
        catalog_variant_id=read.catalog_variant_id,
        series_id=int(issue.series_id),
        issue_number=str(issue.issue_number or ""),
        source_image_url=source_image_url,
        received_via="PHOTO_IMPORT",
        received_at=utc_now(),
    )
    session.flush()
    recompute_actual_book_count(session, acquisition)
    session.add(acquisition)
    assert copy.id is not None
    assert acquisition.id is not None
    return int(acquisition.id), int(copy.id)
