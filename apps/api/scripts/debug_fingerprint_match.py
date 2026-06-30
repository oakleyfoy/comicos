#!/usr/bin/env python3
"""Replay catalog fingerprint search for one image (debug bundle + console breakdown)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from sqlmodel import Session, create_engine

from app.core.config import get_settings
from app.services.intake_fingerprint_search_debug_service import (
    FingerprintSearchDebugContext,
    build_fingerprint_search_details,
    fingerprint_search_debug_context,
    write_fingerprint_search_debug_bundle,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Debug catalog fingerprint match for one cover image.")
    parser.add_argument("--image", required=True, help="Path to search image (full cover crop)")
    parser.add_argument("--limit", type=int, default=20, help="Number of ranked matches to compute")
    parser.add_argument("--intake-item-id", type=int, default=0, help="Intake item id for bundle path (0 = item_0)")
    args = parser.parse_args()
    image_path = Path(args.image).resolve()
    if not image_path.is_file():
        raise SystemExit(f"Image not found: {image_path}")

    settings = get_settings()
    engine = create_engine(settings.database_url)
    ctx = FingerprintSearchDebugContext(intake_item_id=int(args.intake_item_id))
    with Session(engine) as session:
        with fingerprint_search_debug_context(ctx):
            hits, summary, details = build_fingerprint_search_details(
                session, crop_path=image_path, limit=max(1, int(args.limit))
            )
        payload = {"search": summary, "matches": details, "hit_count": len(hits)}
        print(json.dumps(payload, indent=2, default=str))
        bundle_dir = write_fingerprint_search_debug_bundle(
            crop_path=image_path,
            intake_item_id=int(args.intake_item_id),
            summary=summary,
            matches=details,
        )
        print(f"\nWrote debug bundle: {bundle_dir}", file=sys.stderr)


if __name__ == "__main__":
    main()
