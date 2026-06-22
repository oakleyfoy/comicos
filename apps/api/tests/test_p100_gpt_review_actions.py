"""P100 GPT review actions: edit fields, add to inventory, re-read."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session, select

from app.models import InventoryCopy
from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries
from app.models.photo_import import PhotoImportImage, PhotoImportSession
from app.models.photo_import_vision_read import PhotoImportVisionRead
from app.services.photo_import_vision_sandbox_service import VisionSandboxReadResult
from test_inventory import auth_headers, register_and_login


def _start_session(client: TestClient, token: str) -> dict:
    res = client.post("/api/v1/photo-import/sessions", headers=auth_headers(token))
    assert res.status_code == 200, res.text
    return res.json()


def _seed_catalog_issue(session: Session, *, issue_id: int, series: str, publisher: str, issue_number: str) -> int:
    pub = CatalogPublisher(name=publisher, normalized_name=publisher.lower())
    session.add(pub)
    session.flush()
    ser = CatalogSeries(name=series, normalized_name=series.lower(), publisher_id=pub.id)
    session.add(ser)
    session.flush()
    issue = CatalogIssue(
        id=issue_id,
        series_id=ser.id,
        publisher_id=pub.id,
        issue_number=issue_number,
        normalized_issue_number=issue_number,
    )
    session.add(issue)
    session.commit()
    return issue_id


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
    read = PhotoImportVisionRead(
        session_id=int(import_row.id),
        image_id=int(image.id),
        **fields,
    )
    session.add(read)
    session.commit()
    session.refresh(read)
    return read


def test_edit_vision_read_fields(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "gpt-review-edit@example.com")
    created = _start_session(client, token)
    read = _seed_read(session, session_token=created["session_token"], series="Falcom", issue_number="1")

    res = client.patch(
        f"/api/v1/photo-import/vision-read/{read.id}",
        json={"series": "Falcon", "publisher": "Marvel Comics"},
        headers=auth_headers(token),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["series"] == "Falcon"
    assert body["publisher"] == "Marvel Comics"
    assert body["issue_number"] == "1"


def test_add_vision_read_to_inventory_creates_copy(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "gpt-review-add@example.com")
    created = _start_session(client, token)
    catalog_issue_id = _seed_catalog_issue(
        session, issue_id=88001, series="Falcon", publisher="Marvel", issue_number="1"
    )
    read = _seed_read(
        session,
        session_token=created["session_token"],
        publisher="Marvel",
        series="Falcon",
        issue_number="1",
        confidence=0.95,
        catalog_issue_id=catalog_issue_id,
    )

    res = client.post(
        f"/api/v1/photo-import/vision-read/{read.id}/add-to-inventory",
        headers=auth_headers(token),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["created_count"] == 1
    assert len(body["inventory_copy_ids"]) == 1
    assert body["acquisition_id"] is not None
    assert body["vision_read"]["added_to_inventory"] is True

    copy = session.get(InventoryCopy, body["inventory_copy_ids"][0])
    assert copy is not None
    assert copy.acquisition_id == body["acquisition_id"]
    assert copy.catalog_issue_id == catalog_issue_id
    assert copy.order_item_id is None
    assert copy.variant_id is None
    assert copy.order_status == "received"
    assert copy.received_via == "PHOTO_IMPORT"

    # The copy must actually appear in the user's Inventory grid / collection.
    grid = client.get("/inventory?page=1&page_size=50", headers=auth_headers(token))
    assert grid.status_code == 200, grid.text
    grid_body = grid.json()
    assert grid_body["total"] == 1
    item = grid_body["items"][0]
    assert item["title"] == "Falcon"
    assert item["issue_number"] == "1"
    assert item["publisher"] == "Marvel"


def test_add_to_inventory_is_idempotent_per_read(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "gpt-review-dupe@example.com")
    created = _start_session(client, token)
    read = _seed_read(
        session,
        session_token=created["session_token"],
        publisher="Image",
        series="Saga",
        issue_number="1",
        catalog_issue_id=_seed_catalog_issue(
            session, issue_id=88002, series="Saga", publisher="Image", issue_number="1"
        ),
    )

    first = client.post(
        f"/api/v1/photo-import/vision-read/{read.id}/add-to-inventory",
        headers=auth_headers(token),
    )
    assert first.status_code == 200, first.text

    second = client.post(
        f"/api/v1/photo-import/vision-read/{read.id}/add-to-inventory",
        headers=auth_headers(token),
    )
    assert second.status_code == 409, second.text

    grid = client.get("/inventory?page=1&page_size=50", headers=auth_headers(token)).json()
    assert grid["total"] == 1


def test_add_to_inventory_requires_title(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "gpt-review-notitle@example.com")
    created = _start_session(client, token)
    read = _seed_read(session, session_token=created["session_token"], issue_number="5")

    res = client.post(
        f"/api/v1/photo-import/vision-read/{read.id}/add-to-inventory",
        headers=auth_headers(token),
    )
    assert res.status_code == 400, res.text


def test_reread_overwrites_read(client: TestClient, session: Session, tmp_path, monkeypatch) -> None:
    token = register_and_login(client, "gpt-review-reread@example.com")
    created = _start_session(client, token)
    read = _seed_read(session, session_token=created["session_token"], series="Wrong", issue_number="9")

    img_path = tmp_path / "comic.jpg"
    Image.new("RGB", (300, 400), color=(5, 5, 5)).save(img_path, format="JPEG")

    fake = VisionSandboxReadResult(
        publisher="DC",
        series="Batman",
        issue_number="404",
        issue_title="Year One",
        variant_description="",
        year="1987",
        cover_date="",
        barcode="",
        confidence=0.88,
        reasoning="Trade dress",
        possible_alternates=[],
        raw_response={"parsed": {}},
        raw_response_text="{}",
    )

    import app.services.photo_import_vision_sandbox_service as sandbox

    monkeypatch.setattr(sandbox, "resolve_photo_import_storage_path", lambda *a, **k: Path(img_path))
    with mock.patch.object(sandbox, "read_comics_with_gpt_vision", return_value=[fake]):
        res = client.post(
            f"/api/v1/photo-import/vision-read/{read.id}/reread",
            headers=auth_headers(token),
        )
    assert res.status_code == 200, res.text
    body = res.json()
    # Reread is clear-and-rebuild: returns the list of books found in the photo.
    assert isinstance(body, list)
    assert len(body) == 1
    assert body[0]["series"] == "Batman"
    assert body[0]["issue_number"] == "404"
