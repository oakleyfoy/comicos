"""P100 AI vision first-pass recognition."""

from __future__ import annotations

import base64
import json
import logging
import time
from pathlib import Path
from typing import Any

from PIL import Image
from sqlmodel import Session, delete

from app.core.config import get_settings
from app.services.photo_import_issue_number import apply_photo_issue_sanitization, normalize_photo_issue_number
from app.models.photo_import import (
    DETECTION_STATUS_DETECTED,
    DETECTION_STATUS_NEEDS_REVIEW,
    RECOGNITION_STATUS_UNKNOWN,
    PhotoImportDetectedBook,
    PhotoImportImage,
)
from app.services.photo_import_crop_service import clamp_bbox01, extract_and_save_crop
from app.services.photo_import_storage_service import resolve_photo_import_storage_path
from app.services.photo_import_segmentation_service import (
    MAX_DETECTED_BOOKS,
    PHOTO_IMPORT_PIPELINE_VERSION,
    comic_count_from_payload,
    estimate_comic_slots_from_layout,
    expand_books_to_match_bboxes,
    extract_bbox_from_book,
    grid_bboxes_for_count,
    is_full_frame_bbox,
    is_missing_bbox,
    log_bbox_summary,
    looks_like_group_photo,
    parse_bboxes_from_ai_payload,
    parse_books_from_ai_payload,
    should_run_bbox_segmentation,
    sort_books_reading_order,
)

logger = logging.getLogger(__name__)

AI_SYSTEM = (
    "You are an expert comic book cover identification specialist. "
    "Identify every comic book visible in the photo. Return JSON only with this schema: "
    '{"books":[{"bbox":{"x":0,"y":0,"width":0,"height":0},'
    '"publisher_guess":"","series_guess":"","issue_number_guess":null,'
    '"subtitle_guess":"","variant_guess":"","cover_year_guess":"",'
    '"visible_title_text":"","visible_issue_text":"","visible_publisher_text":"",'
    '"visible_character_text":"","confidence":0,"uncertainty_reason":"",'
    '"alternate_titles":[],"reason":""}]} '
    "Rules: bbox values are normalized 0-1 relative to image size (x,y = top-left corner). "
    "Return exactly one books[] object per visible comic cover — never merge multiple comics into one entry. "
    "If six comics are visible, return six objects with six distinct bboxes. "
    "Stacked, overlapping, or grid layouts still require separate bboxes when covers are visible. "
    "Each bbox must tightly frame one cover (not the entire photo). "
    "Do not invent issue numbers; if unclear use null for issue_number_guess and put raw text in visible_issue_text. "
    "issue_number_guess must be a numeric comic issue identifier only (examples: 4, 104, 1/2, 25.NOW). "
    "Never put cover subtitles, taglines, story arcs, or slogans in issue_number_guess "
    '(for example "The Initiative" or "Introducing The Spirits" belong in subtitle_guess or visible_title_text, not issue_number_guess). '
    "If the issue number is not visible on the cover, issue_number_guess must be null. "
    "If title is uncertain, provide best series_guess plus alternate_titles. "
    "Include publisher imprints when visible. "
    "Include partially obscured books with lower confidence. "
    "Confidence must reflect actual certainty (0-1)."
)

BBOX_SEGMENTATION_SYSTEM = (
    "You locate comic book covers in a photo. Return JSON only: "
    '{"comic_count":6,"bboxes":[{"x":0.0,"y":0.0,"width":0.3,"height":0.5}, ...]} '
    "Rules: comic_count = number of distinct visible comic covers. "
    "bboxes must have one entry per comic with normalized 0-1 coordinates (x,y,width,height). "
    "Never return a single bbox covering the whole image when multiple comics are visible. "
    "Do not merge comics. Include partially visible covers at edges."
)


def _abs_path(relative: str, *, image_id: int | None = None) -> Path:
    return resolve_photo_import_storage_path(relative, image_id=image_id)


