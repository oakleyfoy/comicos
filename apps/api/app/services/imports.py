import re
from datetime import datetime, timezone

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import String, cast, func, or_
from sqlmodel import Session, select

from app.models import DraftImport, User
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
from app.schemas.orders import OrderCreate
from app.services.ai_order_parser import parse_order_draft_from_text
from app.services.ops_events import classify_failure_message, record_ops_event
from app.services.orders import create_order_for_user_in_transaction

PUBLISHER_INFERENCE_WARNING_PREFIX = "Publisher auto-filled deterministically for items:"
PUBLISHER_REVIEW_WARNING_PREFIX = "Publisher still missing for items:"
HIGH_CONFIDENCE_TITLE_PUBLISHERS = {
    "DC": ("batman", "superman", "wonder woman"),
    "Marvel": ("spider man", "x men", "avengers"),
    "Image": ("spawn", "invincible", "geiger", "hyde street"),
}
SOURCE_LINE_PUBLISHER_MARKERS = {
    "DC": re.compile(r"\bdc\b", re.IGNORECASE),
    "Marvel": re.compile(r"\bmarvel\b", re.IGNORECASE),
    "Image": re.compile(r"\bimage\b", re.IGNORECASE),
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_spaces(value: str | None) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def _normalize_title_key(value: str | None) -> str:
    normalized = _normalize_spaces(value).lower()
    return re.sub(r"[^a-z0-9]+", " ", normalized).strip()


def _strip_generated_publisher_warnings(warnings: list[str]) -> list[str]:
    return [
        warning
        for warning in warnings
        if not warning.startswith(PUBLISHER_INFERENCE_WARNING_PREFIX)
        and not warning.startswith(PUBLISHER_REVIEW_WARNING_PREFIX)
    ]


def _format_item_label(index: int, title: str | None, issue_number: str | None) -> str:
    normalized_title = _normalize_spaces(title) or "Untitled item"
    normalized_issue = _normalize_spaces(issue_number)
    if normalized_issue:
        return f"{index} ({normalized_title} #{normalized_issue})"
    return f"{index} ({normalized_title})"


def _infer_publisher_from_source_text(title: str | None, raw_text: str) -> str | None:
    title_key = _normalize_title_key(title)
    if not title_key or not raw_text.strip():
        return None

    for raw_line in raw_text.splitlines():
        line_key = _normalize_title_key(raw_line)
        if not line_key or title_key not in line_key:
            continue

        matched_publishers = [
            publisher
            for publisher, pattern in SOURCE_LINE_PUBLISHER_MARKERS.items()
            if pattern.search(raw_line)
        ]
        if len(matched_publishers) == 1:
            return matched_publishers[0]

    return None


def _infer_publisher_from_title(title: str | None) -> str | None:
    title_key = _normalize_title_key(title)
    if not title_key:
        return None

    for publisher, hints in HIGH_CONFIDENCE_TITLE_PUBLISHERS.items():
        if any(hint in title_key for hint in hints):
            return publisher

    return None


def normalize_parsed_order_response(
    parsed: ParseOrderResponse, *, raw_text: str
) -> ParseOrderResponse:
    normalized_items = []
    inferred_publishers: list[str] = []
    unresolved_publishers: list[str] = []

    for index, item in enumerate(parsed.items, start=1):
        normalized_publisher = _normalize_spaces(item.publisher) or None
        inferred_publisher = None

        if normalized_publisher is None:
            inferred_publisher = _infer_publisher_from_source_text(item.title, raw_text)
            if inferred_publisher is None:
                inferred_publisher = _infer_publisher_from_title(item.title)
            normalized_publisher = inferred_publisher

        normalized_item = item.model_copy(update={"publisher": normalized_publisher})
        normalized_items.append(normalized_item)

        item_label = _format_item_label(index, normalized_item.title, normalized_item.issue_number)
        if inferred_publisher is not None:
            inferred_publishers.append(f"{item_label} -> {inferred_publisher}")
        elif normalized_publisher is None:
            unresolved_publishers.append(item_label)

    warnings = _strip_generated_publisher_warnings(parsed.warnings)
    if inferred_publishers:
        warnings.append(
            f"{PUBLISHER_INFERENCE_WARNING_PREFIX} " + "; ".join(inferred_publishers) + "."
        )
    if unresolved_publishers:
        warnings.append(
            f"{PUBLISHER_REVIEW_WARNING_PREFIX} " + "; ".join(unresolved_publishers) + "."
        )

    return parsed.model_copy(update={"items": normalized_items, "warnings": warnings})


def serialize_import(draft_import: DraftImport) -> DraftImportRead:
    normalized_payload = normalize_parsed_order_response(
        ParseOrderResponse.model_validate(draft_import.parsed_payload_json),
        raw_text=draft_import.raw_text,
    )
    return DraftImportRead(
        id=draft_import.id,
        raw_text=draft_import.raw_text,
        parsed_payload_json=normalized_payload,
        confidence_score=draft_import.confidence_score,
        status=draft_import.status,
        order_id=draft_import.linked_order_id,
        created_at=draft_import.created_at,
        updated_at=draft_import.updated_at,
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
    sort_by: str | None,
    sort_dir: str,
) -> DraftImportListResponse:
    filtered_stmt = apply_imports_filters(
        build_imports_base_query(current_user),
        status=status,
        search=search,
    )
    total_stmt = select(func.count()).select_from(filtered_stmt.subquery())
    paginated_stmt = apply_imports_sort(filtered_stmt, sort_by, sort_dir).offset(
        (page - 1) * page_size
    ).limit(page_size)

    total = session.exec(total_stmt).one()
    imports = session.exec(paginated_stmt).all()
    return DraftImportListResponse(
        page=page,
        page_size=page_size,
        total=total,
        items=[serialize_import(item) for item in imports],
    )


def get_import_for_user(
    session: Session,
    current_user: User,
    import_id: int,
) -> DraftImportRead:
    return serialize_import(get_import_for_user_or_404(session, current_user, import_id))


def persist_draft_import(
    session: Session,
    *,
    current_user: User,
    raw_text: str,
    parsed: ParseOrderResponse,
) -> DraftImportRead:
    timestamp = utc_now()
    normalized_parsed = normalize_parsed_order_response(parsed, raw_text=raw_text)
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
    session.commit()
    session.refresh(draft_import)
    return serialize_import(draft_import)


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
        raw_text=draft_import.raw_text,
    )
    draft_import.parsed_payload_json = normalized_payload.model_dump(mode="json")

    draft_import.updated_at = utc_now()
    session.add(draft_import)
    session.commit()
    session.refresh(draft_import)
    return serialize_import(draft_import)


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
    return serialize_import(draft_import)


def build_order_create_from_import(draft_import: DraftImport) -> OrderCreate:
    parsed_payload = normalize_parsed_order_response(
        ParseOrderResponse.model_validate(draft_import.parsed_payload_json),
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
                "issue_number": item.issue_number,
                "cover_name": item.cover_name,
                "printing": item.printing,
                "ratio": item.ratio,
                "variant_type": item.variant_type,
                "cover_artist": item.cover_artist,
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
        order_payload = build_order_create_from_import(draft_import)
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

    try:
        order_response = create_order_for_user_in_transaction(
            session=session,
            current_user=current_user,
            payload=order_payload,
        )
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
        },
    )

    return DraftImportConfirmResponse(
        import_id=draft_import.id,
        status="confirmed",
        order_id=order_response.order_id,
        total_items=order_response.total_items,
        total_copies_created=order_response.total_copies_created,
        all_in_total=order_response.all_in_total,
    )
