"""P100-14H learning feedback from confirmed photo import selections."""

from __future__ import annotations

import json
from pathlib import Path

from sqlmodel import Session

from app.models.photo_import import PhotoImportDetectedBook
from app.services.photo_import_crop_service import resolve_crop_abs_path
from app.services.photo_import_fingerprint_service import fingerprint_hashes_for_crop

LEARNING_PATH = Path(__file__).resolve().parents[2] / "data" / "photo_import" / "match_learning.json"
ISSUE_BOOST_POINTS = 8.0
MAX_BOOST = 15.0


def _load_entries() -> list[dict]:
    if not LEARNING_PATH.is_file():
        return []
    try:
        payload = json.loads(LEARNING_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    rows = payload.get("entries")
    return list(rows) if isinstance(rows, list) else []


def _save_entries(entries: list[dict]) -> None:
    LEARNING_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEARNING_PATH.write_text(json.dumps({"entries": entries[-500:]}, indent=2), encoding="utf-8")


def record_photo_import_confirmation(
    session: Session,
    *,
    det: PhotoImportDetectedBook,
    candidate_rankings: list[tuple[int, float]],
) -> None:
    """Append a lightweight learning record (crop hash + selected issue + rankings)."""
    if det.selected_catalog_issue_id is None:
        return
    crop_abs = resolve_crop_abs_path(det.crop_path)
    phash = None
    if crop_abs is not None:
        hashes = fingerprint_hashes_for_crop(crop_abs)
        if hashes:
            phash = hashes[0]
    entry = {
        "phash_prefix": (phash or "")[:16],
        "catalog_issue_id": int(det.selected_catalog_issue_id),
        "series_guess": (det.ai_series or "")[:200],
        "rankings": [{"catalog_issue_id": iid, "score": score} for iid, score in candidate_rankings[:10]],
    }
    entries = _load_entries()
    entries.append(entry)
    _save_entries(entries)


def learning_boost_for_issue(
    *,
    catalog_issue_id: int,
    series_guess: str,
    crop_phash_prefix: str | None,
) -> float:
    """Boost score for issues the user previously confirmed with a similar crop fingerprint."""
    if not crop_phash_prefix:
        return 0.0
    prefix = crop_phash_prefix[:16]
    if not prefix:
        return 0.0
    boost = 0.0
    series_key = (series_guess or "").strip().lower()[:80]
    for row in _load_entries():
        if int(row.get("catalog_issue_id") or 0) != catalog_issue_id:
            continue
        row_prefix = str(row.get("phash_prefix") or "")[:16]
        if row_prefix and row_prefix == prefix:
            boost = max(boost, ISSUE_BOOST_POINTS)
        elif series_key and series_key == str(row.get("series_guess") or "").strip().lower()[:80]:
            boost = max(boost, ISSUE_BOOST_POINTS * 0.5)
    return min(MAX_BOOST, boost)
