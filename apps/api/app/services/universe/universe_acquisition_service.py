"""Create acquisition placeholders from master universe variant selection."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.models.acquisition import CATALOG_STATUS_PLACEHOLDER, AcquisitionPlaceholderIssue
from app.models.universe import AcquisitionUniverseLink, UniverseIssue, UniversePublisher, UniverseVariant, UniverseVolume
from app.schemas.acquisition import TreePlaceholderCreateResponse
from app.services.acquisition.acquisition_cost_allocation_service import recalc_if_even
from app.services.acquisition.acquisition_inventory_service import (
    VARIANT_STATUS_PLACEHOLDER,
    _create_copy,
    get_acquisition_or_404,
    require_open,
)
from app.services.acquisition.acquisition_service import build_acquisition_read, recompute_actual_book_count
from app.services.catalog_ingestion_service import normalize_issue_number


def create_placeholder_from_universe_variant(
    session: Session,
    *,
    owner_user_id: int,
    acquisition_id: int,
    universe_variant_id: int,
    quantity: int = 1,
) -> TreePlaceholderCreateResponse:
    acquisition = get_acquisition_or_404(session, owner_user_id=owner_user_id, acquisition_id=acquisition_id)
    require_open(acquisition)

    variant = session.get(UniverseVariant, universe_variant_id)
    if variant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Universe variant not found")
    issue = session.get(UniverseIssue, variant.issue_id)
    if issue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Universe issue not found")
    volume = session.get(UniverseVolume, issue.volume_id)
    publisher = session.get(UniversePublisher, volume.publisher_id) if volume else None

    issue_number = issue.issue_number
    norm = normalize_issue_number(issue_number)
    if volume:
        dup = session.exec(
            select(AcquisitionPlaceholderIssue).where(
                AcquisitionPlaceholderIssue.acquisition_id == acquisition_id,
                AcquisitionPlaceholderIssue.tree_linked.is_(True),
                AcquisitionPlaceholderIssue.source_volume_id == volume.comicvine_volume_id,
                AcquisitionPlaceholderIssue.issue_number == issue_number,
            )
        ).first()
        if dup is not None:
            return TreePlaceholderCreateResponse(
                created_count=0,
                skipped_count=1,
                acquisition=build_acquisition_read(session, acquisition),
            )

    pub_label = publisher.name if publisher else "Unknown"
    title = volume.name if volume else "Unknown volume"
    if volume and volume.start_year:
        title = f"{title} ({volume.start_year})"
    variant_label = variant.variant_name or variant.variant_type
    qty = max(1, min(100, int(quantity)))

    placeholder = AcquisitionPlaceholderIssue(
        acquisition_id=acquisition_id,
        user_id=owner_user_id,
        title=title,
        issue_number=issue_number,
        publisher=pub_label,
        quantity=qty,
        catalog_status=CATALOG_STATUS_PLACEHOLDER,
        comicvine_volume_id=volume.comicvine_volume_id if volume else None,
        source_volume_id=volume.comicvine_volume_id if volume else None,
        source_issue_id=str(variant.catalog_issue_id or issue.comicvine_issue_id or issue.id),
        tree_linked=True,
        variant_label=variant_label if variant_label not in ("UNKNOWN", "") else None,
        cover_type=variant.variant_type if variant.variant_type.startswith("COVER") else None,
    )
    session.add(placeholder)
    session.flush()
    session.add(
        AcquisitionUniverseLink(
            placeholder_id=int(placeholder.id or 0),
            universe_variant_id=universe_variant_id,
        )
    )

    created_ids: list[int] = []
    for index in range(qty):
        copy = _create_copy(
            session,
            acquisition=acquisition,
            catalog_issue_id=variant.catalog_issue_id,
            series_id=None,
            issue_number=issue_number or None,
            variant_status=VARIANT_STATUS_PLACEHOLDER,
            placeholder_issue_id=int(placeholder.id or 0),
            copy_number=index + 1,
        )
        label = f"{title} #{issue_number} {variant_label}".strip()
        copy.acquisition_notes = f"Universe picker: {label}"
        session.flush()
        created_ids.append(int(copy.id or 0))

    recompute_actual_book_count(session, acquisition)
    recalc_if_even(session, acquisition)
    session.add(acquisition)
    session.commit()
    session.refresh(acquisition)
    return TreePlaceholderCreateResponse(
        created_count=len(created_ids),
        skipped_count=0,
        acquisition=build_acquisition_read(session, acquisition),
    )
