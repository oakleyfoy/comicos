"""P100 AI vision first-pass recognition."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from PIL import Image
from sqlmodel import Session, delete

from app.services.photo_import_issue_number import apply_photo_issue_sanitization, normalize_photo_issue_number
from app.models.photo_import import (
    DETECTION_STATUS_DETECTED,
    DETECTION_STATUS_NEEDS_REVIEW,
    RECOGNITION_STATUS_UNKNOWN,
    PhotoImportDetectedBook,
    PhotoImportImage,
)

REPO_ROOT = Path(__file__).resolve().parents[3]

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


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _save_crop(image_path: Path, bbox: dict[str, float], *, session_id: int, image_id: int, idx: int) -> str:
    crop_dir = REPO_ROOT / "data" / "photo_import" / "crops" / str(session_id)
    crop_dir.mkdir(parents=True, exist_ok=True)
    crop_name = f"{image_id}_{idx}.jpg"
    crop_path = crop_dir / crop_name
    with Image.open(image_path) as img:
        w, h = img.size
        x = int(_clamp01(bbox.get("x", 0)) * w)
        y = int(_clamp01(bbox.get("y", 0)) * h)
        bw = max(1, int(_clamp01(bbox.get("width", 1)) * w))
        bh = max(1, int(_clamp01(bbox.get("height", 1)) * h))
        cropped = img.crop((x, y, min(w, x + bw), min(h, y + bh)))
        cropped.convert("RGB").save(crop_path, format="JPEG", quality=90)
    return str(crop_path.relative_to(REPO_ROOT)).replace("\\", "/")


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


def _call_openai_vision(image_bytes: bytes) -> dict[str, Any]:
    import urllib.request

    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OpenAI not configured")

    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    body = {
        "model": settings.openai_order_parser_model,
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
    with urllib.request.urlopen(req, timeout=90) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    content = payload["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    if "books" not in parsed:
        parsed = {"books": parsed.get("book", []) if isinstance(parsed.get("book"), list) else []}
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
        return
    path = _abs_path(image.storage_path)
    raw = path.read_bytes()
    try:
        ai_payload = _call_openai_vision(raw)
        raw_response: dict[str, Any] = ai_payload
    except Exception:
        ai_payload = _fallback_books()
        raw_response = {"fallback": True, **ai_payload}

    books: list[dict[str, Any]] = list(ai_payload.get("books") or [])
    if not books:
        ai_payload = _fallback_books()
        books = list(ai_payload.get("books") or [])

    session.exec(delete(PhotoImportDetectedBook).where(PhotoImportDetectedBook.image_id == image_id))

    for idx, raw_book in enumerate(books[:10]):
        book = _normalize_book_entry(raw_book)
        bbox = book.get("bbox") or {}
        crop_rel = _save_crop(path, bbox, session_id=int(image.session_id), image_id=image_id, idx=idx)
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
            bbox_x=_clamp01(bbox.get("x", 0)),
            bbox_y=_clamp01(bbox.get("y", 0)),
            bbox_width=_clamp01(bbox.get("width", 1)),
            bbox_height=_clamp01(bbox.get("height", 1)),
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
