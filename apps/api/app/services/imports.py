from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import String, cast, func, or_
from sqlmodel import Session, select

from app.models import CoverImage, DraftImport, InventoryCopy, OrderItem, User
from app.schemas.ai import ParseOrderResponse
from app.schemas.imports import (
    DraftImportConfirmResponse,
    DraftImportCreate,
    DraftImportListResponse,
    DraftImportRead,
    DraftImportStatus,
    DraftImportUpdate,
    ManualDraftImportCreate,
)
from app.schemas.cover_images import CoverImageRead
from app.schemas.orders import OrderCreate
from app.services.ai_order_parser import parse_order_draft_from_text
from app.services.canonical_creators import get_or_create_canonical_creator
from app.services.import_cover_resolver import apply_import_cover_to_parse_order
from app.services.import_cover_display import cover_display_fields_from_urls, effective_import_cover_url
from app.services.import_line_cover_resolution_service import (
    attach_line_cover_resolutions_to_order,
    hydrate_item_from_stored_cover_resolution,
    persist_parse_order_line_cover_resolutions,
    record_cover_resolution_health_on_confirm,
)
from app.services.import_retailer_cover_extract import enrich_parse_order_retailer_covers_from_raw_text
from app.services.metadata_audits import record_metadata_audit
from app.services.import_release_lifecycle_service import apply_release_lifecycle_to_parse_order
from app.services.metadata_enrichment import (
    RELEASE_DATE_PAYLOAD_SEARCH_FRAGMENT,
    enrich_parse_order_metadata,
    iter_canonical_creator_names,
    normalize_creator_name,
)
from app.services.ops_events import classify_failure_message, record_ops_event
from app.services.orders import create_order_for_user_in_transaction
from app.services.cover_images import (
    COVER_CARRY_MULTI_COPY_NOTICE,
    carry_draft_import_cover_images_to_inventory_copy,
    list_cover_reads_for_draft,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _item_cover_snapshot(item: dict) -> dict:
    return {
        key: item.get(key)
        for key in (
            "cover_url",
            "cover_image_url",
            "cover_thumbnail_url",
            "retailer_cover_url",
            "retailer_thumbnail_url",
            "has_cover_image",
            "cover_source",
            "cover_confidence",
            "variant_confidence",
            "cover_resolution_debug",
            "retailer_lookup_enrichment",
            "retailer_lookup_status",
            "retailer_lookup_score",
            "retailer_lookup_rejected_reason",
            "retailer_lookup_checked_at",
        )
    }


def _persist_resolved_cover_payload_if_changed(
    session: Session,
    draft_import: DraftImport,
    normalized_payload: ParseOrderResponse,
) -> bool:
    new_dump = normalized_payload.model_dump(mode="json")
    old_items = (draft_import.parsed_payload_json or {}).get("items") or []
    new_items = new_dump.get("items") or []
    if len(old_items) != len(new_items):
        draft_import.parsed_payload_json = new_dump
        draft_import.updated_at = utc_now()
        session.add(draft_import)
        return True
    for old_item, new_item in zip(old_items, new_items, strict=False):
        if _item_cover_snapshot(old_item if isinstance(old_item, dict) else {}) != _item_cover_snapshot(
            new_item if isinstance(new_item, dict) else {}
        ):
            draft_import.parsed_payload_json = new_dump
            draft_import.updated_at = utc_now()
            session.add(draft_import)
            return True
    return False


def _release_date_review_item_count(normalized_payload: ParseOrderResponse) -> int:
    marker = RELEASE_DATE_PAYLOAD_SEARCH_FRAGMENT
    return sum(
        1
        for item in normalized_payload.items
        if any(marker in note for note in (item.metadata_review_notes or []))
    )


def normalize_parsed_order_response(
    parsed: ParseOrderResponse,
    *,
    session: Session | None = None,
    owner_user_id: int | None = None,
    raw_text: str,
) -> ParseOrderResponse:
    parsed = enrich_parse_order_retailer_covers_from_raw_text(parsed, raw_text)
    return enrich_parse_order_metadata(
        parsed,
        session=session,
        owner_user_id=owner_user_id,
        raw_text=raw_text,
    )


def sync_canonical_creators_for_payload(
    session: Session,
    payload: ParseOrderResponse,
    *,
    actor_user_id: int | None = None,
    audit_reason: str | None = None,
) -> None:
    for item in payload.items:
        for creator_name in iter_canonical_creator_names(item):
            normalized = normalize_creator_name(creator_name, session=session)
            if normalized.canonical_value is None or normalized.normalized_value is None:
                continue
            get_or_create_canonical_creator(
                session,
                canonical_name=normalized.canonical_value,
                normalized_name=normalized.normalized_value,
                actor_user_id=actor_user_id,
                audit_reason=audit_reason,
            )


def draft_import_cover_image_counts(session: Session, draft_import_ids: list[int]) -> dict[int, int]:
    if not draft_import_ids:
        return {}
    rows = session.exec(
        select(CoverImage.draft_import_id, func.count(CoverImage.id))
        .where(CoverImage.draft_import_id.in_(draft_import_ids))
        .group_by(CoverImage.draft_import_id)
    ).all()
    return {int(draft_id): int(total or 0) for draft_id, total in rows}


def build_draft_import_audit_snapshot(
    draft_import: DraftImport,
    *,
    parsed_payload_json: dict | None = None,
) -> dict:
    return {
        "id": draft_import.id,
        "status": draft_import.status,
        "linked_order_id": draft_import.linked_order_id,
        "confidence_score": draft_import.confidence_score,
        "parsed_payload_json": (
            parsed_payload_json
            if parsed_payload_json is not None
            else draft_import.parsed_payload_json
        ),
    }


def serialize_import(
    session: Session,
    draft_import: DraftImport,
    *,
    prefetch_cover_images: bool = True,
    cover_image_count: int | None = None,
    enrich_metadata: bool = True,
    enrich_lifecycle: bool = True,
    debug_catalog: bool = False,
) -> DraftImportRead:
    parsed_payload = ParseOrderResponse.model_validate(draft_import.parsed_payload_json)
    draft_pk = draft_import.id
    if enrich_metadata:
        normalized_payload = normalize_parsed_order_response(
            parsed_payload,
            session=session,
            owner_user_id=draft_import.user_id,
            raw_text=draft_import.raw_text,
        )
    else:
        normalized_payload = parsed_payload
    if enrich_lifecycle:
        normalized_payload = apply_release_lifecycle_to_parse_order(
            normalized_payload,
            session=session,
            owner_user_id=draft_import.user_id,
            debug_catalog=debug_catalog,
        )
    if session is not None and draft_pk is not None and (enrich_metadata or enrich_lifecycle):
        hydrated_items = [
            hydrate_item_from_stored_cover_resolution(
                session,
                draft_import_id=int(draft_pk),
                line_index=line_index,
                item=item,
            )
            for line_index, item in enumerate(normalized_payload.items)
        ]
        normalized_payload = normalized_payload.model_copy(update={"items": hydrated_items})
    if session is not None and (enrich_metadata or enrich_lifecycle):
        normalized_payload = apply_import_cover_to_parse_order(
            normalized_payload,
            session=session,
            owner_user_id=draft_import.user_id,
            draft_import_id=draft_import.id,
        )
        if draft_pk is not None and draft_import.user_id is not None:
            persist_parse_order_line_cover_resolutions(
                session,
                owner_user_id=int(draft_import.user_id),
                draft_import_id=int(draft_pk),
                items=normalized_payload.items,
            )
            session.flush()
        if draft_import.status == "draft" and draft_pk is not None:
            if _persist_resolved_cover_payload_if_changed(session, draft_import, normalized_payload):
                session.commit()
                session.refresh(draft_import)
    metadata_review_item_count = sum(
        1 for item in normalized_payload.items if item.metadata_review_required
    )
    release_review_count = _release_date_review_item_count(normalized_payload)
    covers: list[CoverImageRead] = []

    if prefetch_cover_images and draft_pk is not None:
        covers = list_cover_reads_for_draft(session, draft_pk)
        resolved_cover_count = len(covers)
    elif cover_image_count is not None:
        resolved_cover_count = cover_image_count
    elif draft_pk is not None:
        resolved_cover_count = int(
            session.exec(
                select(func.count(CoverImage.id)).where(CoverImage.draft_import_id == draft_pk)
            ).one()
        )
    else:
        resolved_cover_count = 0

    return DraftImportRead(
        id=draft_import.id,
        raw_text=draft_import.raw_text,
        parsed_payload_json=normalized_payload,
        confidence_score=draft_import.confidence_score,
        status=draft_import.status,
        needs_metadata_review=metadata_review_item_count > 0,
        metadata_review_item_count=metadata_review_item_count,
        needs_release_date_review=release_review_count > 0,
        release_date_review_item_count=release_review_count,
        order_id=draft_import.linked_order_id,
        created_at=draft_import.created_at,
        updated_at=draft_import.updated_at,
        cover_images=covers,
        cover_image_count=resolved_cover_count,
    )


def get_import_for_user_or_404(
    session: Session,
    current_user: User,
    import_id: int,
) -> DraftImport:
    draft_import = session.exec(
        select(DraftImport).where(
            DraftImport.id == import_id,
            DraftImport.user_id == current_user.id,
        )
    ).first()
    if draft_import is None:
        raise HTTPException(status_code=404, detail="Import not found")
    return draft_import


IMPORT_SORTABLE_FIELDS = {"created_at", "updated_at", "confidence_score", "status"}


def build_imports_base_query(current_user: User):
    return select(DraftImport).where(DraftImport.user_id == current_user.id)


def apply_imports_filters(
    stmt,
    *,
    status: DraftImportStatus | None,
    search: str | None,
    needs_metadata_review: bool | None,
    needs_release_date_review: bool | None,
):
    if status is not None:
        stmt = stmt.where(DraftImport.status == status)

    if search:
        search_term = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                DraftImport.raw_text.ilike(search_term),
                cast(DraftImport.parsed_payload_json, String).ilike(search_term),
            )
        )

    if needs_metadata_review is True:
        stmt = stmt.where(
            or_(
                cast(DraftImport.parsed_payload_json, String).ilike(
                    '%"metadata_review_required": true%'
                ),
                cast(DraftImport.parsed_payload_json, String).ilike(
                    '%"metadata_review_required":true%'
                ),
            )
        )
    elif needs_metadata_review is False:
        stmt = stmt.where(
            ~or_(
                cast(DraftImport.parsed_payload_json, String).ilike(
                    '%"metadata_review_required": true%'
                ),
                cast(DraftImport.parsed_payload_json, String).ilike(
                    '%"metadata_review_required":true%'
                ),
            )
        )

    release_fragment = RELEASE_DATE_PAYLOAD_SEARCH_FRAGMENT
    release_pattern = f"%{release_fragment}%"

    if needs_release_date_review is True:
        stmt = stmt.where(
            cast(DraftImport.parsed_payload_json, String).ilike(release_pattern)
        )
    elif needs_release_date_review is False:
        stmt = stmt.where(
            ~cast(DraftImport.parsed_payload_json, String).ilike(release_pattern)
        )

    return stmt