def _normalize_book_entry(book: dict[str, Any]) -> dict[str, Any]:
    """Map new schema + legacy keys to a unified dict."""
    series = book.get("series_guess") or book.get("series") or book.get("title_text") or ""
    issue_raw = book.get("issue_number_guess")
    if issue_raw is None:
        issue_raw = book.get("issue_number") or ""
    issue = "" if issue_raw is None else str(issue_raw).strip()
    if issue.lower() in {"null", "none", "?"}:
        issue = ""
    publisher = book.get("publisher_guess") or book.get("publisher") or ""
    variant = book.get("variant_guess") or book.get("variant_hint") or ""
    year = book.get("cover_year_guess") or book.get("cover_year") or ""
    alternates = book.get("alternate_titles") or []
    if not isinstance(alternates, list):
        alternates = []
    confidence = float(book.get("confidence") or 0.0)
    bbox = extract_bbox_from_book(book)
    normalized = {
        "bbox": bbox,
        "series_guess": str(series).strip(),
        "issue_number_guess": issue or None,
        "publisher_guess": str(publisher).strip(),
        "subtitle_guess": str(book.get("subtitle_guess") or "").strip(),
        "variant_guess": str(variant).strip(),
        "cover_year_guess": str(year).strip(),
        "visible_title_text": str(book.get("visible_title_text") or series or "").strip(),
        "visible_issue_text": str(book.get("visible_issue_text") or "").strip(),
        "visible_publisher_text": str(book.get("visible_publisher_text") or publisher or "").strip(),
        "visible_character_text": str(book.get("visible_character_text") or "").strip(),
        "confidence": confidence,
        "uncertainty_reason": str(book.get("uncertainty_reason") or "").strip(),
        "alternate_titles": [str(t).strip() for t in alternates if str(t).strip()],
        "reason": str(book.get("reason") or "").strip(),
    }
    return apply_photo_issue_sanitization(normalized)  # type: ignore[return-value]


class RecognitionConfigError(RuntimeError):
    """Raised when the AI provider is not configured (distinct from runtime failures)."""


def _call_openai_vision_json(
    image_bytes: bytes,
    *,
    image_id: int,
    system_prompt: str,
    user_text: str,
    log_label: str,
) -> dict[str, Any]:
    import urllib.request

    settings = get_settings()
    if not settings.openai_api_key:
        raise RecognitionConfigError("OpenAI API key is not configured (settings.openai_api_key is empty)")

    model = settings.openai_order_parser_model
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    logger.info(
        "photo_import.recognition.%s.request image_id=%s model=%s image_bytes=%d",
        log_label,
        image_id,
        model,
        len(image_bytes),
    )
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ],
            },
        ],
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    started = time.monotonic()
    with urllib.request.urlopen(req, timeout=90) as resp:
        raw_text = resp.read().decode("utf-8")
    elapsed_ms = int((time.monotonic() - started) * 1000)
    payload = json.loads(raw_text)
    content = payload["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    logger.info(
        "photo_import.recognition.%s.response image_id=%s elapsed_ms=%d content_len=%d",
        log_label,
        image_id,
        elapsed_ms,
        len(content or ""),
    )
    return parsed


def _call_openai_vision(image_bytes: bytes, *, image_id: int) -> dict[str, Any]:
    parsed = _call_openai_vision_json(
        image_bytes,
        image_id=image_id,
        system_prompt=AI_SYSTEM,
        user_text=(
            "List every comic book cover visible in this photo. "
            "Return one JSON object per visible comic with its own bbox. "
            "Read cover logos and title text carefully. "
            "Do not guess issue numbers you cannot read."
        ),
        log_label="identify",
    )
    if "books" not in parsed:
        books = parse_books_from_ai_payload(parsed)
        parsed = {"books": books}
    logger.info(
        "photo_import.recognition.parsed image_id=%s book_count=%d",
        image_id,
        len(parsed.get("books") or []),
    )
    return parsed


def _call_openai_bbox_segmentation(image_bytes: bytes, *, image_id: int) -> dict[str, Any]:
    return _call_openai_vision_json(
        image_bytes,
        image_id=image_id,
        system_prompt=BBOX_SEGMENTATION_SYSTEM,
        user_text=(
            "How many comic book covers are visible? Return comic_count and one bbox per cover. "
            "Use separate boxes for each comic even in a grid or stack."
        ),
        log_label="bbox_segmentation",
    )


def _fallback_books(*, reason: str) -> dict[str, Any]:
    return {
        "books": [
            {
                "bbox": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
                "series_guess": "",
                "issue_number_guess": None,
                "publisher_guess": "",
                "visible_title_text": "",
                "visible_issue_text": "",
                "confidence": 0.1,
                "uncertainty_reason": reason,
                "alternate_titles": [],
                "reason": f"Placeholder detection ({reason})",
            }
        ]
    }


