"""Debug P100-15 multi-comic segmentation for a local image file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from app.services.photo_import_ai_recognition_service import (  # noqa: E402
    PHOTO_IMPORT_PIPELINE_VERSION,
    diagnose_image_file,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="P100-15 photo import segmentation debug")
    parser.add_argument("--image", required=True, help="Path to group photo JPEG/PNG")
    args = parser.parse_args()
    path = Path(args.image)
    if not path.is_file():
        raise SystemExit(f"Image not found: {path}")
    report = diagnose_image_file(path)
    print(f"pipeline_version={PHOTO_IMPORT_PIPELINE_VERSION}")
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
