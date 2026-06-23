"""ComicVine issue barcode helpers."""

from __future__ import annotations

from app.services.comicvine_api_response import (
    comicvine_barcodes_from_issue_row,
    comicvine_volume_id_from_issue_row,
)
from app.services.photo_import_comicvine_ondemand_service import _find_comicvine_volume_id_via_barcode


class _FakeImporter:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def search_issues_by_barcode(self, barcode: str, *, limit: int = 5) -> list[dict]:
        return self._rows

    @staticmethod
    def volume_id_from_issue_api_row(row: dict) -> int | None:
        from app.services.comicvine_catalog_importer import ComicVineCatalogImporter

        return ComicVineCatalogImporter.volume_id_from_issue_api_row(row)


def test_comicvine_barcodes_from_issue_row_splits_commas() -> None:
    row = {"barcode": "76194120401705811, 76194120401705828"}
    assert comicvine_barcodes_from_issue_row(row) == ["76194120401705811", "76194120401705828"]


def test_comicvine_volume_id_from_issue_row() -> None:
    assert comicvine_volume_id_from_issue_row({"volume": {"id": 12345, "name": "Superman"}}) == 12345


def test_ondemand_barcode_resolves_volume_id() -> None:
    from app.models.photo_import_vision_read import PhotoImportVisionRead

    read = PhotoImportVisionRead(
        session_id=1,
        image_id=1,
        barcode="76194120401705811",
        raw_response={},
    )
    importer = _FakeImporter(
        [{"id": 999, "volume": {"id": 54321, "name": "Action Comics"}}]
    )
    assert _find_comicvine_volume_id_via_barcode(importer, read) == 54321
