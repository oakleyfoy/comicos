"""Bulk placeholder range preview/create from universe tree (local DB only)."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlmodel import Session, select

from app.models.acquisition import AcquisitionPlaceholderIssue, CATALOG_STATUS_PLACEHOLDER
from app.models.asset_ledger import InventoryCopy
from app.models.catalog_master import CatalogIssue
from app.schemas.acquisition import (
    AddBooksItem,
    AddBooksPayload,
    PlaceholderRangeCreateResponse,
    PlaceholderRangePreviewPayload,
    PlaceholderRangePreviewResponse,
    TreePlaceholderRangePayload,
    TreePlaceholderRangePreviewResponse,
)
from app.services.acquisition.acquisition_inventory_service import add_catalog_issues
from app.services.acquisition.acquisition_service import build_acquisition_read, get_acquisition_or_404
from app.services.acquisition.acquisition_tree_placeholder_service import (
    _volume_issue_keys,
    resolve_volume_context,
)
from app.services.catalog_ingestion_service import normalize_issue_number
from app.services.catalog_universe.catalog_universe_service import build_volume_to_series_ids


@dataclass(frozen=True)
class _VariantFields:
    variant_label: str | None
    cover_type: str | None
    printing: str | None
    ratio_variant: str | None
    barcode: str | None
    cover_artist: str | None
    raw_variant_notes: str | None


def _parse_excludes(raw: list[str]) -> set[str]:
    out: set[str] = set()
    for entry in raw:
        for part in entry.replace(";", ",").split(","):
            token = part.strip()
            if token:
                out.add(normalize_issue_number(token))
    return out


def _variant_fields(payload: PlaceholderRangePreviewPayload) -> _VariantFields:
    return _VariantFields(
        variant_label=payload.variant_label,
        cover_type=payload.cover_type,
        printing=payload.printing,
        ratio_variant=payload.ratio_variant,
        barcode=payload.barcode,
        cover_artist=payload.cover_artist,
        raw_variant_notes=payload.raw_variant_notes or payload.notes,
    )


def _existing_catalog_issue_ids_in_acquisition(session: Session, acquisition_id: int) -> set[int]:
    rows = session.exec(
        select(InventoryCopy.catalog_issue_id).where(
            InventoryCopy.acquisition_id == acquisition_id,
            InventoryCopy.catalog_issue_id.is_not(None),
        )
    ).all()
    return {int(r) for r in rows if r is not None}


def _single_catalog_issue_for_number(
    session: Session, series_ids: list[int], issue_number: str
) -> CatalogIssue | None:
    if not series_ids:
        return None
    normalized = normalize_issue_number(issue_number)
    issues = list(
        session.exec(
            select(CatalogIssue).where(
                CatalogIssue.series_id.in_(series_ids),
                CatalogIssue.normalized_issue_number == normalized,
            )
        ).all()
    )
    if len(issues) == 1:
        return issues[0]
    return None


def _plan_range(
    session: Session,
    *,
    owner_user_id: int,
    acquisition_id: int,
    payload: PlaceholderRangePreviewPayload,
) -> PlaceholderRangePreviewResponse:
    get_acquisition_or_404(session, owner_user_id=owner_user_id, acquisition_id=acquisition_id)
    if payload.end_issue < payload.start_issue:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="end_issue must be >= start_issue")

    excludes = _parse_excludes(payload.exclude_issues)
    series_ids = build_volume_to_series_ids(session).get(payload.volume_id, [])
    if payload.volume_id < 0:
        series_ids = [-payload.volume_id]

    tree_keys = _volume_issue_keys(session, acquisition_id)
    catalog_in_acq = _existing_catalog_issue_ids_in_acquisition(session, acquisition_id)

    total_in_range = 0
    excluded_count = 0
    already_in_acquisition = 0
    catalog_to_add: list[int] = []
    placeholder_numbers: list[str] = []
    skipped_duplicates = 0

    for number in range(payload.start_issue, payload.end_issue + 1):
        total_in_range += 1
        num = str(number)
        norm = normalize_issue_number(num)
        if norm in excludes:
            excluded_count += 1
            continue

        if (payload.volume_id, norm) in tree_keys:
            already_in_acquisition += 1
            skipped_duplicates += 1
            continue

        catalog_issue = _single_catalog_issue_for_number(session, series_ids, num)
        if catalog_issue is not None and payload.prefer_catalog and not payload.variant_label:
            cid = int(catalog_issue.id or 0)
            if cid in catalog_in_acq:
                already_in_acquisition += 1
                skipped_duplicates += 1
                continue
            catalog_to_add.append(cid)
            continue

        placeholder_numbers.append(num)

    return PlaceholderRangePreviewResponse(
        total_issues_in_range=total_in_range,
        excluded_count=excluded_count,
        already_in_acquisition=already_in_acquisition,
        catalog_items_to_add=len(catalog_to_add),
        placeholders_to_create=len(placeholder_numbers),
        skipped_duplicates=skipped_duplicates,
        catalog_issue_ids=catalog_to_add,
        placeholder_issue_numbers=placeholder_numbers,
    )


def preview_placeholder_range(
    session: Session,
    *,
    owner_user_id: int,
    acquisition_id: int,
    payload: PlaceholderRangePreviewPayload,
) -> PlaceholderRangePreviewResponse:
    return _plan_range(
        session,
        owner_user_id=owner_user_id,
        acquisition_id=acquisition_id,
        payload=payload,
    )


def create_placeholder_range(
    session: Session,
    *,
    owner_user_id: int,
    acquisition_id: int,
    payload: PlaceholderRangePreviewPayload,
) -> PlaceholderRangeCreateResponse:
    from app.services.acquisition.acquisition_cost_allocation_service import recalc_if_even
    from app.services.acquisition.acquisition_inventory_service import get_acquisition_or_404, require_open
    from app.services.acquisition.acquisition_service import recompute_actual_book_count

    plan = _plan_range(
        session,
        owner_user_id=owner_user_id,
        acquisition_id=acquisition_id,
        payload=payload,
    )
    acquisition = get_acquisition_or_404(session, owner_user_id=owner_user_id, acquisition_id=acquisition_id)
    require_open(acquisition)

    catalog_created = 0
    acquisition_read = None
    if plan.catalog_issue_ids:
        qty = int(payload.quantity_per_issue)
        add_resp = add_catalog_issues(
            session,
            owner_user_id=owner_user_id,
            acquisition_id=acquisition_id,
            payload=AddBooksPayload(
                items=[
                    AddBooksItem(catalog_issue_id=cid, quantity=qty)
                    for cid in plan.catalog_issue_ids
                ],
                force_duplicate=False,
            ),
        )
        catalog_created = int(add_resp.created_count)
        acquisition_read = add_resp.acquisition

    placeholder_created = 0
    if plan.placeholder_issue_numbers:
        display_title, _title, cv_id = resolve_volume_context(
            session, volume_id=payload.volume_id, publisher=payload.publisher
        )
        variants = _variant_fields(payload)
        acquisition = get_acquisition_or_404(session, owner_user_id=owner_user_id, acquisition_id=acquisition_id)
        require_open(acquisition)
        for issue_number in plan.placeholder_issue_numbers:
            ids = _create_tree_placeholder_with_variants(
                session,
                acquisition=acquisition,
                owner_user_id=owner_user_id,
                acquisition_id=acquisition_id,
                title=display_title,
                issue_number=issue_number,
                publisher=payload.publisher.strip(),
                quantity=int(payload.quantity_per_issue),
                volume_id=payload.volume_id,
                comicvine_volume_id=cv_id,
                source_issue_id=None,
                variants=variants,
            )
            placeholder_created += len(ids)
        recompute_actual_book_count(session, acquisition)
        recalc_if_even(session, acquisition)
        session.add(acquisition)
        session.commit()
        session.refresh(acquisition)
        acquisition_read = build_acquisition_read(session, acquisition)

    if acquisition_read is None:
        acquisition = get_acquisition_or_404(session, owner_user_id=owner_user_id, acquisition_id=acquisition_id)
        acquisition_read = build_acquisition_read(session, acquisition)

    return PlaceholderRangeCreateResponse(
        catalog_created=catalog_created,
        placeholder_created=placeholder_created,
        skipped_duplicates=plan.skipped_duplicates,
        acquisition=acquisition_read,
    )


def _create_tree_placeholder_with_variants(
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
    variants: _VariantFields,
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
        variant_label=variants.variant_label,
        cover_type=variants.cover_type,
        printing=variants.printing,
        ratio_variant=variants.ratio_variant,
        barcode=variants.barcode,
        cover_artist=variants.cover_artist,
        raw_variant_notes=variants.raw_variant_notes,
    )
    session.add(placeholder)
    session.flush()

    from app.services.acquisition.acquisition_inventory_service import VARIANT_STATUS_PLACEHOLDER, _create_copy

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
        if variants.variant_label:
            label = f"{label} ({variants.variant_label})"
        copy.acquisition_notes = f"Tree placeholder: {label}"
        session.flush()
        created_ids.append(int(copy.id or 0))
    return created_ids


def legacy_preview_tree_range(
    session: Session,
    *,
    owner_user_id: int,
    acquisition_id: int,
    payload: TreePlaceholderRangePayload,
) -> TreePlaceholderRangePreviewResponse:
    rich = preview_placeholder_range(
        session,
        owner_user_id=owner_user_id,
        acquisition_id=acquisition_id,
        payload=PlaceholderRangePreviewPayload(
            publisher=payload.publisher,
            volume_id=payload.volume_id,
            start_issue=payload.start_issue,
            end_issue=payload.end_issue,
        ),
    )
    return TreePlaceholderRangePreviewResponse(
        will_create=rich.catalog_items_to_add + rich.placeholders_to_create,
        skipped_existing=rich.skipped_duplicates,
        issue_numbers_to_create=rich.placeholder_issue_numbers,
    )
