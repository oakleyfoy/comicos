"""P100-15 multi-comic segmentation helpers (parse bboxes, fallback layout)."""

from __future__ import annotations

import logging
from typing import Any

from app.services.photo_import_crop_service import clamp_bbox01

logger = logging.getLogger(__name__)

MAX_DETECTED_BOOKS = 16


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_bbox(raw: dict[str, Any] | None) -> dict[str, float]:
    box = raw or {}
    if not isinstance(box, dict):
        box = {}
    return {
        "x": clamp_bbox01(_coerce_float(box.get("x"), 0.0)),
        "y": clamp_bbox01(_coerce_float(box.get("y"), 0.0)),
        "width": clamp_bbox01(_coerce_float(box.get("width"), 0.0)),
        "height": clamp_bbox01(_coerce_float(box.get("height"), 0.0)),
    }


def extract_bbox_from_book(raw: dict[str, Any]) -> dict[str, float]:
    for key in ("bbox", "bounding_box", "boundingBox", "box"):
        candidate = raw.get(key)
        if isinstance(candidate, dict):
            return normalize_bbox(candidate)
    return normalize_bbox({})


def is_full_frame_bbox(bbox: dict[str, float]) -> bool:
    return (
        bbox.get("width", 0.0) >= 0.92
        and bbox.get("height", 0.0) >= 0.92
        and bbox.get("x", 0.0) <= 0.05
        and bbox.get("y", 0.0) <= 0.05
    )


def is_missing_bbox(bbox: dict[str, float]) -> bool:
    return bbox.get("width", 0.0) <= 0.01 or bbox.get("height", 0.0) <= 0.01


def parse_books_from_ai_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize AI JSON into a list of book dicts (supports several key names)."""
    if not isinstance(payload, dict):
        return []
    books_raw: list[Any] = []
    for key in ("books", "book", "comics", "detections", "items"):
        value = payload.get(key)
        if isinstance(value, list) and value:
            books_raw = value
            break
        if isinstance(value, dict):
            books_raw = [value]
            break
    if not books_raw and isinstance(payload.get("results"), list):
        books_raw = payload["results"]
    out: list[dict[str, Any]] = []
    for item in books_raw:
        if isinstance(item, dict):
            out.append(item)
    return out


def parse_bboxes_from_ai_payload(payload: dict[str, Any]) -> list[dict[str, float]]:
    if not isinstance(payload, dict):
        return []
    raw_list = payload.get("bboxes") or payload.get("boxes") or payload.get("bounding_boxes")
    if not isinstance(raw_list, list):
        books = parse_books_from_ai_payload(payload)
        return [extract_bbox_from_book(b) for b in books if not is_missing_bbox(extract_bbox_from_book(b))]
    bboxes: list[dict[str, float]] = []
    for item in raw_list:
        if isinstance(item, dict):
            bbox = normalize_bbox(item)
            if not is_missing_bbox(bbox):
                bboxes.append(bbox)
    return bboxes


def comic_count_from_payload(payload: dict[str, Any]) -> int | None:
    if not isinstance(payload, dict):
        return None
    for key in ("comic_count", "comicCount", "count", "visible_comic_count"):
        if payload.get(key) is not None:
            try:
                return max(0, int(payload[key]))
            except (TypeError, ValueError):
                continue
    return None


def grid_bboxes_for_count(count: int) -> list[dict[str, float]]:
    """Even grid split when vision returns a count but not separate boxes."""
    count = max(1, min(count, MAX_DETECTED_BOOKS))
    cols = 2 if count <= 4 else 3
    rows = (count + cols - 1) // cols
    bboxes: list[dict[str, float]] = []
    for index in range(count):
        row, col = divmod(index, cols)
        bw = 1.0 / cols
        bh = 1.0 / rows
        bboxes.append(
            {
                "x": col * bw,
                "y": row * bh,
                "width": bw,
                "height": bh,
            }
        )
    return bboxes


def expand_books_to_match_bboxes(
    books: list[dict[str, Any]],
    bboxes: list[dict[str, float]],
    *,
    reason: str,
) -> list[dict[str, Any]]:
    """One detection per bbox; reuse metadata when a single book entry was returned for many comics."""
    if not bboxes:
        return books
    if len(bboxes) == len(books):
        merged: list[dict[str, Any]] = []
        for book, bbox in zip(books, bboxes, strict=False):
            entry = dict(book)
            entry["bbox"] = bbox
            merged.append(entry)
        return merged
    template = dict(books[0]) if len(books) == 1 else {}
    expanded: list[dict[str, Any]] = []
    for idx, bbox in enumerate(bboxes):
        entry = dict(template) if template else {}
        entry["bbox"] = bbox
        if len(books) > idx and isinstance(books[idx], dict):
            entry.update({k: v for k, v in books[idx].items() if k != "bbox"})
        entry.setdefault("confidence", 0.35)
        entry.setdefault("reason", reason)
        entry.setdefault("uncertainty_reason", "Segmented from multi-comic photo")
        expanded.append(entry)
    return expanded


def needs_multi_comic_segmentation(books: list[dict[str, Any]], *, image_width: int, image_height: int) -> bool:
    if image_width < 400 or image_height < 400:
        return False
    if len(books) > 1:
        return False
    if not books:
        return True
    bbox = extract_bbox_from_book(books[0])
    if is_missing_bbox(bbox) or is_full_frame_bbox(bbox):
        return True
    return False


def log_bbox_summary(*, image_id: int, image_width: int, image_height: int, books: list[dict[str, Any]]) -> None:
    logger.info(
        "photo_import.segmentation.summary image_id=%s dimensions=%sx%s ai_books=%d bbox_count=%d",
        image_id,
        image_width,
        image_height,
        len(books),
        len(books),
    )
    for idx, book in enumerate(books):
        bbox = extract_bbox_from_book(book)
        logger.info(
            "photo_import.segmentation.bbox image_id=%s index=%d bbox=%s series=%r confidence=%s",
            image_id,
            idx,
            bbox,
            book.get("series_guess") or book.get("visible_title_text"),
            book.get("confidence"),
        )
