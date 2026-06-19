"""P100-22 vision-first comic identification.

Ask OpenAI vision to identify the specific comic *issue* from a full cover photo
(not merely OCR the cover). The structured guess is then verified against the
ComicOS catalog by the candidate service (exact issue, barcode, cover/fingerprint).
This module owns the prompt + parsing only; it never auto-confirms anything.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

VISION_PIPELINE_VERSION = "P100-22"

VISION_SYSTEM = (
    "You are an expert comic book identification specialist. "
    "Identify the SPECIFIC comic book issue shown in the photo — not just the words on the cover. "
    "Use the full cover image: publisher logo, series logo, trade dress, barcode/UPC box, "
    "issue number box, cover text, character art, costume, art style, and layout. "
    "Return JSON only with this exact schema: "
    '{"publisher":"","series_title":"","issue_number":null,"issue_title":"",'
    '"cover_date":"","publication_year":"","barcode_text":"","visible_logo_text":"",'
    '"visible_issue_box_text":"","visible_cover_text":"","confidence":0,'
    '"uncertainty_reason":"","top_identification_reasons":[],"possible_alternates":[]} '
    "Rules: "
    "issue_number must be a numeric comic issue identifier only (examples: 1, 104, 1/2, 25.NOW); "
    "if the issue number is not clearly visible, set issue_number to null and leave the raw text in visible_issue_box_text. "
    "Never put subtitles, taglines, story-arc names, or slogans in issue_number "
    "(for example 'The Initiative' or 'Reborn' belong in issue_title, not issue_number). "
    "Do NOT guess if you are uncertain — lower your confidence and explain why in uncertainty_reason. "
    "When the title is ambiguous, list every plausible series in possible_alternates. "
    "Carefully distinguish similar Marvel X-titles: X-Men, X-Factor, X-Force, X-Man, Uncanny X-Men — "
    "they share trade dress but are different series. "
    "Distinguish a main ongoing series from a miniseries or a numbered relaunch (volume/year). "
    "barcode_text should contain only the digits you can read from the UPC/barcode if present, else empty. "
    "confidence is 0-1 and must reflect genuine certainty about the exact issue."
)

VISION_USER = (
    "Identify the exact comic book issue in this photo. "
    "Return the structured JSON described. Read the logo and issue box carefully, "
    "use cover art and trade dress to disambiguate similar series, "
    "and return possible_alternates whenever the series or issue is uncertain."
)


class VisionUnavailableError(RuntimeError):
    """Raised when vision identification could not run (config missing or call failed)."""


@dataclass
class VisionIdentification:
    publisher: str = ""
    series_title: str = ""
    issue_number: str | None = None
    issue_title: str = ""
    cover_date: str = ""
    publication_year: str = ""
    barcode_text: str = ""
    visible_logo_text: str = ""
    visible_issue_box_text: str = ""
    visible_cover_text: str = ""
    confidence: float = 0.0
    uncertainty_reason: str = ""
    top_identification_reasons: list[str] = field(default_factory=list)
    possible_alternates: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    def is_usable(self) -> bool:
        """Usable when the model returned at least a series title or a barcode to verify."""
        return bool(self.series_title.strip() or self.normalized_barcode())

    def normalized_barcode(self) -> str:
        return normalize_barcode(self.barcode_text)


def normalize_barcode(value: str | None) -> str:
    """Keep digits only (UPC/EAN); short noise strings are dropped."""
    if not value:
        return ""
    digits = re.sub(r"\D", "", str(value))
    return digits if len(digits) >= 8 else ""


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        if value:
            return [str(value).strip()]
        return []
    out: list[str] = []
    for item in value:
        text = str(item).strip()
        if text and text not in out:
            out.append(text)
    return out


def parse_vision_identification(payload: dict[str, Any]) -> VisionIdentification:
    issue_raw = payload.get("issue_number")
    issue = None if issue_raw is None else _as_str(issue_raw)
    if issue is not None and issue.lower() in {"", "null", "none", "?", "n/a"}:
        issue = None
    try:
        confidence = float(payload.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    return VisionIdentification(
        publisher=_as_str(payload.get("publisher")),
        series_title=_as_str(payload.get("series_title")),
        issue_number=issue,
        issue_title=_as_str(payload.get("issue_title")),
        cover_date=_as_str(payload.get("cover_date")),
        publication_year=_as_str(payload.get("publication_year")),
        barcode_text=_as_str(payload.get("barcode_text")),
        visible_logo_text=_as_str(payload.get("visible_logo_text")),
        visible_issue_box_text=_as_str(payload.get("visible_issue_box_text")),
        visible_cover_text=_as_str(payload.get("visible_cover_text")),
        confidence=max(0.0, min(1.0, confidence)),
        uncertainty_reason=_as_str(payload.get("uncertainty_reason")),
        top_identification_reasons=_as_str_list(payload.get("top_identification_reasons")),
        possible_alternates=_as_str_list(payload.get("possible_alternates")),
        raw=payload if isinstance(payload, dict) else {},
    )


def identify_comic_from_image(image_bytes: bytes, *, image_id: int) -> VisionIdentification:
    """Call OpenAI vision for a direct issue identification. Raises VisionUnavailableError on failure."""
    # Lazy import avoids a circular import with the AI recognition service.
    from app.services.photo_import_ai_recognition_service import (
        RecognitionConfigError,
        _call_openai_vision_json,
    )

    try:
        payload = _call_openai_vision_json(
            image_bytes,
            image_id=image_id,
            system_prompt=VISION_SYSTEM,
            user_text=VISION_USER,
            log_label="vision_identify",
        )
    except RecognitionConfigError as exc:
        raise VisionUnavailableError(f"not_configured: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise VisionUnavailableError(f"call_failed: {exc}") from exc

    identification = parse_vision_identification(payload if isinstance(payload, dict) else {})
    logger.info(
        "photo_import.vision.parsed image_id=%s recognition_mode=vision_first publisher=%r series=%r "
        "issue=%r barcode=%r confidence=%.2f alternates=%d",
        image_id,
        identification.publisher,
        identification.series_title,
        identification.issue_number,
        identification.normalized_barcode(),
        identification.confidence,
        len(identification.possible_alternates),
    )
    return identification


def vision_identification_to_book(identification: VisionIdentification) -> dict[str, Any]:
    """Map a vision identification onto the existing 'book' dict consumed by the persist pipeline."""
    from app.services.photo_import_ai_recognition_service import (
        SINGLE_COMIC_FULL_FRAME_BBOX,
        _normalize_book_entry,
    )

    year = identification.publication_year or identification.cover_date
    raw_book = {
        "bbox": dict(SINGLE_COMIC_FULL_FRAME_BBOX),
        "series_guess": identification.series_title,
        "issue_number_guess": identification.issue_number,
        "publisher_guess": identification.publisher,
        "subtitle_guess": identification.issue_title,
        "variant_guess": "",
        "cover_year_guess": year,
        "visible_title_text": identification.visible_logo_text or identification.series_title,
        "visible_issue_text": identification.visible_issue_box_text,
        "visible_publisher_text": identification.publisher,
        "visible_character_text": "",
        "confidence": identification.confidence,
        "uncertainty_reason": identification.uncertainty_reason,
        "alternate_titles": identification.possible_alternates,
        "reason": "; ".join(identification.top_identification_reasons),
    }
    book = _normalize_book_entry(raw_book)
    book["barcode"] = identification.normalized_barcode()
    book["recognition_mode"] = "vision_first"
    return book
