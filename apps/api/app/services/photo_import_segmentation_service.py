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


PHOTO_IMPORT_PIPELINE_VERSION = "P100-15b"


def book_has_weak_metadata(book: dict[str, Any]) -> bool:
    series = str(book.get("series_guess") or book.get("visible_title_text") or "").strip()
    publisher = str(book.get("publisher_guess") or book.get("visible_publisher_text") or "").strip()
    issue = book.get("issue_number_guess")
    confidence = float(book.get("confidence") or 0.0)
    if series or publisher:
        return confidence < 0.2
    return confidence < 0.35


def looks_like_group_photo(*, image_width: int, image_height: int) -> bool:
    """Wide shelf/table rows or tall multi-book stacks — not a single portrait cover."""
    w, h = image_width, image_height
    if min(w, h) < 200:
        return False
    if w >= h * 1.15 and w >= 700:
        return True
    if h >= w * 1.35 and h >= 700:
        return True
    return False


def estimate_comic_slots_from_layout(*, image_width: int, image_height: int) -> int:
    """Heuristic slot count for shelf/table group photos when vision under-segments."""
    if image_width <= 0 or image_height <= 0:
        return 1
    ratio = image_width / image_height
    if ratio >= 1.2:
        cols = 3 if image_width >= 900 else 2
        rows = 2 if image_height >= 450 else 1
        return min(MAX_DETECTED_BOOKS, cols * rows)
    if ratio <= 0.85:
        rows = min(8, max(2, int(image_height / max(160, image_width * 1.1))))
        return min(MAX_DETECTED_BOOKS, rows)
    return min(MAX_DETECTED_BOOKS, 4)


def _distinct_bbox_count(books: list[dict[str, Any]]) -> int:
    keys: set[tuple[float, float, float, float]] = set()
    for book in books:
        bbox = extract_bbox_from_book(book)
        keys.add((bbox["x"], bbox["y"], bbox["width"], bbox["height"]))
    return len(keys)


def should_run_bbox_segmentation(
    books: list[dict[str, Any]],
    *,
    image_width: int,
    image_height: int,
) -> bool:
    group = looks_like_group_photo(image_width=image_width, image_height=image_height)
    if not books:
        return group or image_width >= 400
    if len(books) == 1:
        bbox = extract_bbox_from_book(books[0])
        if is_missing_bbox(bbox) or is_full_frame_bbox(bbox):
            return True
        if group and book_has_weak_metadata(books[0]):
            return True
        return False

    if _distinct_bbox_count(books) <= 1:
        return True
    if all(is_full_frame_bbox(extract_bbox_from_book(b)) for b in books):
        return True
    if group and len(books) < estimate_comic_slots_from_layout(image_width=image_width, image_height=image_height):
        return True
    return False


def needs_multi_comic_segmentation(books: list[dict[str, Any]], *, image_width: int, image_height: int) -> bool:
    return should_run_bbox_segmentation(books, image_width=image_width, image_height=image_height)


def log_bbox_summary(*, image_id: int, image_width: int, image_height: int, books: list[dict[str, Any]]) -> None:
    distinct = _distinct_bbox_count(books)
    logger.info(
        "photo_import.segmentation.summary image_id=%s dimensions=%sx%s group_photo=%s ai_books=%d distinct_bboxes=%d",
        image_id,
        image_width,
        image_height,
        looks_like_group_photo(image_width=image_width, image_height=image_height),
        len(books),
        distinct,
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
