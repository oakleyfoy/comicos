"""R2 cloud asset pipeline: manifest build, upload, download + checksum verify."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import app.services.gcd_cloud_asset_service as svc

_CFG = svc.R2Config(
    endpoint_url="https://acct.r2.cloudflarestorage.com",
    access_key_id="ak",
    secret_access_key="sk",
    bucket="comic-os-data",
)


class FakeR2:
    """In-memory stand-in for the boto3 S3 client used against R2."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def head_object(self, Bucket: str, Key: str):  # noqa: N803
        if Key not in self.objects:
            raise KeyError(Key)
        return {"ContentLength": len(self.objects[Key])}

    def put_object(self, Bucket: str, Key: str, Body: bytes, **_kw):  # noqa: N803
        self.objects[Key] = Body if isinstance(Body, bytes) else bytes(Body)

    def upload_file(self, filename: str, Bucket: str, Key: str):  # noqa: N803
        self.objects[Key] = Path(filename).read_bytes()

    def download_file(self, Bucket: str, Key: str, filename: str):  # noqa: N803
        Path(filename).write_bytes(self.objects[Key])

    def get_object(self, Bucket: str, Key: str):  # noqa: N803
        data = self.objects[Key]

        class _Body:
            def read(self_inner) -> bytes:  # noqa: N805
                return data

        return {"Body": _Body()}


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeR2:
    client = FakeR2()
    monkeypatch.setattr(svc, "load_r2_config", lambda: _CFG)
    monkeypatch.setattr(svc, "r2_client", lambda config=None: client)
    return client


def _db(path: Path, content: bytes) -> Path:
    path.write_bytes(content)
    return path


def test_sha256_file(tmp_path: Path) -> None:
    p = _db(tmp_path / "x.bin", b"hello world")
    assert svc.sha256_file(p) == hashlib.sha256(b"hello world").hexdigest()


def test_upload_creates_folders_and_manifest(fake: FakeR2, tmp_path: Path) -> None:
    master = _db(tmp_path / "master.db", b"M" * 5000)
    slim = _db(tmp_path / "slim.db", b"S" * 4000)
    manifest = svc.upload_gcd_assets(master_path=master, slim_path=slim, version="v1")

    for prefix in svc.BUCKET_PREFIXES:
        assert f"{prefix}.keep" in fake.objects
    assert f"{svc.PREFIX_MASTER}{svc.MASTER_FILENAME}" in fake.objects
    assert f"{svc.PREFIX_SLIM}{svc.SLIM_FILENAME}" in fake.objects

    stored = json.loads(fake.objects[svc.MANIFEST_KEY])
    assert stored == manifest
    assert manifest["version"] == "v1"
    assert manifest["master_sha256"] == hashlib.sha256(b"M" * 5000).hexdigest()
    assert manifest["slim_sha256"] == hashlib.sha256(b"S" * 4000).hexdigest()
    assert manifest["master_size"] == 5000
    assert manifest["slim_size"] == 4000


def test_download_slim_verifies_checksum(fake: FakeR2, tmp_path: Path) -> None:
    master = _db(tmp_path / "master.db", b"M" * 5000)
    slim = _db(tmp_path / "slim.db", b"S" * 4000)
    svc.upload_gcd_assets(master_path=master, slim_path=slim, version="v1")

    dest = tmp_path / "out" / "scanner.db"
    path = svc.download_slim(dest)
    assert path.read_bytes() == b"S" * 4000


def test_download_master_recovers_full_db(fake: FakeR2, tmp_path: Path) -> None:
    master = _db(tmp_path / "master.db", b"M" * 5000)
    slim = _db(tmp_path / "slim.db", b"S" * 4000)
    svc.upload_gcd_assets(master_path=master, slim_path=slim, version="v1")

    dest = tmp_path / "recovered" / "gcd.db"
    path = svc.download_master(dest)
    assert path.read_bytes() == b"M" * 5000


def test_download_rejects_corrupt_checksum(fake: FakeR2, tmp_path: Path) -> None:
    master = _db(tmp_path / "master.db", b"M" * 5000)
    slim = _db(tmp_path / "slim.db", b"S" * 4000)
    svc.upload_gcd_assets(master_path=master, slim_path=slim, version="v1")

    # Corrupt the stored slim object after the manifest was published.
    fake.objects[f"{svc.PREFIX_SLIM}{svc.SLIM_FILENAME}"] = b"S" * 3999 + b"X"
    dest = tmp_path / "out" / "scanner.db"
    with pytest.raises(ValueError, match="mismatch"):
        svc.download_slim(dest)
    assert not dest.exists()


def test_load_r2_config_missing_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    class _S:
        r2_resolved_endpoint_url = ""
        r2_access_key_id = ""
        r2_secret_access_key = ""
        gcd_r2_bucket = ""

    monkeypatch.setattr(svc, "get_settings", lambda: _S())
    with pytest.raises(svc.GcdAssetConfigError):
        svc.load_r2_config()
