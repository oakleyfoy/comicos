"""P100-24/25 pure GPT vision read (no catalog, no crop, no OCR)."""

from __future__ import annotations

import base64
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from sqlmodel import Session, select

from app.core.config import get_settings
from app.models.photo_import import PhotoImportImage
from app.models.photo_import_vision_read import PhotoImportVisionRead
from app.services.photo_import_ai_recognition_service import RecognitionConfigError
from app.services.photo_import_storage_service import resolve_photo_import_storage_path

logger = logging.getLogger(__name__)

VISION_SANDBOX_SYSTEM = (
    "You are a professional comic book identifier. "
    "Identify the comic book shown in this photo as accurately as possible. "
    "Use cover logo, character art, issue number box, barcode area, publisher logo, trade dress, "
    "creator credits, cover design, publication era, and distinctive markings or overprints. "
    "Return JSON only with this schema: "
    '{"publisher":"","series":"","issue_number":null,"issue_title":"","variant_description":"",'
    '"year":"","cover_date":"","barcode":"","confidence":0,"reasoning":"","possible_alternates":[]} '
    "Rules: Do not search a catalog. Do not compare to a ComicOS database. "
    "Do not default to issue #1 unless issue #1 is clearly visible or the cover is known to be issue #1. "
    "If issue number is uncertain, set issue_number to null. "
    "If you infer the issue from known cover art, explain that in reasoning. "
    "If red text, sticker, stamp, price tag, bag glare, or overlay is not part of the printed cover, say that. "
    "If uncertain, list possible_alternates."
)

VISION_SANDBOX_USER = (
    "Identify the comic in this photo using the full uploaded image. "
    "Return the structured JSON only. Do not match against any database."
)


@dataclass
class VisionSandboxReadResult:
    publisher: str
    series: str
    issue_number: str | None
    issue_title: str
    variant_description: str
    year: str
    cover_date: str
    barcode: str
    confidence: float
    reasoning: str
    raw_response: dict[str, Any]
    raw_response_text: str
    possible_alternates: list[str] = field(default_factory=list)


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = str(item).strip()
        if text and text not in out:
            out.append(text)
    return out


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _parse_sandbox_payload(payload: dict[str, Any]) -> VisionSandboxReadResult:
    issue_raw = payload.get("issue_number")
    issue: str | None = None
    if issue_raw is not None and str(issue_raw).strip().lower() not in {"", "null", "none", "n/a"}:
        issue = _as_str(issue_raw)
    try:
        confidence = float(payload.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    return VisionSandboxReadResult(
        publisher=_as_str(payload.get("publisher")),
        series=_as_str(payload.get("series")),
        issue_number=issue,
        issue_title=_as_str(payload.get("issue_title")),
        variant_description=_as_str(payload.get("variant_description")),
        year=_as_str(payload.get("year")),
        cover_date=_as_str(payload.get("cover_date")),
        barcode=_as_str(payload.get("barcode")),
        confidence=max(0.0, min(1.0, confidence)),
        reasoning=_as_str(payload.get("reasoning")),
        possible_alternates=_as_str_list(payload.get("possible_alternates")),
        raw_response=payload,
        raw_response_text="",
    )


def read_comic_with_gpt_vision(image_bytes: bytes, *, image_id: int) -> VisionSandboxReadResult:
    """Call OpenAI vision on the full uploaded image; no catalog or OCR."""
    import urllib.request

    settings = get_settings()
    if not settings.openai_api_key:
        raise RecognitionConfigError("OpenAI API key is not configured (settings.openai_api_key is empty)")

    model = settings.photo_import_vision_sandbox_model
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    logger.info(
        "photo_import.vision_sandbox.request image_id=%s model=%s image_bytes=%d",
        image_id,
        model,
        len(image_bytes),
    )
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": VISION_SANDBOX_SYSTEM},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": VISION_SANDBOX_USER},
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
    with urllib.request.urlopen(req, timeout=120) as resp:
        api_raw_text = resp.read().decode("utf-8")
    elapsed_ms = int((time.monotonic() - started) * 1000)
    api_payload = json.loads(api_raw_text)
    content = api_payload["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    result = _parse_sandbox_payload(parsed if isinstance(parsed, dict) else {})
    result.raw_response = {
        "parsed": parsed,
        "openai_response": api_payload,
    }
    result.raw_response_text = api_raw_text
    logger.info(
        "photo_import.vision_sandbox.response image_id=%s elapsed_ms=%d series=%r issue=%r confidence=%.2f",
        image_id,
        elapsed_ms,
        result.series,
        result.issue_number,
        result.confidence,
    )
    return result


def persist_vision_read(
    session: Session,
    *,
    session_id: int,
    image_id: int,
    result: VisionSandboxReadResult,
) -> PhotoImportVisionRead:
    row = PhotoImportVisionRead(
        session_id=session_id,
        image_id=image_id,
        publisher=result.publisher[:256] or None,
        series=result.series[:512] or None,
        issue_number=result.issue_number[:64] if result.issue_number else None,
        issue_title=result.issue_title[:512] or None,
        variant_description=result.variant_description[:512] or None,
        year=result.year[:16] or None,
        cover_date=result.cover_date[:32] or None,
        barcode=result.barcode[:64] or None,
        confidence=result.confidence,
        reasoning=result.reasoning or None,
        possible_alternates=result.possible_alternates or None,
        raw_response=result.raw_response,
        raw_response_text=result.raw_response_text,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def run_vision_sandbox_for_image(session: Session, *, image_id: int) -> PhotoImportVisionRead | None:
    image = session.get(PhotoImportImage, image_id)
    if image is None:
        logger.warning("photo_import.vision_sandbox.image_missing image_id=%s", image_id)
        return None
    path = resolve_photo_import_storage_path(image.storage_path, image_id=image_id)
    if not path.is_file():
        logger.error("photo_import.vision_sandbox.file_missing image_id=%s path=%s", image_id, path)
        return None
    raw = path.read_bytes()
    try:
        result = read_comic_with_gpt_vision(raw, image_id=image_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("photo_import.vision_sandbox.failed image_id=%s error=%s", image_id, exc)
        raise
    return persist_vision_read(
        session,
        session_id=int(image.session_id),
        image_id=image_id,
        result=result,
    )


def latest_vision_read_for_image(session: Session, *, image_id: int) -> PhotoImportVisionRead | None:
    return session.exec(
        select(PhotoImportVisionRead)
        .where(PhotoImportVisionRead.image_id == image_id)
        .order_by(PhotoImportVisionRead.id.desc())
    ).first()


def vision_reads_for_session(session: Session, *, session_id: int) -> list[PhotoImportVisionRead]:
    return list(
        session.exec(
            select(PhotoImportVisionRead)
            .where(PhotoImportVisionRead.session_id == session_id)
            .order_by(PhotoImportVisionRead.id.asc())
        ).all()
    )
