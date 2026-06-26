"""P105 manual barcode/supplement debug CLI.

Run the production P105 comic barcode pipeline against a saved image (no intake
session item required) and dump the overlay, region crops, OCR attempts, and the
final supplement decision.

    python scripts/p105_debug_comic_barcode_image.py --image path\\to\\image.jpg --expected-supplement 03921
    python scripts/p105_debug_comic_barcode_image.py --image path\\to\\image.jpg --expected-supplement 00311
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from app.services.p105_comic_barcode_read_service import (  # noqa: E402
    read_comic_barcode_from_image_bytes,
)
from app.services.p105_comic_barcode_regions import opencv_import_status  # noqa: E402

LOGGER = logging.getLogger(__name__)
MANUAL_DEBUG_ROOT = Path("data/p105/debug/manual")


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
    return cleaned[:60] or "image"


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _open_session(database_url: str | None):
    """Best-effort DB session for catalog/fingerprint correction; None if unavailable."""
    try:
        from sqlmodel import Session

        from p97_db import get_p97_engine, resolve_p97_database_url

        engine = get_p97_engine(resolve_p97_database_url(database_url))
        return Session(engine, expire_on_commit=False)
    except Exception as exc:  # noqa: BLE001
        print(f"WARNING: catalog DB unavailable ({exc}); running OCR-only without catalog correction.", file=sys.stderr)
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="P105 manual comic barcode supplement debug")
    parser.add_argument("--image", required=True, type=Path, help="Path to a saved cover/barcode photo")
    parser.add_argument("--expected-supplement", default=None, help="Expected printed 5-digit left supplement")
    parser.add_argument("--slug", default=None, help="Override the output folder name")
    parser.add_argument("--database-url", default=None, help="Catalog DB URL (defaults to P97 resolution)")
    parser.add_argument("--no-db", action="store_true", help="Skip catalog DB (OCR-only)")
    parser.add_argument("--json", action="store_true", help="Also print the full result JSON")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    image_path: Path = args.image
    if not image_path.is_file():
        print(f"ERROR: image not found: {image_path}", file=sys.stderr)
        return 2
    image_bytes = image_path.read_bytes()

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    slug = args.slug or f"{timestamp}_{_slugify(image_path.stem)}"
    debug_dir = MANUAL_DEBUG_ROOT / slug

    session = None if args.no_db else _open_session(args.database_url)
    try:
        result = read_comic_barcode_from_image_bytes(
            image_bytes,
            session=session,
            cover_path=image_path,
            debug_dir=debug_dir,
            log_context=f"p105_manual:{slug}",
        )
    finally:
        if session is not None:
            session.close()

    base = Path(result.region_debug_path) if result.region_debug_path else debug_dir
    overlay_path = base / "overlay.jpg"
    left_path = base / "left_supplement.jpg"
    ocr_debug_path = base / "ocr_debug.json"

    geometry = result.region_ocr_debug.get("geometry", {}) if result.region_ocr_debug else {}
    opencv_ok, opencv_err = opencv_import_status()

    print("=" * 64)
    print(f"P105 manual barcode debug - {image_path}")
    print("=" * 64)
    print("OPENCV / GEOMETRY DETECTION")
    print(f"  opencv_available:    {opencv_ok}")
    if opencv_err:
        print(f"  opencv_import_error: {opencv_err}")
    if geometry:
        orig = geometry.get("original_size", {})
        work = geometry.get("working_size", {})
        det = geometry.get("detection_size", {})
        print("GEOMETRY DIAGNOSTICS")
        print(f"  original_size:  {orig.get('width')}x{orig.get('height')}")
        print(f"  working_size:   {work.get('width')}x{work.get('height')}")
        print(
            f"  detection_size: {det.get('width')}x{det.get('height')} "
            f"(scale={geometry.get('detection_scale')})"
        )
        print(f"  geometry_failed: {geometry.get('geometry_failed')}")
        print(f"  geometry_attempted: {geometry.get('geometry_attempted')}")
        print(f"  opencv_available (run): {geometry.get('opencv_available')}")
        print(f"  fallback_reason: {geometry.get('fallback_reason') or '(none — geometry used)'}")
        if geometry.get("geometry_rejection_reason"):
            print(f"  geometry_rejection_reason: {geometry.get('geometry_rejection_reason')}")
        if geometry.get("exception_message"):
            print(f"  exception_message: {geometry.get('exception_message')}")
        print(f"  contour_count: {geometry.get('contour_count')}")
        candidates = geometry.get("candidate_boxes") or []
        print(f"  candidate_boxes: {len(candidates)}")
        for cand in candidates[:8]:
            print(
                f"    x={cand.get('x')} y={cand.get('y')} w={cand.get('width')} h={cand.get('height')} "
                f"score={cand.get('score')} area_ok={cand.get('passes_area')} "
                f"aspect_ok={cand.get('passes_aspect')} selected={cand.get('selected')}"
            )
        if geometry.get("chosen_candidate"):
            print(f"  chosen_candidate: {geometry.get('chosen_candidate')}")
        rects = geometry.get("rectangles", {})
        for name in ("full_expanded", "price_box", "main_bars", "left_supplement", "right_cover_digit"):
            r = rects.get(name)
            if not r:
                print(f"  {name:18s} (none)")
                continue
            print(
                f"  {name:18s} x={r.get('x')} y={r.get('y')} "
                f"w={r.get('width')} h={r.get('height')}"
            )
        for note in geometry.get("notes", []):
            print(f"  note: {note}")
        print("-" * 64)
    print(f"detection_method:      {result.detection_method}")
    print(f"fallback_reason:       {result.fallback_reason or '(none)'}")
    print(f"main_upc:              {result.main_upc or '(none)'}")
    print(f"decoded_supp (bars):   {result.decoded_supplement or '(none)'}")
    print(f"ocr_supplement:        {result.ocr_supplement or '(none)'}")
    print(f"corrected_supplement:  {result.corrected_supplement or '(none)'}")
    print(f"final_supplement:      {result.final_supplement or '(none)'}")
    print(f"reconstructed_full:    {result.reconstructed_full or '(none)'}")
    print(
        "confidence:            "
        f"main={result.confidence_main:.2f} supplement={result.confidence_left:.2f} "
        f"reconstructed={result.confidence_reconstructed:.2f}"
    )
    print(f"inferred/corrected:    {result.inferred_supplement}")
    print(f"catalog_confirmed:     {result.catalog_confirmed}")
    print(f"fingerprint_confirmed: {result.fingerprint_confirmed}")
    print(f"supplement_disagree:   {result.supplement_disagreement}")
    print(f"auto_match_eligible:   {result.auto_match_allowed}")
    if result.correction_reason:
        print(f"correction_reason:     {result.correction_reason}")
    if result.review_reason:
        print(f"review_reason:         {result.review_reason}")

    print("-" * 64)
    print("top OCR candidates:")
    if result.supplement_candidates:
        for cand in result.supplement_candidates[:5]:
            print(
                f"  {cand.get('digits')}  score={cand.get('score')}  "
                f"reps={cand.get('repeat_count')}  conf={cand.get('ocr_confidence')}  "
                f"catalog={cand.get('catalog_exists')}  fp={cand.get('fingerprint_score')}"
            )
    else:
        print("  (none — left supplement OCR returned no 5-digit candidate)")

    nonblank = [a for a in result.ocr_attempts if a.get("digits")]
    print(f"raw OCR attempts (non-blank {len(nonblank)} / total {len(result.ocr_attempts)}):")
    for attempt in nonblank[:12]:
        print(
            f"  {attempt.get('variant')}: {attempt.get('digits')} "
            f"(conf={attempt.get('confidence')}, {attempt.get('source')})"
        )

    print("-" * 64)
    print(f"overlay.jpg:           {overlay_path}")
    print(f"left_supplement.jpg:   {left_path}")
    print(f"ocr_debug.json:        {ocr_debug_path}")
    print(f"debug_dir:             {base}")

    if args.json:
        print("-" * 64)
        print(json.dumps(result.to_dict(), indent=2, default=str))

    exit_code = 0
    if args.expected_supplement is not None:
        expected = _digits(args.expected_supplement).zfill(5)
        actual = _digits(result.final_supplement)
        ocr_actual = _digits(result.ocr_supplement)
        print("=" * 64)
        if actual == expected:
            label = "via correction" if result.inferred_supplement else "direct OCR"
            print(f"PASS: final supplement {actual} matches expected {expected} ({label}).")
        else:
            print(
                f"FAIL: expected {expected} but final supplement is {actual or '(none)'} "
                f"(raw OCR was {ocr_actual or 'blank'}). See {base} for overlay + attempts."
            )
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
