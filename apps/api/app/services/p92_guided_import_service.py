"""P92 guided import — progress, exception-only review, summaries."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlmodel import Session

from app.models.p92_import_health import P92ImportHealthEvent
from app.schemas.ai import AiDraftOrderItem, ParseOrderResponse
from app.schemas.imports import DraftImportRead
from app.schemas.jobs import ImportParseJobStatusResponse
from app.schemas.p92_guided_import import (
    GuidedImportExceptionItemRead,
    GuidedImportProgressPhaseRead,
    GuidedImportProgressRead,
    GuidedImportReviewRead,
    GuidedImportSuccessRead,
    GuidedImportSummaryRead,
)
from app.services.imports import serialize_import

COVER_CONFIDENCE_THRESHOLD = 0.55
VARIANT_CONFIDENCE_THRESHOLD = 0.55
CATALOG_MATCH_MIN_SCORE = 70


def _cover_source_display_label(item: AiDraftOrderItem, retailer: str | None) -> str | None:
    kind = item.cover_source
    if not kind and not item.cover_image_source:
        return None
    if kind == "RETAILER":
        return (retailer or "Retailer").strip() or "Retailer"
    if kind == "LOCG":
        return "LoCG"
    if kind == "EXTERNAL_CATALOG":
        return "Catalog"
    if kind == "USER_UPLOAD":
        return "Your upload"
    legacy = (item.cover_image_source or "").lower()
    if "retailer" in legacy:
        return (retailer or "Retailer").strip() or "Retailer"
    if "external" in legacy or "locg" in legacy:
        return "LoCG"
    if "draft" in legacy or "upload" in legacy or "line" in legacy:
        return "Your upload"
    return None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


PROGRESS_PHASES: tuple[tuple[str, str], ...] = (
    ("UPLOADING", "Reading order"),
    ("PARSING", "Matching comics"),
    ("MATCHING", "Finding covers"),
    ("ENRICHING", "Checking release data"),
    ("READY_FOR_REVIEW", "Building inventory preview"),
    ("COMPLETE", "Ready for you"),
)


def record_import_health_event(
    session: Session,
    *,
    owner_user_id: int,
    event_type: str,
    draft_import_id: int | None = None,
    payload: dict | None = None,
) -> None:
    session.add(
        P92ImportHealthEvent(
            owner_user_id=owner_user_id,
            draft_import_id=draft_import_id,
            event_type=event_type,
            payload_json=dict(payload or {}),
        )
    )
    session.flush()


def map_parse_job_to_progress(job: ImportParseJobStatusResponse) -> GuidedImportProgressRead:
    status = (job.status or "").lower()
    if status in {"finished", "complete", "completed"}:
        active = "COMPLETE"
    elif status in {"failed", "error"}:
        active = "PARSING"
    elif status in {"started", "running"}:
        active = "MATCHING"
    elif job.import_id is not None:
        active = "ENRICHING"
    else:
        active = "UPLOADING"

    order = [code for code, _ in PROGRESS_PHASES]
    active_index = order.index(active) if active in order else 0
    phases = [
        GuidedImportProgressPhaseRead(
            code=code,
            label=label,
            complete=order.index(code) < active_index or (active == "COMPLETE" and code == "COMPLETE"),
            active=code == active,
        )
        for code, label in PROGRESS_PHASES
    ]
    return GuidedImportProgressRead(
        engine_state=active,
        user_label=next(label for code, label in PROGRESS_PHASES if code == active),
        phases=phases,
        import_id=job.import_id,
        job_status=job.status,
        error=job.error,
    )


def _exception_reasons(item: AiDraftOrderItem) -> list[str]:
    reasons: list[str] = []
    if item.metadata_review_required:
        notes = item.metadata_review_notes or []
        if notes:
            reasons.extend(notes[:2])
        else:
            reasons.append("Metadata needs a quick review")
    if item.catalog_match_matched is False and item.catalog_match_possible:
        reasons.append("Multiple catalog matches found — pick the best fit")
    elif item.catalog_match_matched is False:
        reasons.append("No confident catalog match")
    if item.has_cover_image is False:
        reasons.append("No cover available")
    cover_conf = item.cover_confidence
    if cover_conf is not None and cover_conf < COVER_CONFIDENCE_THRESHOLD:
        reasons.append("Low confidence on cover image")
    variant_conf = item.variant_confidence
    if variant_conf is not None and variant_conf < VARIANT_CONFIDENCE_THRESHOLD:
        reasons.append("Cover variant may not match your order")
    score = item.catalog_match_score
    if score is not None and score < CATALOG_MATCH_MIN_SCORE and item.catalog_match_matched is not True:
        reasons.append("Low confidence match")
    if item.metadata_review_notes:
        for note in item.metadata_review_notes:
            lower = note.lower()
            if "variant" in lower and "variant" not in " ".join(reasons).lower():
                reasons.append("Variant conflict needs review")
            if "duplicate" in lower:
                reasons.append("Possible duplicate entry")
    deduped: list[str] = []
    seen: set[str] = set()
    for reason in reasons:
        key = reason.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(reason)
    return deduped


def _item_is_exception(item: AiDraftOrderItem) -> bool:
    return len(_exception_reasons(item)) > 0


def build_guided_import_review(draft_read: DraftImportRead) -> GuidedImportReviewRead:
    payload = draft_read.parsed_payload_json
    retailer = payload.retailer
    exceptions: list[GuidedImportExceptionItemRead] = []
    auto_count = 0
    for index, item in enumerate(payload.items):
        if _item_is_exception(item):
            reasons = _exception_reasons(item)
            exceptions.append(
                GuidedImportExceptionItemRead(
                    item_index=index,
                    title=item.title or item.canonical_title or "Unknown title",
                    issue_number=item.issue_number or item.canonical_issue_number or "",
                    publisher=item.publisher or item.canonical_publisher or "",
                    variant_label=item.cover_name or item.variant_type or "",
                    release_date=str(item.release_date or item.parsed_release_date or ""),
                    cover_url=item.cover_thumbnail_url or item.cover_image_url,
                    problems=reasons,
                    cover_source=_cover_source_display_label(item, retailer),
                    cover_confidence=item.cover_confidence,
                    variant_confidence=item.variant_confidence,
                    catalog_match_score=item.catalog_match_score,
                    suggested_catalog_title=item.catalog_match_title,
                )
            )
        else:
            auto_count += 1
    return GuidedImportReviewRead(
        import_id=draft_read.id,
        auto_matched_count=auto_count,
        exception_count=len(exceptions),
        exceptions=exceptions,
        status=draft_read.status,
    )


def build_guided_import_summary(draft_read: DraftImportRead) -> GuidedImportSummaryRead:
    payload = draft_read.parsed_payload_json
    publishers: set[str] = set()
    series: set[str] = set()
    variant_count = 0
    total_value = Decimal("0")
    book_count = 0
    for item in payload.items:
        qty = int(item.quantity or 1)
        book_count += qty
        pub = (item.publisher or item.canonical_publisher or "").strip()
        if pub:
            publishers.add(pub)
        title = (item.title or item.canonical_title or "").strip()
        if title:
            series.add(title)
        if item.cover_name or item.variant_type or item.ratio:
            variant_count += qty
        if item.raw_item_price is not None:
            total_value += Decimal(str(item.raw_item_price)) * qty
    return GuidedImportSummaryRead(
        import_id=draft_read.id,
        books_imported=book_count,
        publisher_count=len(publishers),
        variant_count=variant_count,
        value_tracked=float(total_value),
        new_series_count=len(series),
        retailer=payload.retailer,
        order_date=str(payload.order_date) if payload.order_date else None,
    )


def build_guided_import_success(
    *,
    import_id: int,
    books_added: int,
    summary: GuidedImportSummaryRead,
) -> GuidedImportSuccessRead:
    return GuidedImportSuccessRead(
        import_id=import_id,
        books_added=books_added,
        estimated_value=summary.value_tracked,
        series_discovered=summary.new_series_count,
        publishers_discovered=summary.publisher_count,
    )


def get_guided_review_for_import(
    session: Session,
    *,
    current_user,
    draft_import_id: int,
) -> GuidedImportReviewRead:
    from app.services.imports import get_import_for_user_or_404

    draft = get_import_for_user_or_404(session, current_user, draft_import_id)
    draft_read = serialize_import(session, draft)
    review = build_guided_import_review(draft_read)
    record_import_health_event(
        session,
        owner_user_id=int(current_user.id),
        event_type="guided_review_opened",
        draft_import_id=draft_import_id,
        payload={"exception_count": review.exception_count, "auto_matched_count": review.auto_matched_count},
    )
    return review
