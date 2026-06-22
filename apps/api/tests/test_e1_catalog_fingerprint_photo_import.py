from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image
from sqlmodel import Session

from app.models.catalog_master import (
    CatalogImage,
    CatalogImageFingerprint,
    CatalogIssue,
    CatalogPublisher,
    CatalogSeries,
)
from app.models.photo_import import PhotoImportDetectedBook
from app.models.photo_import_vision_read import PhotoImportVisionRead
from app.services.catalog_fingerprint_service import fingerprint_image_path, search_similar_catalog_fingerprints
from app.services.photo_import_candidate_service import _apply_fingerprint_candidate_seeding
from app.services.photo_import_catalog_match_service import match_read_to_catalog


def _jpeg_bytes(color: tuple[int, int, int]) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (120, 180), color=color).save(buf, format="JPEG")
    return buf.getvalue()


def _seed_catalog_with_cover(
    session: Session,
    tmp_path: Path,
    *,
    issue_id: int,
    color: tuple[int, int, int],
    series_name: str = "Test Series",
) -> tuple[CatalogIssue, bytes]:
    publisher = CatalogPublisher(name="Test Pub", normalized_name="test pub")
    session.add(publisher)
    session.flush()
    series = CatalogSeries(name=series_name, normalized_name=series_name.lower(), publisher_id=publisher.id)
    session.add(series)
    session.flush()
    issue = CatalogIssue(
        id=issue_id,
        series_id=series.id,
        publisher_id=publisher.id,
        issue_number="1",
        normalized_issue_number="1",
    )
    session.add(issue)
    session.flush()
    image_bytes = _jpeg_bytes(color)
    cover_path = tmp_path / f"cover-{issue_id}.jpg"
    cover_path.write_bytes(image_bytes)
    image = CatalogImage(
        issue_id=issue.id,
        image_type="cover",
        download_status="ready",
        source="test",
        local_path=str(cover_path),
        source_url=f"https://example.com/{issue_id}.jpg",
    )
    session.add(image)
    session.flush()
    phash, dhash, ahash = fingerprint_image_path(cover_path)
    session.add(
        CatalogImageFingerprint(
            image_id=image.id,
            issue_id=issue.id,
            phash=phash,
            dhash=dhash,
            ahash=ahash,
        )
    )
    session.commit()
    return issue, image_bytes


def test_search_similar_catalog_fingerprints_finds_exact_issue(session: Session, tmp_path: Path) -> None:
    issue, _ = _seed_catalog_with_cover(session, tmp_path, issue_id=9001, color=(10, 20, 30))
    _seed_catalog_with_cover(session, tmp_path, issue_id=9002, color=(200, 50, 50), series_name="Other")
    cover_path = tmp_path / "probe.jpg"
    cover_path.write_bytes(_jpeg_bytes((10, 20, 30)))
    phash, dhash, ahash = fingerprint_image_path(cover_path)
    hits = search_similar_catalog_fingerprints(session, phash=phash, dhash=dhash, ahash=ahash, limit=3)
    assert hits
    assert int(hits[0][0].issue_id or 0) == int(issue.id or 0)
    assert hits[0][1] >= 0.95


def test_fingerprint_candidate_seeding_injects_issue(session: Session, tmp_path: Path) -> None:
    issue, image_bytes = _seed_catalog_with_cover(session, tmp_path, issue_id=9010, color=(40, 80, 120))
    crop_path = tmp_path / "crop.jpg"
    crop_path.write_bytes(image_bytes)
    rel_crop = str(crop_path).replace("\\", "/")
    det = PhotoImportDetectedBook(
        session_id=1,
        image_id=1,
        user_id=1,
        crop_path=rel_crop,
    )

    from unittest.mock import MagicMock

    import app.services.photo_import_candidate_service as cand_mod

    original = cand_mod.resolve_crop_abs_path
    cand_mod.resolve_crop_abs_path = lambda _p: crop_path
    try:
        seeded = _apply_fingerprint_candidate_seeding(session, det=det, scored=[])
    finally:
        cand_mod.resolve_crop_abs_path = original

    assert len(seeded) == 1
    assert int(seeded[0].issue.id or 0) == int(issue.id or 0)
    assert seeded[0].matched_on == "fingerprint_catalog_search"


def test_vision_read_fingerprint_match(session: Session, tmp_path: Path, monkeypatch) -> None:
    issue, image_bytes = _seed_catalog_with_cover(session, tmp_path, issue_id=9020, color=(5, 105, 205))
    crop_path = tmp_path / "vision-crop.jpg"
    crop_path.write_bytes(image_bytes)

    import app.services.photo_import_catalog_match_service as match_mod

    monkeypatch.setattr(match_mod, "resolve_crop_path_for_vision_read", lambda _s, _r: crop_path)

    read = PhotoImportVisionRead(
        session_id=1,
        image_id=1,
        series="Wrong Series",
        issue_number="99",
        publisher="Wrong Pub",
        detection_index=0,
    )
    match = match_read_to_catalog(session, read)
    assert match.method == "fingerprint"
    assert match.catalog_issue_id == int(issue.id or 0)
    assert (match.confidence or 0) >= 0.95