def resolve_books_for_image(
    *,
    image_id: int,
    image_bytes: bytes,
    image_width: int,
    image_height: int,
    books_raw: list[dict[str, Any]],
    raw_response: dict[str, Any],
    allow_bbox_retry: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Apply multi-comic segmentation fallbacks before persisting detections."""
    log_bbox_summary(image_id=image_id, image_width=image_width, image_height=image_height, books=books_raw)
    group_photo = looks_like_group_photo(image_width=image_width, image_height=image_height)

    if not should_run_bbox_segmentation(books_raw, image_width=image_width, image_height=image_height):
        logger.info(
            "photo_import.segmentation.skip image_id=%s reason=distinct_bboxes_ok books=%d",
            image_id,
            len(books_raw),
        )
        return [_normalize_book_entry(b) for b in sort_books_reading_order(books_raw)][:MAX_DETECTED_BOOKS], raw_response

    if not allow_bbox_retry or raw_response.get("fallback"):
        logger.warning(
            "photo_import.segmentation.skipped_retry image_id=%s books=%d fallback=%s group_photo=%s",
            image_id,
            len(books_raw),
            bool(raw_response.get("fallback")),
            group_photo,
        )
        if group_photo and books_raw:
            layout_count = estimate_comic_slots_from_layout(image_width=image_width, image_height=image_height)
            if layout_count > 1:
                bboxes = grid_bboxes_for_count(layout_count)
                expanded = expand_books_to_match_bboxes(
                    books_raw,
                    bboxes,
                    reason="layout_grid_no_ai_retry",
                )
                raw_response = {**raw_response, "layout_grid_fallback": layout_count}
                return [_normalize_book_entry(b) for b in expanded][:MAX_DETECTED_BOOKS], raw_response
        return [_normalize_book_entry(b) for b in sort_books_reading_order(books_raw)][:MAX_DETECTED_BOOKS], raw_response

    seg_payload: dict[str, Any] | None = None
    try:
        seg_payload = _call_openai_bbox_segmentation(image_bytes, image_id=image_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("photo_import.segmentation.bbox_retry_failed image_id=%s error=%s", image_id, exc)

    bboxes: list[dict[str, float]] = parse_bboxes_from_ai_payload(seg_payload or {}) if seg_payload else []
    count = comic_count_from_payload(seg_payload or {}) if seg_payload else None
    logger.info(
        "photo_import.segmentation.bbox_retry image_id=%s comic_count=%s bbox_count=%d group_photo=%s",
        image_id,
        count,
        len(bboxes),
        group_photo,
    )

    layout_estimate = estimate_comic_slots_from_layout(image_width=image_width, image_height=image_height)
    target_count = count if count and count > 1 else None
    if target_count is None and group_photo and layout_estimate > 1:
        target_count = layout_estimate
        logger.info(
            "photo_import.segmentation.layout_estimate image_id=%s slots=%d",
            image_id,
            layout_estimate,
        )

    if len(bboxes) <= 1 and target_count and target_count > 1:
        bboxes = grid_bboxes_for_count(int(target_count))
        logger.info(
            "photo_import.segmentation.grid_fallback image_id=%s count=%d bbox_count=%d",
            image_id,
            target_count,
            len(bboxes),
        )

    if len(bboxes) > 1:
        expanded = expand_books_to_match_bboxes(
            books_raw,
            bboxes,
            reason="bbox_segmentation_retry",
        )
        raw_response = {**raw_response, "bbox_segmentation": seg_payload}
        log_bbox_summary(image_id=image_id, image_width=image_width, image_height=image_height, books=expanded)
        return [_normalize_book_entry(b) for b in expanded][:MAX_DETECTED_BOOKS], raw_response

    if group_photo and layout_estimate > 1:
        bboxes = grid_bboxes_for_count(layout_estimate)
        expanded = expand_books_to_match_bboxes(books_raw, bboxes, reason="layout_grid_after_retry")
        raw_response = {**raw_response, "bbox_segmentation": seg_payload, "layout_grid_fallback": layout_estimate}
        logger.warning(
            "photo_import.segmentation.hard_guard_layout image_id=%s final_bboxes=%d",
            image_id,
            len(bboxes),
        )
        return [_normalize_book_entry(b) for b in expanded][:MAX_DETECTED_BOOKS], raw_response

    return [_normalize_book_entry(b) for b in sort_books_reading_order(books_raw)][:MAX_DETECTED_BOOKS], raw_response


def run_ai_recognition_for_image(session: Session, *, image_id: int) -> None:
    image = session.get(PhotoImportImage, image_id)
    if image is None:
        logger.warning("photo_import.recognition.image_missing image_id=%s", image_id)
        return
    path = _abs_path(image.storage_path, image_id=image_id)
    logger.info(
        "photo_import.recognition.image_received image_id=%s session_id=%s storage_path=%s resolved_path=%s exists=%s",
        image_id,
        image.session_id,
        image.storage_path,
        path,
        path.is_file(),
    )
    logger.info(
        "photo_import.recognition.pipeline image_id=%s version=%s",
        image_id,
        PHOTO_IMPORT_PIPELINE_VERSION,
    )
    with Image.open(path) as img:
        image_width, image_height = img.size
    logger.info(
        "photo_import.recognition.dimensions image_id=%s width=%d height=%d",
        image_id,
        image_width,
        image_height,
    )

    raw = path.read_bytes()
    raw_response: dict[str, Any]
    allow_bbox_retry = True
    try:
        ai_payload = _call_openai_vision(raw, image_id=image_id)
        raw_response = ai_payload
    except RecognitionConfigError as exc:
        logger.error("photo_import.recognition.not_configured image_id=%s detail=%s", image_id, exc)
        ai_payload = _fallback_books(reason="AI not configured")
        raw_response = {"fallback": True, "failure_kind": "not_configured", "failure_detail": str(exc), **ai_payload}
        allow_bbox_retry = False
    except Exception as exc:  # noqa: BLE001
        logger.exception("photo_import.recognition.failed image_id=%s error=%s", image_id, exc)
        ai_payload = _fallback_books(reason=str(exc))
        raw_response = {
            "fallback": True,
            "failure_kind": exc.__class__.__name__,
            "failure_detail": str(exc),
            **ai_payload,
        }
        allow_bbox_retry = False

    books_raw = parse_books_from_ai_payload(ai_payload)
    if not books_raw and raw_response.get("fallback"):
        books_raw = list(ai_payload.get("books") or [])

    logger.info(
        "photo_import.recognition.ai_parse image_id=%s parsed_book_count=%d raw_keys=%s",
        image_id,
        len(books_raw),
        sorted(ai_payload.keys()) if isinstance(ai_payload, dict) else [],
    )
    if isinstance(raw_response, dict) and not raw_response.get("fallback"):
        logger.info(
            "photo_import.recognition.ai_raw_preview image_id=%s preview=%s",
            image_id,
            json.dumps(ai_payload, default=str)[:2000],
        )

    if not books_raw and not raw_response.get("fallback"):
        logger.warning("photo_import.recognition.empty_books image_id=%s", image_id)

    books, raw_response = resolve_books_for_image(
        image_id=image_id,
        image_bytes=raw,
        image_width=image_width,
        image_height=image_height,
        books_raw=books_raw,
        raw_response=raw_response,
        allow_bbox_retry=allow_bbox_retry,
    )

    if not books and not raw_response.get("fallback"):
        logger.error("photo_import.recognition.no_detections image_id=%s after_segmentation", image_id)
        ai_payload = _fallback_books(reason="no detections after segmentation")
        books = [_normalize_book_entry(b) for b in ai_payload["books"]]
        raw_response = {**raw_response, "fallback": True, "failure_kind": "no_detections"}

    session.exec(delete(PhotoImportDetectedBook).where(PhotoImportDetectedBook.image_id == image_id))

    created = 0
    for idx, book in enumerate(books[:MAX_DETECTED_BOOKS]):
        bbox = book.get("bbox") or {}
        crop_result = extract_and_save_crop(
            path,
            bbox,
            session_id=int(image.session_id),
            image_id=image_id,
            idx=idx,
        )
        logger.info(
            "photo_import.recognition.detection image_id=%s index=%d series=%r visible_title=%r "
            "bbox=%s expanded_bbox=%s refined_bbox=%s crop_path=%s crop_dimensions=%sx%s "
            "crop_quality=%s crop_area_percent=%s boundary_method=%s",
            image_id,
            idx,
            book.get("series_guess") or book.get("series"),
            book.get("visible_title_text"),
            bbox,
            crop_result.expanded_bbox,
            crop_result.refined_bbox,
            crop_result.relative_path,
            crop_result.width,
            crop_result.height,
            crop_result.crop_quality,
            crop_result.crop_area_percent,
            crop_result.boundary_method,
        )
        confidence = float(book.get("confidence") or 0.0)
        status = DETECTION_STATUS_DETECTED if confidence >= 0.85 else DETECTION_STATUS_NEEDS_REVIEW
        issue_str = book.get("issue_number_guess")
        issue_store = None
        if issue_str is not None:
            sanitized = normalize_photo_issue_number(str(issue_str))
            issue_store = sanitized[:64] if sanitized else None
        variant = book.get("variant_guess") or ""
        row = PhotoImportDetectedBook(
            session_id=int(image.session_id),
            image_id=int(image.id or 0),
            user_id=int(image.user_id),
            crop_path=crop_result.relative_path,
            bbox_x=clamp_bbox01(bbox.get("x", 0)),
            bbox_y=clamp_bbox01(bbox.get("y", 0)),
            bbox_width=clamp_bbox01(bbox.get("width", 1)) if not is_missing_bbox(bbox) else clamp_bbox01(bbox.get("width", 0)),
            bbox_height=clamp_bbox01(bbox.get("height", 1)) if not is_missing_bbox(bbox) else clamp_bbox01(bbox.get("height", 0)),
            status=status,
            recognition_status=RECOGNITION_STATUS_UNKNOWN,
            confidence=confidence,
            selected_catalog_issue_id=None,
            selected_variant_id=None,
            ai_series=(book.get("series_guess") or book.get("visible_title_text") or "")[:512] or None,
            ai_issue_number=issue_store,
            ai_publisher=(book.get("publisher_guess") or "")[:256] or None,
            ai_subtitle_guess=(book.get("subtitle_guess") or "")[:512] or None,
            ai_variant_hint=variant[:256] or None,
            ai_variant_guess=variant[:256] or None,
            ai_cover_year=str(book.get("cover_year_guess") or "")[:16] or None,
            ai_visible_title_text=(book.get("visible_title_text") or "")[:512] or None,
            ai_visible_issue_text=(book.get("visible_issue_text") or "")[:128] or None,
            ai_visible_publisher_text=(book.get("visible_publisher_text") or "")[:256] or None,
            ai_visible_character_text=(book.get("visible_character_text") or "")[:512] or None,
            ai_uncertainty_reason=(book.get("uncertainty_reason") or "")[:4000] or None,
            ai_alternate_titles=book.get("alternate_titles") or [],
            ai_confidence=confidence,
            ai_reason=(book.get("reason") or "")[:4000] or None,
            raw_ai_response=raw_response if idx == 0 else None,
        )
        session.add(row)
        created += 1
    session.commit()
    logger.info(
        "photo_import.recognition.persisted image_id=%s pipeline=%s ai_books_returned=%d detected_book_rows=%d fallback=%s",
        image_id,
        PHOTO_IMPORT_PIPELINE_VERSION,
        len(books),
        created,
        bool(raw_response.get("fallback")),
    )


def diagnose_image_file(image_path: Path, *, image_id: int = 0) -> dict[str, Any]:
    """Run identify + segmentation without DB (for regression/debug)."""
    raw = image_path.read_bytes()
    with Image.open(image_path) as img:
        image_width, image_height = img.size
    allow_bbox_retry = True
    try:
        ai_payload = _call_openai_vision(raw, image_id=image_id or 1)
        raw_response: dict[str, Any] = dict(ai_payload)
    except Exception as exc:  # noqa: BLE001
        ai_payload = _fallback_books(reason=str(exc))
        raw_response = {"fallback": True, "failure_detail": str(exc), **ai_payload}
        allow_bbox_retry = False

    books_raw = parse_books_from_ai_payload(ai_payload)
    books, raw_response = resolve_books_for_image(
        image_id=image_id or 1,
        image_bytes=raw,
        image_width=image_width,
        image_height=image_height,
        books_raw=books_raw,
        raw_response=raw_response,
        allow_bbox_retry=allow_bbox_retry,
    )
    return {
        "pipeline_version": PHOTO_IMPORT_PIPELINE_VERSION,
        "image_dimensions": {"width": image_width, "height": image_height},
        "group_photo": looks_like_group_photo(image_width=image_width, image_height=image_height),
        "ai_raw_response": ai_payload,
        "parsed_book_count": len(books_raw),
        "final_book_count": len(books),
        "final_bboxes": [b.get("bbox") for b in books],
        "raw_response_meta": {k: v for k, v in raw_response.items() if k != "books"},
    }
