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

logger = logging.getLogger(__name__)

from app.services.photo_import_crop_service import REPO_ROOT, clamp_bbox01, extract_and_save_crop

AI_SYSTEM = (
    "You are an expert comic book cover identification specialist. "
    "Identify every comic book visible in the photo. Return JSON only with this schema: "
    '{"books":[{"bbox":{"x":0,"y":0,"width":0,"height":0},'
    '"publisher_guess":"","series_guess":"","issue_number_guess":null,'
    '"subtitle_guess":"","variant_guess":"","cover_year_guess":"",'
    '"visible_title_text":"","visible_issue_text":"","visible_publisher_text":"",'
    '"visible_character_text":"","confidence":0,"uncertainty_reason":"",'
    '"alternate_titles":[],"reason":""}]} '
    "Rules: bbox values are normalized 0-1 relative to image size. "
    "Do not invent issue numbers; if unclear use null for issue_number_guess and put raw text in visible_issue_text. "
    "issue_number_guess must be a numeric comic issue identifier only (examples: 4, 104, 1/2, 25.NOW). "
    "Never put cover subtitles, taglines, story arcs, or slogans in issue_number_guess "
    '(for example "The Initiative" or "Introducing The Spirits" belong in subtitle_guess or visible_title_text, not issue_number_guess). '
    "If the issue number is not visible on the cover, issue_number_guess must be null. "
    "If title is uncertain, provide best series_guess plus alternate_titles. "
    "Include publisher imprints when visible. One object per visible comic. "
    "Include partially obscured books with lower confidence. "
    "Confidence must reflect actual certainty (0-1)."
)


def _abs_path(relative: str) -> Path:
    return REPO_ROOT / relative


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
    normalized = {
        "bbox": book.get("bbox") or {},
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


def _call_openai_vision(image_bytes: bytes, *, image_id: int) -> dict[str, Any]:
    import urllib.request

    settings = get_settings()
    if not settings.openai_api_key:
        raise RecognitionConfigError("OpenAI API key is not configured (settings.openai_api_key is empty)")

    model = settings.openai_order_parser_model
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    logger.info(
        "photo_import.recognition.request image_id=%s model=%s image_bytes=%d b64_len=%d",
        image_id,
        model,
        len(image_bytes),
        len(b64),
    )
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": AI_SYSTEM},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "List every comic book cover visible in this photo. "
                            "Read cover logos and title text carefully. "
                            "Do not guess issue numbers you cannot read."
                        ),
                    },
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
    logger.info(
        "photo_import.recognition.response image_id=%s elapsed_ms=%d content_len=%d preview=%s",
        image_id,
        elapsed_ms,
        len(content or ""),
        (content or "")[:500].replace("\n", " "),
    )
    parsed = json.loads(content)
    if "books" not in parsed:
        parsed = {"books": parsed.get("book", []) if isinstance(parsed.get("book"), list) else []}
    book_count = len(parsed.get("books") or [])
    logger.info(
        "photo_import.recognition.parsed image_id=%s book_count=%d",
        image_id,
        book_count,
    )
    return parsed


def _fallback_books() -> dict[str, Any]:
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
                "uncertainty_reason": "AI unavailable",
                "alternate_titles": [],
                "reason": "Placeholder detection (AI unavailable)",
            }
        ]
    }


def run_ai_recognition_for_image(session: Session, *, image_id: int) -> None:
    image = session.get(PhotoImportImage, image_id)
    if image is None:
        logger.warning("photo_import.recognition.image_missing image_id=%s", image_id)
        return
    path = _abs_path(image.storage_path)
    logger.info(
        "photo_import.recognition.image_received image_id=%s session_id=%s storage_path=%s exists=%s",
        image_id,
        image.session_id,
        image.storage_path,
        path.is_file(),
    )
    raw = path.read_bytes()
    raw_response: dict[str, Any]
    try:
        ai_payload = _call_openai_vision(raw, image_id=image_id)
        raw_response = ai_payload
    except RecognitionConfigError as exc:
        logger.error("photo_import.recognition.not_configured image_id=%s detail=%s", image_id, exc)
        ai_payload = _fallback_books()
        raw_response = {"fallback": True, "failure_kind": "not_configured", "failure_detail": str(exc), **ai_payload}
    except Exception as exc:  # noqa: BLE001 - we record the real cause instead of hiding it
        logger.exception("photo_import.recognition.failed image_id=%s error=%s", image_id, exc)
        ai_payload = _fallback_books()
        raw_response = {
            "fallback": True,
            "failure_kind": exc.__class__.__name__,
            "failure_detail": str(exc),
            **ai_payload,
        }

    books: list[dict[str, Any]] = list(ai_payload.get("books") or [])
    if not books:
        logger.warning("photo_import.recognition.empty_books image_id=%s using_fallback", image_id)
        ai_payload = _fallback_books()
        books = list(ai_payload.get("books") or [])

    session.exec(delete(PhotoImportDetectedBook).where(PhotoImportDetectedBook.image_id == image_id))

    for idx, raw_book in enumerate(books[:10]):
        book = _normalize_book_entry(raw_book)
        bbox = book.get("bbox") or {}
        crop_rel = extract_and_save_crop(
            path,
            bbox,
            session_id=int(image.session_id),
            image_id=image_id,
            idx=idx,
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
            crop_path=crop_rel,
            bbox_x=clamp_bbox01(bbox.get("x", 0)),
            bbox_y=clamp_bbox01(bbox.get("y", 0)),
            bbox_width=clamp_bbox01(bbox.get("width", 1)),
            bbox_height=clamp_bbox01(bbox.get("height", 1)),
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
    session.commit()
    logger.info(
        "photo_import.recognition.persisted image_id=%s detections=%d fallback=%s",
        image_id,
        min(len(books), 10),
        bool(raw_response.get("fallback")),
    )