def apply_imports_sort(stmt, sort_by: str | None, sort_dir: str):
    resolved_sort = sort_by or "updated_at"
    if resolved_sort not in IMPORT_SORTABLE_FIELDS:
        raise HTTPException(status_code=400, detail="Invalid sort_by value")

    sort_column_map = {
        "created_at": DraftImport.created_at,
        "updated_at": DraftImport.updated_at,
        "confidence_score": DraftImport.confidence_score,
        "status": DraftImport.status,
    }
    sort_column = sort_column_map[resolved_sort]
    direction = sort_column.desc() if sort_dir == "desc" else sort_column.asc()
    tie_breaker = DraftImport.id.desc() if sort_dir == "desc" else DraftImport.id.asc()
    return stmt.order_by(direction, tie_breaker)


def list_imports_for_user(
    session: Session,
    current_user: User,
    *,
    page: int,
    page_size: int,
    status: DraftImportStatus | None,
    search: str | None,
    needs_metadata_review: bool | None,
    needs_release_date_review: bool | None,
    sort_by: str | None,
    sort_dir: str,
) -> DraftImportListResponse:
    filtered_stmt = apply_imports_filters(
        build_imports_base_query(current_user),
        status=status,
        search=search,
        needs_metadata_review=needs_metadata_review,
        needs_release_date_review=needs_release_date_review,
    )
    total_stmt = select(func.count()).select_from(filtered_stmt.subquery())
    paginated_stmt = apply_imports_sort(filtered_stmt, sort_by, sort_dir).offset(
        (page - 1) * page_size
    ).limit(page_size)

    total = session.exec(total_stmt).one()
    imports = session.exec(paginated_stmt).all()
    draft_ids = [row.id for row in imports if row.id is not None]
    counts = draft_import_cover_image_counts(session, draft_ids)

    def count_for(import_row: DraftImport) -> int:
        if import_row.id is None:
            return 0
        return counts.get(import_row.id, 0)

    return DraftImportListResponse(
        page=page,
        page_size=page_size,
        total=total,
        items=[
            serialize_import(session, row, prefetch_cover_images=False, cover_image_count=count_for(row))
            for row in imports
        ],
    )


