"""P100 AI vision first-pass recognition."""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path
from typing import Any

from PIL import Image
from sqlmodel import Session, delete, select

from app.core.config import get_settings
from app.models.photo_import import (
    DETECTION_STATUS_DETECTED,
    DETECTION_STATUS_NEEDS_REVIEW,
    RECOGNITION_STATUS_FAILED,
    RECOGNITION_STATUS_MATCHED,
    RECOGNITION_STATUS_UNKNOWN,
    PhotoImportDetectedBook,
    PhotoImportImage,
)

REPO_ROOT = Path(__file__).resolve().parents[3]

AI_SYSTEM = (
    "You identify visible comic books in photos. Return JSON only with schema: "
    '{"books":[{"bbox":{"x":0,"y":0,"width":0,"height":0},"series":"","issue_number":"",'
    '"publisher":"","title_text":"","variant_hint":"","cover_year":"","confidence":0,"reason":""}]} '
    "bbox values are normalized 0-1 relative to image size. Return one entry per visible comic."
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


def _call_openai_vision(image_bytes: bytes) -> dict[str, Any]:
    import urllib.error
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
                    {"type": "text", "text": "Identify all comic books visible in this photo."},
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
                "series": "",
                "issue_number": "",
                "publisher": "",
                "title_text": "",
                "variant_hint": "",
                "cover_year": "",
                "confidence": 0.1,
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
        raw_response = ai_payload
    except Exception:
        ai_payload = _fallback_books()
        raw_response = {"fallback": True, **ai_payload}

    books: list[dict[str, Any]] = list(ai_payload.get("books") or [])
    if not books:
        ai_payload = _fallback_books()
        books = list(ai_payload.get("books") or [])

    session.exec(delete(PhotoImportDetectedBook).where(PhotoImportDetectedBook.image_id == image_id))

    for idx, book in enumerate(books[:10]):
        bbox = book.get("bbox") or {}
        crop_rel = _save_crop(path, bbox, session_id=int(image.session_id), image_id=image_id, idx=idx)
        confidence = float(book.get("confidence") or 0.0)
        recognition = RECOGNITION_STATUS_MATCHED if confidence >= 0.5 else RECOGNITION_STATUS_UNKNOWN
        status = DETECTION_STATUS_DETECTED if confidence >= 0.85 else DETECTION_STATUS_NEEDS_REVIEW
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
            recognition_status=recognition,
            confidence=confidence,
            ai_series=(book.get("series") or book.get("title_text") or "")[:512] or None,
            ai_issue_number=str(book.get("issue_number") or "")[:64] or None,
            ai_publisher=(book.get("publisher") or "")[:256] or None,
            ai_variant_hint=(book.get("variant_hint") or "")[:256] or None,
            ai_cover_year=str(book.get("cover_year") or "")[:16] or None,
            ai_confidence=confidence,
            ai_reason=(book.get("reason") or "")[:4000] or None,
            raw_ai_response=raw_response if idx == 0 else None,
        )
        session.add(row)
    session.commit()
