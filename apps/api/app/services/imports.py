from datetime import datetime, timezone

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
from app.services.metadata_audits import record_metadata_audit
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
) -> DraftImportRead:
    parsed_payload = ParseOrderResponse.model_validate(draft_import.parsed_payload_json)
    if enrich_metadata:
        normalized_payload = normalize_parsed_order_response(
            parsed_payload,
            session=session,
            owner_user_id=draft_import.user_id,
            raw_text=draft_import.raw_text,
        )
    else:
        normalized_payload = parsed_payload
    metadata_review_item_count = sum(
        1 for item in normalized_payload.items if item.metadata_review_required
    )
    release_review_count = _release_date_review_item_count(normalized_payload)
    covers: list[CoverImageRead] = []
    draft_pk = draft_import.id

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
) -> DraftImportRead:
    return serialize_import(
        session,
        get_import_for_user_or_404(session, current_user, import_id),
    )


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

    try:
        return OrderCreate.model_validate(
            {
                "retailer": parsed_payload.retailer,
                "order_date": parsed_payload.order_date,
                "source_type": parsed_payload.source_type,
                "shipping_amount": parsed_payload.shipping_amount,
                "tax_amount": parsed_payload.tax_amount,
                "items": normalized_items,
            }
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="Draft import is invalid") from exc


def confirm_import_for_user(
    session: Session,
    current_user: User,
    import_id: int,
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