def get_import_for_user(
    session: Session,
    current_user: User,
    import_id: int,
    *,
    debug_catalog: bool = False,
) -> DraftImportRead:
    return serialize_import(
        session,
        get_import_for_user_or_404(session, current_user, import_id),
        debug_catalog=debug_catalog,
    )


def re_resolve_import_covers_for_user(
    session: Session,
    current_user: User,
    import_id: int,
) -> DraftImportRead:
    draft_import = get_import_for_user_or_404(session, current_user, import_id)
    if draft_import.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft imports can re-resolve covers.")

    parsed = ParseOrderResponse.model_validate(draft_import.parsed_payload_json)
    cleared_items = []
    for item in parsed.items:
        if item.cover_verified_by == "USER" and effective_import_cover_url(item):
            cleared_items.append(item)
            continue
        preserve_exact_retailer_item = bool(item.retailer_cover_url and (item.retailer_item_id or item.retailer_order_number))
        cleared_items.append(
            item.model_copy(
                update={
                    "cover_verified_by": None,
                    "cover_verified_at": None,
                    "cover_image_url": None,
                    "cover_thumbnail_url": None,
                    "cover_url": None,
                    "has_cover_image": False,
                    "cover_resolution_debug": None,
                    "retailer_lookup_enrichment": None,
                    "retailer_lookup_status": None,
                    "retailer_lookup_score": None,
                    "retailer_lookup_rejected_reason": None,
                    "retailer_lookup_checked_at": None,
                    "retailer_cover_url": item.retailer_cover_url if preserve_exact_retailer_item else None,
                    "retailer_thumbnail_url": item.retailer_thumbnail_url if preserve_exact_retailer_item else None,
                    "retailer_product_url": item.retailer_product_url if preserve_exact_retailer_item else None,
                    "retailer_sku": item.retailer_sku if preserve_exact_retailer_item else None,
                }
            )
        )
    draft_import.parsed_payload_json = parsed.model_copy(update={"items": cleared_items}).model_dump(
        mode="json"
    )
    draft_import.updated_at = utc_now()
    session.add(draft_import)
    session.commit()
    session.refresh(draft_import)
    return serialize_import(session, draft_import)


