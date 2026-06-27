"""Upload GCD master + slim databases to Cloudflare R2 and publish the manifest.

Builds the slim DB first when missing, then uploads both files, computes SHA-256
for each, and writes ``gcd/manifests/latest.json``.

R2 credentials and bucket come from environment variables (never hardcoded):
    R2_ACCOUNT_ID or R2_ENDPOINT_URL, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, GCD_R2_BUCKET

Usage:
    python scripts/upload_gcd_assets.py
    python scripts/upload_gcd_assets.py --master data/p101/current/2026-06-15.db \
        --slim data/p101/current/gcd-barcode-slim.db --version 2026-06-15
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.gcd_cloud_asset_service import upload_gcd_assets  # noqa: E402

DEFAULT_MASTER = Path("data/p101/current/2026-06-15.db")
DEFAULT_SLIM = Path("data/p101/current/gcd-barcode-slim.db")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    parser = argparse.ArgumentParser(description="Upload GCD assets to R2.")
    parser.add_argument("--master", type=Path, default=DEFAULT_MASTER)
    parser.add_argument("--slim", type=Path, default=DEFAULT_SLIM)
    parser.add_argument("--version", type=str, default=None)
    parser.add_argument(
        "--build-slim",
        action="store_true",
        help="Build the slim DB from the master before uploading if it is missing.",
    )
    args = parser.parse_args()

    if args.build_slim and not args.slim.is_file():
        from build_slim_gcd_barcode_db import build as build_slim

        build_slim(args.master, args.slim)

    manifest = upload_gcd_assets(master_path=args.master, slim_path=args.slim, version=args.version)
    print("upload complete")
    print(f"  version       {manifest['version']}")
    print(f"  master_sha256 {manifest['master_sha256']}  ({manifest['master_size']} bytes)")
    print(f"  slim_sha256   {manifest['slim_sha256']}  ({manifest['slim_size']} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
