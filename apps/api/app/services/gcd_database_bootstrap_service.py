"""Download the slim GCD barcode database to the API host at startup if missing.

The full GCD dump is too large to deploy, so production hosts (e.g. Render) start
without any GCD file and every barcode scan fails with "GCD database is missing".
When ``GCD_SLIM_DB_URL`` is set, this downloads the slim barcode DB (built by
``scripts/build_slim_gcd_barcode_db.py``) into ``GCD_SQLITE_PATH`` if it is not
already present, so the scanner can resolve barcodes that exist in GCD.

Idempotent and best-effort: a download failure never crashes the API; the scanner
just keeps reporting the missing-database state until ops fixes the source.
"""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
import urllib.request
from pathlib import Path

from app.core.config import get_settings

logger = logging.getLogger("app.startup")

_MIN_VALID_BYTES = 1_000_000  # a real slim DB is tens of MB; reject truncated downloads.


def _sha256_of_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _try_r2_slim_download(target: Path) -> bool:
    """Provision the slim DB from the R2 manifest pipeline. Returns True on success."""
    try:
        from app.services.gcd_cloud_asset_service import (
            GcdAssetConfigError,
            download_slim,
            load_manifest,
        )

        try:
            manifest = load_manifest()
        except GcdAssetConfigError:
            return False
        download_slim(target, manifest=manifest)
        # Make the runtime read from the provisioned file even if GCD_SQLITE_PATH was unset.
        os.environ["GCD_SQLITE_PATH"] = str(target)
        get_settings.cache_clear()  # type: ignore[attr-defined]
        logger.info("gcd.bootstrap.r2_slim_ok path=%s version=%s", target, manifest.get("version"))
        return True
    except Exception:
        logger.exception("gcd.bootstrap.r2_slim_failed target=%s", target)
        return False


def ensure_gcd_database_present() -> bool:
    """Ensure GCD_SQLITE_PATH exists, downloading the slim DB when configured.

    Resolution order: existing file -> R2 manifest pipeline -> single GCD_SLIM_DB_URL.
    Returns True when a usable GCD file is present after the call.
    """
    settings = get_settings()
    target = settings.gcd_sqlite_path
    if target.is_file() and target.stat().st_size >= _MIN_VALID_BYTES:
        logger.info("gcd.bootstrap.present path=%s bytes=%s", target, target.stat().st_size)
        return True

    target.parent.mkdir(parents=True, exist_ok=True)

    if _try_r2_slim_download(target):
        return True

    url = (settings.gcd_slim_db_url or "").strip()
    if not url:
        logger.warning(
            "gcd.bootstrap.missing_no_source path=%s set R2 env vars (GCD_R2_BUCKET + R2_*) "
            "or GCD_SLIM_DB_URL to auto-provision the slim GCD db",
            target,
        )
        return False

    tmp_fd, tmp_name = tempfile.mkstemp(dir=str(target.parent), suffix=".gcd-download")
    tmp_path = Path(tmp_name)
    os.close(tmp_fd)
    try:
        logger.info("gcd.bootstrap.download_start url=%s -> %s", url, target)
        with urllib.request.urlopen(url) as resp, tmp_path.open("wb") as out:  # noqa: S310
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
        size = tmp_path.stat().st_size
        if size < _MIN_VALID_BYTES:
            raise ValueError(f"downloaded file too small ({size} bytes) — treating as failed")

        expected = (settings.gcd_slim_db_sha256 or "").strip().lower()
        if expected:
            actual = _sha256_of_file(tmp_path)
            if actual != expected:
                raise ValueError(f"sha256 mismatch expected={expected} actual={actual}")

        tmp_path.replace(target)
        logger.info("gcd.bootstrap.download_ok path=%s bytes=%s", target, size)
        return True
    except Exception:
        logger.exception("gcd.bootstrap.download_failed url=%s target=%s", url, target)
        tmp_path.unlink(missing_ok=True)
        return False