def persist_draft_import(
    session: Session,
    *,
    current_user: User,
    raw_text: str,
    parsed: ParseOrderResponse,
) -> DraftImportRead:
    timestamp = utc_now()
    normalized_parsed = normalize_parsed_order_response(
        parsed,
        session=session,
        owner_user_id=current_user.id,
        raw_text=raw_text,
    )
    sync_canonical_creators_for_payload(
        session,
        normalized_parsed,
        actor_user_id=current_user.id,
        audit_reason="Deterministic draft enrichment during import persistence.",
    )
    draft_import = DraftImport(
        user_id=current_user.id,
        raw_text=raw_text,
        parsed_payload_json=normalized_parsed.model_dump(mode="json"),
        confidence_score=normalized_parsed.confidence_score,
        status="draft",
        created_at=timestamp,
        updated_at=timestamp,
    )
    session.add(draft_import)
    session.flush()
    record_metadata_audit(
        session,
        entity_type="draft_item",
        entity_id=draft_import.id,
        action="enriched",
        after_snapshot=build_draft_import_audit_snapshot(
            draft_import,
            parsed_payload_json=normalized_parsed.model_dump(mode="json"),
        ),
        reason="Deterministic metadata enrichment saved for draft import.",
        actor_user_id=current_user.id,
    )
    session.commit()
    session.refresh(draft_import)
    return serialize_import(session, draft_import)


