"""Cloudflare R2 (S3-compatible) cloud asset pipeline for GCD databases.

Single source of truth shared by the upload/download CLIs and the API startup
bootstrap. The full GCD dump (~6.5 GB) and the slim scanner DB (~64 MB) live in R2;
a manifest records versions + checksums so every host can fetch and verify the
correct file.

Design rules:
    * No hardcoded URLs/buckets — everything comes from environment variables.
    * Checksums (SHA-256) are computed on upload and verified on download.
    * Best-effort on the API host: provisioning failures never crash boot.

Environment variables (see ``app.core.config.Settings``):
    R2_ACCOUNT_ID         Cloudflare account id (builds the endpoint) OR
    R2_ENDPOINT_URL       explicit S3 endpoint (overrides account id)
    R2_ACCESS_KEY_ID      R2 access key
    R2_SECRET_ACCESS_KEY  R2 secret key
    GCD_R2_BUCKET         bucket name (e.g. comic-os-data)
    GCD_SQLITE_PATH       local path the runtime reads the GCD db from
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger("app.gcd_assets")

# Object key layout in the bucket. These are prefixes, not URLs, so they are stable.
PREFIX_MASTER = "gcd/master/"
PREFIX_SLIM = "gcd/slim/"
PREFIX_MANIFESTS = "gcd/manifests/"
MANIFEST_KEY = "gcd/manifests/latest.json"

# Full folder structure the pipeline owns/initializes in the bucket.
BUCKET_PREFIXES = (
    PREFIX_MASTER,
    PREFIX_SLIM,
    PREFIX_MANIFESTS,
    "backups/postgres/",
    "backups/catalog/",
    "covers/",
    "exports/",
)

MASTER_FILENAME = "gcd-master.db"
SLIM_FILENAME = "gcd-barcode-slim.db"

_DOWNLOAD_CHUNK = 8 * 1024 * 1024
_MIN_SLIM_BYTES = 1_000_000


class GcdAssetConfigError(RuntimeError):
    """Raised when required R2 environment configuration is missing."""


@dataclass(frozen=True)
class R2Config:
    endpoint_url: str
    access_key_id: str
    secret_access_key: str
    bucket: str


def load_r2_config() -> R2Config:
    s = get_settings()
    endpoint = s.r2_resolved_endpoint_url
    cfg = R2Config(
        endpoint_url=endpoint,
        access_key_id=s.r2_access_key_id.strip(),
        secret_access_key=s.r2_secret_access_key.strip(),
        bucket=s.gcd_r2_bucket.strip(),
    )
    missing = [
        name
        for name, value in (
            ("R2_ACCOUNT_ID/R2_ENDPOINT_URL", cfg.endpoint_url),
            ("R2_ACCESS_KEY_ID", cfg.access_key_id),
            ("R2_SECRET_ACCESS_KEY", cfg.secret_access_key),
            ("GCD_R2_BUCKET", cfg.bucket),
        )
        if not value
    ]
    if missing:
        raise GcdAssetConfigError(
            "Missing R2 configuration environment variables: " + ", ".join(missing)
        )
    return cfg


def r2_client(config: R2Config | None = None):  # noqa: ANN201 - boto3 client type is dynamic
    import boto3
    from botocore.config import Config as BotoConfig

    cfg = config or load_r2_config()
    return boto3.client(
        "s3",
        endpoint_url=cfg.endpoint_url,
        aws_access_key_id=cfg.access_key_id,
        aws_secret_access_key=cfg.secret_access_key,
        region_name="auto",
        config=BotoConfig(signature_version="s3v4", retries={"max_attempts": 5, "mode": "standard"}),
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(_DOWNLOAD_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_folder_structure(client=None, config: R2Config | None = None) -> None:  # noqa: ANN001
    """Create the bucket's logical folder layout via zero-byte ``.keep`` markers."""
    cfg = config or load_r2_config()
    cli = client or r2_client(cfg)
    for prefix in BUCKET_PREFIXES:
        key = f"{prefix}.keep"
        try:
            cli.head_object(Bucket=cfg.bucket, Key=key)
        except Exception:  # noqa: BLE001 - missing marker -> create it
            cli.put_object(Bucket=cfg.bucket, Key=key, Body=b"")
            logger.info("gcd.assets.folder_created prefix=%s", prefix)


def _build_manifest(*, master: Path, slim: Path, version: str) -> dict[str, Any]:
    return {
        "version": version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "master_filename": MASTER_FILENAME,
        "master_sha256": sha256_file(master),
        "master_size": master.stat().st_size,
        "slim_filename": SLIM_FILENAME,
        "slim_sha256": sha256_file(slim),
        "slim_size": slim.stat().st_size,
    }


