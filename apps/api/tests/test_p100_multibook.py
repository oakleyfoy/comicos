"""P100 multi-book photo identification + catalog match."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session, select

from app.models import InventoryCopy
from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries, CatalogUpc
from app.models.photo_import import PhotoImportImage, PhotoImportSession
from app.models.photo_import_vision_read import PhotoImportVisionRead
from app.services.photo_import_catalog_match_service import match_read_to_catalog
from app.services.photo_import_vision_sandbox_service import (
    VisionSandboxReadResult,
    _extract_comics_payloads,
    run_vision_sandbox_for_image,
)
from test_inventory import auth_headers, register_and_login


def _seed_catalog(session: Session) -> CatalogIssue:
    pub = CatalogPublisher(name="Marvel", normalized_name="marvel")
    session.add(pub)
    session.flush()
    ser = CatalogSeries(publisher_id=pub.id, name="Amazing Spider-Man", normalized_name="amazing spider-man")
    session.add(ser)
    session.flush()
    iss = CatalogIssue(series_id=ser.id, publisher_id=pub.id, issue_number="300", normalized_issue_number="300")
    session.add(iss)
    session.commit()
    session.refresh(iss)
    return iss


def _fake(series: str, issue: str, **extra) -> VisionSandboxReadResult:
    return VisionSandboxReadResult(
        publisher=extra.get("publisher", "Marvel"),
        series=series,
        issue_number=issue,
        issue_title="",
        variant_description="",
        year="",
        cover_date="",
        barcode=extra.get("barcode", ""),
        confidence=0.8,
        reasoning="",
        possible_alternates=[],
        raw_response={"parsed": {}},
        raw_response_text="{}",
    )


# ---- parse ----------------------------------------------------------------


def test_extract_comics_array() -> None:
    payloads = _extract_comics_payloads({"comics": [{"series": "A"}, {"series": "B"}]})
    assert len(payloads) == 2


def test_extract_comics_single_back_compat() -> None:
    payloads = _extract_comics_payloads({"series": "Solo", "issue_number": "1"})
    assert len(payloads) == 1
    assert payloads[0]["series"] == "Solo"


def test_extract_comics_empty() -> None:
    assert _extract_comics_payloads({"comics": []}) == []
    assert _extract_comics_payloads({}) == []


# ---- per-book matching ----------------------------------------------------


def test_match_read_by_text(session: Session) -> None:
    iss = _seed_catalog(session)
    read = PhotoImportVisionRead(
        session_id=1, image_id=1, series="Amazing Spider-Man", issue_number="300", publisher="Marvel"
    )
    result = match_read_to_catalog(session, read)
    assert result.catalog_issue_id == int(iss.id)
    assert result.method == "text"


def test_match_read_by_upc(session: Session) -> None:
    iss = _seed_catalog(session)
    session.add(CatalogUpc(issue_id=int(iss.id), upc="759606043879", normalized_upc="759606043879", source="t"))
    session.commit()
    read = PhotoImportVisionRead(session_id=1, image_id=1, series="Whatever", barcode="7 59606 04387 9")
    result = match_read_to_catalog(session, read)
    assert result.catalog_issue_id == int(iss.id)
    assert result.method == "upc"


def test_match_read_no_match(session: Session) -> None:
    _seed_catalog(session)
    read = PhotoImportVisionRead(session_id=1, image_id=1, series="Totally Unknown Indie", issue_number="1")
    result = match_read_to_catalog(session, read)
    assert result.catalog_issue_id is None
    assert result.method == "none"


# ---- persist multi-book + clear-and-rebuild -------------------------------


def test_run_vision_sandbox_persists_one_row_per_book(
    client: TestClient, session: Session, tmp_path, monkeypatch
) -> None:
    token = register_and_login(client, "mb-persist@example.com")
    created = client.post("/api/v1/photo-import/sessions", headers=auth_headers(token)).json()
    import_row = session.exec(
        select(PhotoImportSession).where(PhotoImportSession.session_token == created["session_token"])
    ).one()
    img_path = tmp_path / "stack.jpg"
    Image.new("RGB", (400, 300), color=(9, 9, 9)).save(img_path, format="JPEG")
    image = PhotoImportImage(
        session_id=int(import_row.id),
        user_id=int(import_row.user_id),
        storage_path="data/photo_import/stack.jpg",
        original_filename="stack.jpg",
        mime_type="image/jpeg",
        file_size=1,
        status="processed",
    )
    session.add(image)
    session.commit()
    session.refresh(image)

    import app.services.photo_import_vision_sandbox_service as sandbox

    monkeypatch.setattr(sandbox, "resolve_photo_import_storage_path", lambda *a, **k: Path(img_path))
    monkeypatch.setattr(
        sandbox,
        "read_comics_with_gpt_vision",
        lambda *a, **k: [_fake("Spider-Man", "1"), _fake("X-Men", "266"), _fake("Hulk", "377")],
    )

    rows = run_vision_sandbox_for_image(session, image_id=int(image.id))
    assert len(rows) == 3
    assert [r.detection_index for r in rows] == [0, 1, 2]

    # Clear-and-rebuild: a second run replaces, does not accumulate.
    monkeypatch.setattr(
        sandbox, "read_comics_with_gpt_vision", lambda *a, **k: [_fake("Batman", "404")]
    )
    rows2 = run_vision_sandbox_for_image(session, image_id=int(image.id))
    assert len(rows2) == 1
    remaining = session.exec(
        select(PhotoImportVisionRead).where(PhotoImportVisionRead.image_id == int(image.id))
    ).all()
    assert len(remaining) == 1
    assert remaining[0].series == "Batman"


# ---- add-all + catalog_issue_id linkage -----------------------------------


def _seed_read(session: Session, *, session_token: str, **fields) -> PhotoImportVisionRead:
    import_row = session.exec(
        select(PhotoImportSession).where(PhotoImportSession.session_token == session_token)
    ).one()
    image = PhotoImportImage(
        session_id=int(import_row.id),
        user_id=int(import_row.user_id),
        storage_path="data/photo_import/seed.jpg",
        original_filename="seed.jpg",
        mime_type="image/jpeg",
        file_size=1,
        status="processed",
    )
    session.add(image)
    session.commit()
    session.refresh(image)
    read = PhotoImportVisionRead(session_id=int(import_row.id), image_id=int(image.id), **fields)
    session.add(read)
    session.commit()
    session.refresh(read)
    return read


def test_add_all_session_reads(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "mb-addall@example.com")
    created = client.post("/api/v1/photo-import/sessions", headers=auth_headers(token)).json()
    _seed_read(session, session_token=created["session_token"], series="Saga", issue_number="1", publisher="Image")
    _seed_read(session, session_token=created["session_token"], series="Paper Girls", issue_number="1", publisher="Image")

    res = client.post(
        f"/api/v1/photo-import/sessions/{created['session_token']}/add-all",
        headers=auth_headers(token),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["added_count"] == 2
    assert body["total_copies"] == 2

    grid = client.get("/inventory?page=1&page_size=50", headers=auth_headers(token)).json()
    assert grid["total"] == 2


def test_add_to_inventory_uses_existing_catalog_match(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "mb-cataloglink@example.com")
    created = client.post("/api/v1/photo-import/sessions", headers=auth_headers(token)).json()
    iss = _seed_catalog(session)
    read = _seed_read(
        session,
        session_token=created["session_token"],
        series="Amazing Spider-Man",
        issue_number="300",
        publisher="Marvel",
        catalog_issue_id=int(iss.id),
    )

    res = client.post(
        f"/api/v1/photo-import/vision-read/{read.id}/add-to-inventory",
        headers=auth_headers(token),
    )
    assert res.status_code == 200, res.text
    copy_id = res.json()["inventory_copy_ids"][0]
    copy = session.get(InventoryCopy, copy_id)
    assert copy is not None
    assert copy.catalog_issue_id == int(iss.id)