def create_import_for_user(
    session: Session,
    current_user: User,
    payload: DraftImportCreate,
) -> DraftImportRead:
    parsed = parse_order_draft_from_text(payload.raw_text)
    return persist_draft_import(
        session,
        current_user=current_user,
        raw_text=payload.raw_text,
        parsed=parsed,
    )


def create_manual_import_for_user(
    session: Session,
    current_user: User,
    payload: ManualDraftImportCreate,
) -> DraftImportRead:
    parsed = ParseOrderResponse.model_validate(payload.model_dump(exclude={"raw_text"}))
    return persist_draft_import(
        session,
        current_user=current_user,
        raw_text=payload.raw_text or "",
        parsed=parsed,
    )


def update_import_for_user(
    session: Session,
    current_user: User,
    import_id: int,
    payload: DraftImportUpdate,
) -> DraftImportRead:
    draft_import = get_import_for_user_or_404(session, current_user, import_id)
    if draft_import.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft imports can be edited")

    if payload.raw_text is not None:
        draft_import.raw_text = payload.raw_text

    if payload.parsed_payload_json is not None:
        validated_payload = normalize_parsed_order_response(
            ParseOrderResponse.model_validate(payload.parsed_payload_json),
            session=session,
            owner_user_id=current_user.id,
            raw_text=draft_import.raw_text,
        )
        draft_import.parsed_payload_json = validated_payload.model_dump(mode="json")
        draft_import.confidence_score = (
            payload.confidence_score
            if payload.confidence_score is not None
            else validated_payload.confidence_score
        )
    elif payload.confidence_score is not None:
        draft_import.confidence_score = payload.confidence_score

    normalized_payload = normalize_parsed_order_response(
        ParseOrderResponse.model_validate(draft_import.parsed_payload_json),
        session=session,
        owner_user_id=current_user.id,
        raw_text=draft_import.raw_text,
    )
    sync_canonical_creators_for_payload(
        session,
        normalized_payload,
        actor_user_id=current_user.id,
        audit_reason="Deterministic draft enrichment during draft update.",
    )
    draft_import.parsed_payload_json = normalized_payload.model_dump(mode="json")

    draft_import.updated_at = utc_now()
    session.add(draft_import)
    session.commit()
    session.refresh(draft_import)
    return serialize_import(session, draft_import)


def attach_import_line_cover_image(
    session: Session,
    *,
    current_user: User,
    draft_import_id: int,
    line_index: int,
    cover_image_id: int,
) -> None:
    draft_import = get_import_for_user_or_404(session, current_user, draft_import_id)
    if draft_import.status != "draft":
        raise HTTPException(
            status_code=409,
            detail="Cover scans can only be linked to line items on draft imports.",
        )

    cover = session.get(CoverImage, cover_image_id)
    if cover is None or cover.draft_import_id != draft_import_id:
        raise HTTPException(status_code=404, detail="Cover image not found for this import.")

    parsed = ParseOrderResponse.model_validate(draft_import.parsed_payload_json)
    if line_index < 0 or line_index >= len(parsed.items):
        raise HTTPException(status_code=422, detail="Invalid import line index.")

    items = list(parsed.items)
    items[line_index] = items[line_index].model_copy(
        update={
            "import_line_cover_image_id": cover_image_id,
            "cover_verified_by": "USER",
            "cover_verified_at": utc_now(),
        },
    )
    parsed = parsed.model_copy(update={"items": items})

    normalized_payload = normalize_parsed_order_response(
        parsed,
        session=session,
        owner_user_id=current_user.id,
        raw_text=draft_import.raw_text,
    )
    normalized_payload = apply_import_cover_to_parse_order(
        normalized_payload,
        session=session,
        owner_user_id=current_user.id,
        draft_import_id=draft_import_id,
    )
    persist_parse_order_line_cover_resolutions(
        session,
        owner_user_id=int(current_user.id),
        draft_import_id=draft_import_id,
        items=normalized_payload.items,
    )
    draft_import.parsed_payload_json = normalized_payload.model_dump(mode="json")
    draft_import.updated_at = utc_now()
    session.add(draft_import)
    session.commit()


