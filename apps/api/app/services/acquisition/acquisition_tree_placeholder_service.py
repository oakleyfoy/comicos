"""Create acquisition placeholders from the local catalog universe tree (no ComicVine API)."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.models.acquisition import (
    CATALOG_STATUS_PLACEHOLDER,
    AcquisitionPlaceholderIssue,
)
from app.models.catalog_master import CatalogSeries
from app.models.catalog_p97 import ComicVineVolumeUniverse
from app.schemas.acquisition import (
    TreePlaceholderCreateResponse,
    TreePlaceholderIssuePayload,
    TreePlaceholderRangePayload,
    TreePlaceholderRangePreviewResponse,
    TreeUnknownIssuePayload,
)
from app.services.acquisition.acquisition_cost_allocation_service import recalc_if_even
from app.services.acquisition.acquisition_inventory_service import (
    VARIANT_STATUS_PLACEHOLDER,
    _create_copy,
    get_acquisition_or_404,
    require_open,
)
from app.services.acquisition.acquisition_service import build_acquisition_read, recompute_actual_book_count
from app.services.catalog_ingestion_service import normalize_issue_number
from app.services.comicvine_catalog_importer import comicvine_volume_id_for_series


def resolve_volume_context(
    session: Session,
    *,
    volume_id: int,
    publisher: str,
) -> tuple[str, str, int | None]:
    """Return display title, series title, comicvine_volume_id."""
    publisher_label = (publisher or "").strip() or "Unknown"
    if volume_id < 0:
        series = session.get(CatalogSeries, -volume_id)
        if series is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Volume not found")
        title = series.name
        year = series.start_year
        cv_key = comicvine_volume_id_for_series(series)
        cv_id = int(cv_key) if cv_key and str(cv_key).isdigit() else None
    else:
        universe = session.exec(
            select(ComicVineVolumeUniverse).where(ComicVineVolumeUniverse.volume_id == volume_id)
        ).first()
        if universe is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Volume not found")
        title = universe.name
        year = universe.start_year
        cv_id = int(volume_id)
    display = f"{title} ({year})" if year else title
    return display, title, cv_id


def _volume_issue_keys(session: Session, acquisition_id: int) -> set[tuple[int, str]]:
    keys: set[tuple[int, str]] = set()
    for row in session.exec(
        select(AcquisitionPlaceholderIssue).where(
            AcquisitionPlaceholderIssue.acquisition_id == acquisition_id,
            AcquisitionPlaceholderIssue.tree_linked.is_(True),
        )
    ).all():
        if row.source_volume_id is None:
            continue
        norm = normalize_issue_number(row.issue_number or "")
        keys.add((int(row.source_volume_id), norm))
    return keys


def _create_tree_placeholder(
    session: Session,
    *,
    acquisition,
    owner_user_id: int,
    acquisition_id: int,
    title: str,
    issue_number: str,
    publisher: str,
    quantity: int,
    volume_id: int,
    comicvine_volume_id: int | None,
    source_issue_id: str | None,
) -> list[int]:
    placeholder = AcquisitionPlaceholderIssue(
        acquisition_id=acquisition_id,
        user_id=owner_user_id,
        title=title,
        issue_number=issue_number,
        publisher=publisher or None,
        quantity=quantity,
        catalog_status=CATALOG_STATUS_PLACEHOLDER,
        comicvine_volume_id=comicvine_volume_id,
        source_volume_id=volume_id,
        source_issue_id=source_issue_id,
        tree_linked=True,
    )
    session.add(placeholder)
    session.flush()

    created_ids: list[int] = []
    for index in range(quantity):
        copy = _create_copy(
            session,
            acquisition=acquisition,
            catalog_issue_id=None,
            series_id=None,
            issue_number=issue_number or None,
            variant_status=VARIANT_STATUS_PLACEHOLDER,
            placeholder_issue_id=int(placeholder.id or 0),
            copy_number=index + 1,
        )
        label = f"{title} #{issue_number}".strip() if issue_number else title
        copy.acquisition_notes = f"Tree placeholder: {label}"
        session.flush()
        created_ids.append(int(copy.id or 0))
    return created_ids


def create_tree_placeholder_issue(
    session: Session,
    *,
    owner_user_id: int,
    acquisition_id: int,
    payload: TreePlaceholderIssuePayload,
) -> TreePlaceholderCreateResponse:
    acquisition = get_acquisition_or_404(session, owner_user_id=owner_user_id, acquisition_id=acquisition_id)
    require_open(acquisition)

    issue_number = (payload.issue_number or "").strip()
    if not issue_number:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="issue_number is required")

    display_title, _series_title, cv_id = resolve_volume_context(
        session, volume_id=payload.volume_id, publisher=payload.publisher
    )
    norm = normalize_issue_number(issue_number)
    if (payload.volume_id, norm) in _volume_issue_keys(session, acquisition_id):
        return TreePlaceholderCreateResponse(
            created_count=0,
            skipped_count=1,
            acquisition=build_acquisition_read(session, acquisition),
        )

    source_issue_id = payload.source_issue_id or payload.issue_title or None
    qty = int(payload.quantity)
    created_ids = _create_tree_placeholder(
        session,
        acquisition=acquisition,
        owner_user_id=owner_user_id,
        acquisition_id=acquisition_id,
        title=display_title,
        issue_number=issue_number,
        publisher=payload.publisher.strip(),
        quantity=qty,
        volume_id=payload.volume_id,
        comicvine_volume_id=cv_id,
        source_issue_id=source_issue_id,
    )

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


def create_tree_unknown_issue(
    session: Session,
    *,
    owner_user_id: int,
    acquisition_id: int,
    payload: TreeUnknownIssuePayload,
) -> TreePlaceholderCreateResponse:
    acquisition = get_acquisition_or_404(session, owner_user_id=owner_user_id, acquisition_id=acquisition_id)
    require_open(acquisition)

    display_title, _series_title, cv_id = resolve_volume_context(
        session, volume_id=payload.volume_id, publisher=payload.publisher
    )
    created_ids = _create_tree_placeholder(
        session,
        acquisition=acquisition,
        owner_user_id=owner_user_id,
        acquisition_id=acquisition_id,
        title=display_title,
        issue_number="",
        publisher=payload.publisher.strip(),
        quantity=int(payload.quantity),
        volume_id=payload.volume_id,
        comicvine_volume_id=cv_id,
        source_issue_id=None,
    )

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


def preview_tree_placeholder_range(
    session: Session,
    *,
    owner_user_id: int,
    acquisition_id: int,
    payload: TreePlaceholderRangePayload,
) -> TreePlaceholderRangePreviewResponse:
    get_acquisition_or_404(session, owner_user_id=owner_user_id, acquisition_id=acquisition_id)
    if payload.end_issue < payload.start_issue:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="end_issue must be >= start_issue")

    existing = _volume_issue_keys(session, acquisition_id)
    to_create: list[str] = []
    skipped = 0
    for number in range(payload.start_issue, payload.end_issue + 1):
        num = str(number)
        norm = normalize_issue_number(num)
        if (payload.volume_id, norm) in existing:
            skipped += 1
            continue
        to_create.append(num)

    return TreePlaceholderRangePreviewResponse(
        will_create=len(to_create),
        skipped_existing=skipped,
        issue_numbers_to_create=to_create,
    )


def create_tree_placeholder_range(
    session: Session,
    *,
    owner_user_id: int,
    acquisition_id: int,
    payload: TreePlaceholderRangePayload,
) -> TreePlaceholderCreateResponse:
    preview = preview_tree_placeholder_range(
        session,
        owner_user_id=owner_user_id,
        acquisition_id=acquisition_id,
        payload=payload,
    )
    if preview.will_create == 0:
        acquisition = get_acquisition_or_404(session, owner_user_id=owner_user_id, acquisition_id=acquisition_id)
        return TreePlaceholderCreateResponse(
            created_count=0,
            skipped_count=preview.skipped_existing,
            acquisition=build_acquisition_read(session, acquisition),
        )

    acquisition = get_acquisition_or_404(session, owner_user_id=owner_user_id, acquisition_id=acquisition_id)
    require_open(acquisition)
    display_title, _series_title, cv_id = resolve_volume_context(
        session, volume_id=payload.volume_id, publisher=payload.publisher
    )

    created_total = 0
    for issue_number in preview.issue_numbers_to_create:
        ids = _create_tree_placeholder(
            session,
            acquisition=acquisition,
            owner_user_id=owner_user_id,
            acquisition_id=acquisition_id,
            title=display_title,
            issue_number=issue_number,
            publisher=payload.publisher.strip(),
            quantity=1,
            volume_id=payload.volume_id,
            comicvine_volume_id=cv_id,
            source_issue_id=None,
        )
        created_total += len(ids)

    recompute_actual_book_count(session, acquisition)
    recalc_if_even(session, acquisition)
    session.add(acquisition)
    session.commit()
    session.refresh(acquisition)

    return TreePlaceholderCreateResponse(
        created_count=created_total,
        skipped_count=preview.skipped_existing,
        acquisition=build_acquisition_read(session, acquisition),
    )