def _upload_file(client, cfg: R2Config, *, path: Path, key: str) -> None:  # noqa: ANN001
    size = path.stat().st_size
    logger.info("gcd.assets.upload_start key=%s bytes=%s", key, size)
    client.upload_file(str(path), cfg.bucket, key)
    logger.info("gcd.assets.upload_complete key=%s bytes=%s", key, size)


def upload_gcd_assets(*, master_path: Path, slim_path: Path, version: str | None = None) -> dict[str, Any]:
    """Upload master + slim DBs and publish the manifest. Returns the manifest dict."""
    cfg = load_r2_config()
    client = r2_client(cfg)
    master_path = Path(master_path)
    slim_path = Path(slim_path)
    if not master_path.is_file():
        raise FileNotFoundError(f"master GCD db not found: {master_path}")
    if not slim_path.is_file():
        raise FileNotFoundError(f"slim GCD db not found: {slim_path}")

    ensure_folder_structure(client, cfg)
    resolved_version = version or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    _upload_file(client, cfg, path=master_path, key=f"{PREFIX_MASTER}{MASTER_FILENAME}")
    _upload_file(client, cfg, path=slim_path, key=f"{PREFIX_SLIM}{SLIM_FILENAME}")

    manifest = _build_manifest(master=master_path, slim=slim_path, version=resolved_version)
    logger.info(
        "gcd.assets.checksum_verified master_sha=%s slim_sha=%s",
        manifest["master_sha256"],
        manifest["slim_sha256"],
    )
    client.put_object(
        Bucket=cfg.bucket,
        Key=MANIFEST_KEY,
        Body=json.dumps(manifest, indent=2).encode("utf-8"),
        ContentType="application/json",
    )
    logger.info("gcd.assets.upload_complete key=%s version=%s", MANIFEST_KEY, resolved_version)
    return manifest


def load_manifest(client=None, config: R2Config | None = None) -> dict[str, Any]:  # noqa: ANN001
    cfg = config or load_r2_config()
    cli = client or r2_client(cfg)
    obj = cli.get_object(Bucket=cfg.bucket, Key=MANIFEST_KEY)
    manifest = json.loads(obj["Body"].read().decode("utf-8"))
    logger.info("gcd.assets.version_loaded version=%s", manifest.get("version"))
    return manifest


def _download_to(client, cfg: R2Config, *, key: str, dest: Path, expected_sha: str, expected_size: int) -> Path:  # noqa: ANN001
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".r2-download")
    logger.info("gcd.assets.download_start key=%s -> %s", key, dest)
    client.download_file(cfg.bucket, key, str(tmp))
    actual_size = tmp.stat().st_size
    if expected_size and actual_size != expected_size:
        tmp.unlink(missing_ok=True)
        raise ValueError(f"size mismatch key={key} expected={expected_size} actual={actual_size}")
    actual_sha = sha256_file(tmp)
    if expected_sha and actual_sha != expected_sha.lower():
        tmp.unlink(missing_ok=True)
        raise ValueError(f"sha256 mismatch key={key} expected={expected_sha} actual={actual_sha}")
    tmp.replace(dest)
    logger.info("gcd.assets.checksum_verified key=%s sha=%s", key, actual_sha)
    logger.info("gcd.assets.download_complete key=%s bytes=%s", key, actual_size)
    return dest


def download_master(dest: Path, *, manifest: dict[str, Any] | None = None) -> Path:
    cfg = load_r2_config()
    client = r2_client(cfg)
    m = manifest or load_manifest(client, cfg)
    key = f"{PREFIX_MASTER}{m.get('master_filename', MASTER_FILENAME)}"
    return _download_to(
        client,
        cfg,
        key=key,
        dest=dest,
        expected_sha=str(m.get("master_sha256") or ""),
        expected_size=int(m.get("master_size") or 0),
    )


def download_slim(dest: Path, *, manifest: dict[str, Any] | None = None) -> Path:
    cfg = load_r2_config()
    client = r2_client(cfg)
    m = manifest or load_manifest(client, cfg)
    key = f"{PREFIX_SLIM}{m.get('slim_filename', SLIM_FILENAME)}"
    return _download_to(
        client,
        cfg,
        key=key,
        dest=dest,
        expected_sha=str(m.get("slim_sha256") or ""),
        expected_size=int(m.get("slim_size") or 0),
    )


def slim_db_is_present(path: Path) -> bool:
    p = Path(path)
    return p.is_file() and p.stat().st_size >= _MIN_SLIM_BYTES