def discard_import_for_user(
    session: Session,
    current_user: User,
    import_id: int,
) -> DraftImportRead:
    draft_import = get_import_for_user_or_404(session, current_user, import_id)
    if draft_import.status == "confirmed":
        raise HTTPException(status_code=409, detail="Confirmed imports cannot be discarded")

    draft_import.status = "discarded"
    draft_import.updated_at = utc_now()
    session.add(draft_import)
    session.commit()
    session.refresh(draft_import)
    return serialize_import(session, draft_import)


def build_order_create_from_import(session: Session, draft_import: DraftImport) -> OrderCreate:
    parsed_payload = normalize_parsed_order_response(
        ParseOrderResponse.model_validate(draft_import.parsed_payload_json),
        session=session,
        owner_user_id=draft_import.user_id,
        raw_text=draft_import.raw_text,
    )
    draft_import.parsed_payload_json = parsed_payload.model_dump(mode="json")
    missing_fields: list[str] = []

    if parsed_payload.retailer is None:
        missing_fields.append("retailer")
    if parsed_payload.order_date is None:
        missing_fields.append("order_date")
    if not parsed_payload.items:
        missing_fields.append("items")

    normalized_items = []
    for index, item in enumerate(parsed_payload.items, start=1):
        item_missing: list[str] = []
        if item.publisher is None:
            item_missing.append("publisher")
        if item.title is None:
            item_missing.append("title")
        if item.issue_number is None:
            item_missing.append("issue_number")
        if item.quantity is None:
            item_missing.append("quantity")
        if item.raw_item_price is None:
            item_missing.append("raw_item_price")
        if item_missing:
            missing_fields.append(f"items[{index}]: {', '.join(item_missing)}")
            continue

        normalized_items.append(
            {
                "publisher": item.publisher,
                "title": item.title,
                "release_date": item.parsed_release_date,
                "release_year": item.parsed_release_year,
                "release_status": item.release_status,
                "order_status": item.order_status,
                "purchase_date": item.purchase_date,
                "expected_ship_date": item.expected_ship_date,
                "received_at": item.received_at,
                "issue_number": item.issue_number,
                "cover_name": item.cover_name,
                "printing": item.printing,
                "ratio": item.ratio,
                "variant_type": item.variant_type,
                "cover_artist": item.cover_artist,
                "writers": item.canonical_writers or item.writers,
                "artists": item.canonical_artists or item.artists,
                "cover_artists": item.canonical_cover_artists or item.cover_artists,
                "metadata_identity_key": item.metadata_identity_key,
                "quantity": item.quantity,
                "raw_item_price": item.raw_item_price,
            }
        )

    if missing_fields:
        raise HTTPException(
            status_code=422,
            detail="Draft import is incomplete: " + "; ".join(missing_fields),
        )

    line_subtotal = sum(
        Decimal(item.quantity or 0) * (item.raw_item_price or Decimal("0"))
        for item in parsed_payload.items
    )
    if parsed_payload.order_total is not None:
        shipping_amount = Decimal("0")
        tax_amount = max(Decimal("0"), parsed_payload.order_total - line_subtotal)
    else:
        shipping_amount = parsed_payload.shipping_amount
        tax_amount = parsed_payload.tax_amount

    try:
        return OrderCreate.model_validate(
            {
                "retailer": parsed_payload.retailer,
                "order_date": parsed_payload.order_date,
                "source_type": parsed_payload.source_type,
                "shipping_amount": shipping_amount,
                "tax_amount": tax_amount,
                "items": normalized_items,
            }
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="Draft import is invalid") from exc


