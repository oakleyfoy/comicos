"""Download GCD databases from Cloudflare R2, verifying SHA-256 after download.

Recovery + provisioning tool. On a fresh machine:

    python scripts/download_gcd_assets.py --master   # recover full ~6.5 GB GCD db
    python scripts/download_gcd_assets.py --slim      # fetch ~64 MB scanner db

With neither flag, the slim DB is downloaded (the common case). Destinations
default to the GCD data directory; ``--slim`` writes to ``GCD_SQLITE_PATH`` so the
runtime picks it up immediately.

R2 credentials/bucket come from environment variables (never hardcoded).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.services.gcd_cloud_asset_service import (  # noqa: E402
    MASTER_FILENAME,
    download_master,
    download_slim,
    load_manifest,
)

DEFAULT_DATA_DIR = Path("data/p101/current")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    parser = argparse.ArgumentParser(description="Download GCD assets from R2.")
    parser.add_argument("--master", action="store_true", help="Download the full master GCD db.")
    parser.add_argument("--slim", action="store_true", help="Download the slim scanner db.")
    parser.add_argument("--master-dest", type=Path, default=None)
    parser.add_argument("--slim-dest", type=Path, default=None)
    args = parser.parse_args()

    # Default to slim when neither flag is provided.
    want_master = args.master
    want_slim = args.slim or not (args.master or args.slim)

    manifest = load_manifest()
    print("version loaded:", manifest.get("version"))

    if want_master:
        dest = args.master_dest or (DEFAULT_DATA_DIR / MASTER_FILENAME)
        path = download_master(dest, manifest=manifest)
        print(f"master download complete -> {path}")

    if want_slim:
        dest = args.slim_dest or get_settings().gcd_sqlite_path
        path = download_slim(dest, manifest=manifest)
        print(f"slim download complete -> {path}")

    print("checksum verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
