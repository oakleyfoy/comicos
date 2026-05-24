from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session, select

from app.core.config import get_settings
from app.db.session import get_engine
from app.models import CoverImage, InventoryCopy, OpsEvent
from app.tasks.jobs import run_cover_image_process_job
from app.tasks.queue import enqueue_cover_image_process_job


def register_and_login(client: TestClient, email: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "supersecret123"})
    response = client.post("/auth/login", json={"email": email, "password": "supersecret123"})
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_order_basic(client: TestClient, token: str) -> dict:
    payload = {
        "retailer": "Whatnot",
        "order_date": "2026-05-19",
        "source_type": "manual",
        "shipping_amount": 0,
        "tax_amount": 0,
        "items": [
            {
                "title": "Invincible",
                "publisher": "Image",
                "issue_number": "1",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 5.0,
            }
        ],
    }
    response = client.post("/orders", json=payload, headers=auth_headers(token))
    assert response.status_code == 201
    return response.json()


def make_png_bytes(size: tuple[int, int] = (11, 13), color: tuple[int, int, int] = (30, 120, 200)) -> bytes:
    image = Image.new("RGB", size, color=color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _cover_storage_path(relative_storage_path: str) -> Path:
    settings = get_settings()
    return settings.cover_images_storage_root / relative_storage_path


def test_enqueue_cover_image_process_job_is_idempotent_for_active_job(monkeypatch) -> None:
    class ExistingJob:
        id = "cover-image-process-42"

        def get_status(self, refresh: bool = False) -> str:
            del refresh
            return "started"

    def fail_enqueue(*args, **kwargs):
        raise AssertionError("queue.enqueue should not be called when active job already exists")

    class FakeQueue:
        name = "ai_parse"

        enqueue = staticmethod(fail_enqueue)

    monkeypatch.setattr("app.tasks.queue.fetch_job_by_id", lambda job_id: ExistingJob())
    monkeypatch.setattr("app.tasks.queue.get_ai_parse_queue", lambda: FakeQueue())

    job = enqueue_cover_image_process_job(cover_image_id=42, user_id=7)
    assert job.id == "cover-image-process-42"


def test_process_cover_image_success_updates_metadata_and_status(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "cover-process-success@example.com")
    created = create_order_basic(client, token)
    order_detail = client.get(f"/orders/{created['order_id']}", headers=auth_headers(token)).json()
    inventory_copy_id = order_detail["items"][0]["inventory_copy_ids"][0]

    upload = client.post(
        f"/inventory/{inventory_copy_id}/cover-images",
        headers=auth_headers(token),
        files={"file": ("scan.png", make_png_bytes(), "image/png")},
        data={"source_type": "upload"},
    )
    assert upload.status_code == 200
    cover_id = upload.json()["id"]

    row = session.get(CoverImage, cover_id)
    assert row is not None
    row.image_width = 999
    row.image_height = 999
    row.file_size = 1
    row.mime_type = "image/gif"
    row.processing_status = "pending"
    row.processing_error = "old error"
    row.processed_at = None
    row.metadata_refreshed_at = None
    session.add(row)
    session.commit()

    inv = session.get(InventoryCopy, inventory_copy_id)
    assert inv is not None
    result = run_cover_image_process_job(cover_id, inv.user_id)
    assert result["cover_image_id"] == cover_id
    assert result["processing_status"] == "processed"

    session.expire_all()
    refreshed = session.get(CoverImage, cover_id)
    assert refreshed is not None
    assert refreshed.processing_status == "processed"
    assert refreshed.processing_error is None
    assert refreshed.mime_type == "image/png"
    assert refreshed.image_width == 11
    assert refreshed.image_height == 13
    assert refreshed.file_size == len(make_png_bytes())
    assert refreshed.processed_at is not None
    assert refreshed.metadata_refreshed_at is not None


def test_process_cover_image_missing_file_marks_failed(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "cover-process-missing@example.com")
    created = create_order_basic(client, token)
    order_detail = client.get(f"/orders/{created['order_id']}", headers=auth_headers(token)).json()
    inventory_copy_id = order_detail["items"][0]["inventory_copy_ids"][0]

    upload = client.post(
        f"/inventory/{inventory_copy_id}/cover-images",
        headers=auth_headers(token),
        files={"file": ("scan.png", make_png_bytes(), "image/png")},
        data={"source_type": "upload"},
    )
    assert upload.status_code == 200
    cover_id = upload.json()["id"]

    row = session.get(CoverImage, cover_id)
    assert row is not None
    storage_path = _cover_storage_path(row.storage_path)
    storage_path.unlink()

    inv = session.get(InventoryCopy, inventory_copy_id)
    assert inv is not None
    with pytest.raises(ValueError, match="missing on disk"):
        run_cover_image_process_job(cover_id, inv.user_id)

    session.expire_all()
    failed = session.get(CoverImage, cover_id)
    assert failed is not None
    assert failed.processing_status == "failed"
    assert failed.processing_error is not None
    assert "missing on disk" in failed.processing_error


def test_process_cover_image_hash_mismatch_marks_failed(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "cover-process-hash@example.com")
    created = create_order_basic(client, token)
    order_detail = client.get(f"/orders/{created['order_id']}", headers=auth_headers(token)).json()
    inventory_copy_id = order_detail["items"][0]["inventory_copy_ids"][0]

    upload = client.post(
        f"/inventory/{inventory_copy_id}/cover-images",
        headers=auth_headers(token),
        files={"file": ("scan.png", make_png_bytes(), "image/png")},
        data={"source_type": "upload"},
    )
    assert upload.status_code == 200
    cover_id = upload.json()["id"]

    row = session.get(CoverImage, cover_id)
    assert row is not None
    storage_path = _cover_storage_path(row.storage_path)
    storage_path.write_bytes(make_png_bytes(size=(17, 19), color=(10, 20, 30)))

    inv = session.get(InventoryCopy, inventory_copy_id)
    assert inv is not None
    with pytest.raises(ValueError, match="SHA-256"):
        run_cover_image_process_job(cover_id, inv.user_id)

    session.expire_all()
    failed = session.get(CoverImage, cover_id)
    assert failed is not None
    assert failed.processing_status == "failed"
    assert failed.processing_error is not None
    assert "SHA-256" in failed.processing_error


def test_processing_does_not_change_linkage_or_primary(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "cover-process-linkage@example.com")
    created = create_order_basic(client, token)
    order_detail = client.get(f"/orders/{created['order_id']}", headers=auth_headers(token)).json()
    inventory_copy_id = order_detail["items"][0]["inventory_copy_ids"][0]

    upload = client.post(
        f"/inventory/{inventory_copy_id}/cover-images",
        headers=auth_headers(token),
        files={"file": ("scan.png", make_png_bytes(), "image/png")},
        data={"source_type": "upload"},
    )
    assert upload.status_code == 200
    cover_id = upload.json()["id"]

    set_primary = client.post(
        f"/inventory/{inventory_copy_id}/cover-images/{cover_id}/primary",
        headers=auth_headers(token),
    )
    assert set_primary.status_code == 200

    inv = session.get(InventoryCopy, inventory_copy_id)
    assert inv is not None
    before_primary = inv.primary_cover_image_id
    before_cover = session.get(CoverImage, cover_id)
    assert before_cover is not None
    before_inventory_link = before_cover.inventory_copy_id
    before_draft_link = before_cover.draft_import_id

    run_cover_image_process_job(cover_id, inv.user_id)

    session.expire_all()
    after_inv = session.get(InventoryCopy, inventory_copy_id)
    after_cover = session.get(CoverImage, cover_id)
    assert after_inv is not None
    assert after_cover is not None
    assert after_inv.primary_cover_image_id == before_primary
    assert after_cover.inventory_copy_id == before_inventory_link
    assert after_cover.draft_import_id == before_draft_link


def test_cover_image_process_endpoints_queue_owner_and_ops(
    client: TestClient,
    monkeypatch,
) -> None:
    token = register_and_login(client, "cover-process-owner@example.com")
    created = create_order_basic(client, token)
    order_detail = client.get(f"/orders/{created['order_id']}", headers=auth_headers(token)).json()
    inventory_copy_id = order_detail["items"][0]["inventory_copy_ids"][0]
    upload = client.post(
        f"/inventory/{inventory_copy_id}/cover-images",
        headers=auth_headers(token),
        files={"file": ("scan.png", make_png_bytes(), "image/png")},
        data={"source_type": "upload"},
    )
    cover_id = upload.json()["id"]

    fake_job = type("FakeJob", (), {"id": f"cover-image-process-{cover_id}"})()
    monkeypatch.setattr(
        "app.services.background_jobs.enqueue_cover_image_process_job",
        lambda **kwargs: fake_job,
    )
    monkeypatch.setattr(
        "app.services.background_jobs.fetch_job_by_id",
        lambda job_id: None,
    )

    owner_response = client.post(f"/cover-images/{cover_id}/process", headers=auth_headers(token))
    assert owner_response.status_code == 202
    assert owner_response.json()["job_id"] == fake_job.id
    assert owner_response.json()["status"] == "queued"

    monkeypatch.setenv("OPS_ADMIN_EMAILS", "cover-process-ops@example.com")
    get_settings.cache_clear()
    ops_token = register_and_login(client, "cover-process-ops@example.com")
    ops_response = client.post(
        f"/ops/cover-images/{cover_id}/process",
        headers=auth_headers(ops_token),
    )
    assert ops_response.status_code == 202
    assert ops_response.json()["job_id"] == fake_job.id
    get_settings.cache_clear()


def test_cover_image_process_ops_endpoint_requires_admin(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "cover-process-admin@example.com")
    get_settings.cache_clear()
    token = register_and_login(client, "cover-process-regular@example.com")
    response = client.post("/ops/cover-images/1/process", headers=auth_headers(token))
    assert response.status_code == 403
    get_settings.cache_clear()


def test_cover_image_process_job_records_ops_event(client: TestClient) -> None:
    token = register_and_login(client, "cover-process-event@example.com")
    created = create_order_basic(client, token)
    order_detail = client.get(f"/orders/{created['order_id']}", headers=auth_headers(token)).json()
    inventory_copy_id = order_detail["items"][0]["inventory_copy_ids"][0]
    upload = client.post(
        f"/inventory/{inventory_copy_id}/cover-images",
        headers=auth_headers(token),
        files={"file": ("scan.png", make_png_bytes(), "image/png")},
        data={"source_type": "upload"},
    )
    cover_id = upload.json()["id"]

    with Session(get_engine()) as session:
        inv = session.get(InventoryCopy, inventory_copy_id)
        assert inv is not None
        result = run_cover_image_process_job(cover_id, inv.user_id)
        assert result["processing_status"] == "processed"
        event = session.exec(
            select(OpsEvent)
            .where(
                OpsEvent.event_type == "cover_image_process",
                OpsEvent.status == "success",
                OpsEvent.user_id == inv.user_id,
            )
            .order_by(OpsEvent.id.desc())
        ).first()
        assert event is not None
        assert event.details_json["cover_image_id"] == cover_id
