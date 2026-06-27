"""Startup bootstrap that downloads the slim GCD barcode DB when missing."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

import app.services.gcd_database_bootstrap_service as bootstrap


class _Settings:
    def __init__(self, *, gcd_sqlite_path: Path, url: str = "", sha: str = "") -> None:
        self.gcd_sqlite_path = gcd_sqlite_path
        self.gcd_slim_db_url = url
        self.gcd_slim_db_sha256 = sha


def _payload(n: int = 2_000_000) -> bytes:
    return b"SQLite format 3\x00" + b"x" * n


def test_returns_true_when_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "gcd.db"
    db.write_bytes(_payload())
    monkeypatch.setattr(bootstrap, "get_settings", lambda: _Settings(gcd_sqlite_path=db))
    assert bootstrap.ensure_gcd_database_present() is True


def test_no_url_returns_false(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "missing.db"
    monkeypatch.setattr(bootstrap, "get_settings", lambda: _Settings(gcd_sqlite_path=db))
    assert bootstrap.ensure_gcd_database_present() is False
    assert not db.exists()


def test_downloads_when_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "nested" / "gcd.db"
    data = _payload()

    class _Resp:
        def __init__(self) -> None:
            self._buf = data

        def read(self, n: int) -> bytes:
            chunk, self._buf = self._buf[:n], self._buf[n:]
            return chunk

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(
        bootstrap,
        "get_settings",
        lambda: _Settings(gcd_sqlite_path=db, url="https://example.test/gcd.db"),
    )
    monkeypatch.setattr(bootstrap.urllib.request, "urlopen", lambda _u: _Resp())
    assert bootstrap.ensure_gcd_database_present() is True
    assert db.is_file()
    assert db.read_bytes() == data


def test_rejects_sha_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "gcd.db"
    data = _payload()

    class _Resp:
        def __init__(self) -> None:
            self._buf = data

        def read(self, n: int) -> bytes:
            chunk, self._buf = self._buf[:n], self._buf[n:]
            return chunk

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(
        bootstrap,
        "get_settings",
        lambda: _Settings(gcd_sqlite_path=db, url="https://example.test/gcd.db", sha="deadbeef"),
    )
    monkeypatch.setattr(bootstrap.urllib.request, "urlopen", lambda _u: _Resp())
    assert bootstrap.ensure_gcd_database_present() is False
    assert not db.exists()


def test_accepts_matching_sha(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "gcd.db"
    data = _payload()
    sha = hashlib.sha256(data).hexdigest()

    class _Resp:
        def __init__(self) -> None:
            self._buf = data

        def read(self, n: int) -> bytes:
            chunk, self._buf = self._buf[:n], self._buf[n:]
            return chunk

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(
        bootstrap,
        "get_settings",
        lambda: _Settings(gcd_sqlite_path=db, url="https://example.test/gcd.db", sha=sha),
    )
    monkeypatch.setattr(bootstrap.urllib.request, "urlopen", lambda _u: _Resp())
    assert bootstrap.ensure_gcd_database_present() is True
    assert db.read_bytes() == data