def confirm_import_for_user(
    session: Session,
    current_user: User,
    import_id: int,
    *,
    bypass_legacy_write_retirement: bool = False,
) -> DraftImportConfirmResponse:
    draft_import = get_import_for_user_or_404(session, current_user, import_id)
    if draft_import.status == "discarded":
        record_ops_event(
            event_type="confirm_failure",
            status="failed",
            user_id=current_user.id,
            draft_import_id=draft_import.id,
            message="Discarded imports cannot be confirmed",
            details={"http_status": 409},
        )
        raise HTTPException(status_code=409, detail="Discarded imports cannot be confirmed")
    if draft_import.status == "confirmed":
        record_ops_event(
            event_type="confirm_failure",
            status="failed",
            user_id=current_user.id,
            draft_import_id=draft_import.id,
            order_id=draft_import.linked_order_id,
            message="Import already confirmed",
            details={"http_status": 409},
        )
        raise HTTPException(status_code=409, detail="Import already confirmed")

    try:
        order_payload = build_order_create_from_import(session, draft_import)
    except HTTPException as exc:
        record_ops_event(
            event_type="confirm_failure",
            status="failed",
            user_id=current_user.id,
            draft_import_id=draft_import.id,
            message=str(exc.detail),
            details={
                "http_status": exc.status_code,
                "failure_type": classify_failure_message(str(exc.detail)),
            },
        )
        raise

    notices: list[str] = []
    draft_cover_carryover_mode = "none"
    draft_cover_count_before_carryover = 0

    try:
        order_response = create_order_for_user_in_transaction(
            session=session,
            current_user=current_user,
            payload=order_payload,
            bypass_legacy_write_retirement=bypass_legacy_write_retirement,
        )
        draft_cover_count_before_carryover = len(
            session.exec(
                select(CoverImage.id).where(CoverImage.draft_import_id == draft_import.id)
            ).all()
        )

        if draft_cover_count_before_carryover > 0:
            if order_response.total_copies_created == 1:
                inventory_ids = list(
                    session.exec(
                        select(InventoryCopy.id)
                        .join(OrderItem, InventoryCopy.order_item_id == OrderItem.id)
                        .where(OrderItem.order_id == order_response.order_id)
                        .order_by(InventoryCopy.id.asc())
                    ).all()
                )
                if len(inventory_ids) == 1:
                    carry_draft_import_cover_images_to_inventory_copy(
                        session,
                        draft_import=draft_import,
                        inventory_copy_id=inventory_ids[0],
                    )
                    draft_cover_carryover_mode = "single_inventory_copy"
                elif draft_cover_count_before_carryover > 0:
                    notices.append(COVER_CARRY_MULTI_COPY_NOTICE)
                    draft_cover_carryover_mode = "skipped_invariant_mismatch"
            else:
                notices.append(COVER_CARRY_MULTI_COPY_NOTICE)
                draft_cover_carryover_mode = "skipped_multiple_inventory_copies"

        draft_import.status = "confirmed"
        draft_import.linked_order_id = order_response.order_id
        draft_import.updated_at = utc_now()
        session.add(draft_import)
        from app.services.p92_guided_import_service import record_import_health_event

        record_import_health_event(
            session,
            owner_user_id=int(current_user.id),
            event_type="import_confirmed",
            draft_import_id=int(draft_import.id or 0),
            payload={
                "total_items": order_response.total_items,
                "total_copies_created": order_response.total_copies_created,
            },
        )
        linked_cover_rows = attach_line_cover_resolutions_to_order(
            session,
            draft_import_id=int(draft_import.id or 0),
            order_id=int(order_response.order_id),
        )
        record_cover_resolution_health_on_confirm(
            session,
            owner_user_id=int(current_user.id),
            draft_import_id=int(draft_import.id or 0),
            linked_count=linked_cover_rows,
            item_count=order_response.total_items,
        )
        session.commit()
    except Exception as exc:
        session.rollback()
        record_ops_event(
            event_type="confirm_failure",
            status="failed",
            user_id=current_user.id,
            draft_import_id=draft_import.id,
            message=str(exc),
            details={"failure_type": classify_failure_message(str(exc))},
        )
        raise

    record_ops_event(
        event_type="confirm_success",
        status="success",
        user_id=current_user.id,
        draft_import_id=draft_import.id,
        order_id=order_response.order_id,
        message="Draft import confirmed into order",
        details={
            "total_items": order_response.total_items,
            "total_copies_created": order_response.total_copies_created,
            "all_in_total": order_response.all_in_total,
            "draft_import_cover_carryover_mode": draft_cover_carryover_mode,
            "draft_import_cover_count_before_carryover": draft_cover_count_before_carryover,
            "draft_import_cover_notice_count": len(notices),
        },
    )

    return DraftImportConfirmResponse(
        import_id=draft_import.id,
        status="confirmed",
        order_id=order_response.order_id,
        total_items=order_response.total_items,
        total_copies_created=order_response.total_copies_created,
        all_in_total=order_response.all_in_total,
        notices=notices,
    )
