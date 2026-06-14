from pathlib import Path

from app.core.config import API_ROOT
from app.services.catalog_cover_harvest_service import resolve_catalog_image_local_path


class _FakeImage:
    def __init__(self, local_path: str):
        self.local_path = local_path
        self.issue_id = None
        self.id = 1


def test_resolve_catalog_image_local_path_uses_api_root(monkeypatch, tmp_path):
    rel = Path("data/catalog/covers/test-cover.bin")
    target = API_ROOT / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"\xff\xd8\xff\xd8fake")
    try:
        monkeypatch.chdir(tmp_path)
        assert not (tmp_path / rel).exists()
        resolved = resolve_catalog_image_local_path(None, _FakeImage(str(rel)))  # type: ignore[arg-type]
        assert resolved is not None
        assert resolved == target
    finally:
        if target.exists():
            target.unlink()


def test_resolve_storage_path_relative_to_api_root(monkeypatch, tmp_path):
    from app.services import catalog_cover_harvest_service as harvest

    rel_file = API_ROOT / "data/catalog/_path_test_marker.bin"
    rel_file.parent.mkdir(parents=True, exist_ok=True)
    rel_file.write_bytes(b"x")
    try:
        monkeypatch.chdir(tmp_path)
        resolved = harvest._resolve_storage_path("data/catalog/_path_test_marker.bin")
        assert resolved.exists()
    finally:
        if rel_file.exists():
            rel_file.unlink()
